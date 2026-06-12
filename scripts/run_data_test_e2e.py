#!/usr/bin/env python3
"""Run a full live E2E test on data/test samples with step I/O + latency logging."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import BaseModel

from app.core.config import get_settings
from app.storage.db import init_db
from app.storage import repository
from app.workflows import steps
from app.workflows.parsing import parse_upload
from app.workflows.runner import (
    create_run_from_uploads,
    execute_run,
    store_parsed_document,
)

TEST_DIR = ROOT / "data" / "test"
JD_FILE = TEST_DIR / "ai_agent_job_description.txt"
RESUME_FILE = TEST_DIR / "沈洋简历_0526.pdf"
TEXT_PREVIEW = 500


def _preview(text: str, limit: int = TEXT_PREVIEW) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [{len(text) - limit} chars truncated]"


def _serialize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if is_dataclass(value) and not isinstance(value, type):
        return _serialize(asdict(value))
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if k in ("text", "jd_text", "resume_text") and isinstance(v, str):
                out[k] = _preview(v)
                out[f"{k}_chars"] = len(v)
            else:
                out[k] = _serialize(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    return value


class StepLogger:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def record(self, step: str, phase: str, *, input_data: Any, output_data: Any, ms: float) -> None:
        self.entries.append(
            {
                "step": step,
                "phase": phase,
                "duration_ms": round(ms, 1),
                "input": _serialize(input_data),
                "output": _serialize(output_data),
                "ts": datetime.now(UTC).isoformat(),
            }
        )
        print(f"[{phase}] {step}: {ms:.0f}ms ({ms / 1000:.1f}s)", flush=True)


def main() -> int:
    if not JD_FILE.exists() or not RESUME_FILE.exists():
        print(f"Missing test files under {TEST_DIR}", file=sys.stderr)
        return 1

    settings = get_settings()
    if not settings.llm_api_key:
        print("LLM_API_KEY required for live run", file=sys.stderr)
        return 1

    init_db()
    logger = StepLogger()
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_dir = TEST_DIR / "e2e_logs" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== E2E test data/test -> {out_dir} ===", flush=True)
    print(f"model={settings.model_name} qianfan={'yes' if settings.qianfan_api_key else 'no'}", flush=True)

    # ---- Phase 1: document parsing (upload-time) ----
    parse_artifacts: dict[str, str] = {}
    parsed_docs: list[tuple[str, Any]] = []

    for label, path in [("jd", JD_FILE), ("resume", RESUME_FILE)]:
        data = path.read_bytes()
        t0 = time.monotonic()
        parsed = parse_upload(path.name, data)
        ms = (time.monotonic() - t0) * 1000
        text_path = out_dir / f"parsed_{label}.txt"
        text_path.write_text(parsed.text or "", encoding="utf-8")
        parse_artifacts[label] = str(text_path)
        parsed_docs.append((label, parsed))
        logger.record(
            f"parse_{label}",
            "ingest",
            input_data={"filename": path.name, "bytes": len(data), "path": str(path)},
            output_data={
                "parse_status": parsed.parse_status,
                "char_count": parsed.char_count,
                "document_hash": parsed.document_hash,
                "page_count": len(parsed.page_texts or []),
                "text_file": str(text_path),
                "text_preview": _preview(parsed.text or ""),
            },
            ms=ms,
        )
        if parsed.parse_status != "parsed":
            print(f"Parse failed for {path.name}: {parsed.parse_status}", file=sys.stderr)
            _write_report(out_dir, logger, None, parse_artifacts, failed=True)
            return 2

    # ---- Phase 2: create run + execute workflow ----
    jd_data = JD_FILE.read_bytes()
    resume_data = RESUME_FILE.read_bytes()
    t_create = time.monotonic()
    run_id = create_run_from_uploads(
        (JD_FILE.name, jd_data),
        [(RESUME_FILE.name, resume_data)],
        idempotency_key=f"e2e-test-{ts}",
    )
    create_ms = (time.monotonic() - t_create) * 1000
    logger.record(
        "create_run_from_uploads",
        "orchestration",
        input_data={"jd": JD_FILE.name, "resumes": [RESUME_FILE.name]},
        output_data={"run_id": run_id},
        ms=create_ms,
    )

    # Patch workflow steps to capture I/O
    originals = {
        "extract_rubric": steps.extract_rubric,
        "extract_profile": steps.extract_profile,
        "analyze_and_score": steps.analyze_and_score,
        "generate_pack": steps.generate_pack,
    }

    def _wrap(name: str, fn):
        def wrapped(*args, **kwargs):
            t0 = time.monotonic()
            arg_names = fn.__code__.co_varnames[: fn.__code__.co_argcount]
            bound = dict(zip(arg_names, args, strict=False))
            bound.update(kwargs)
            inp = {k: v for k, v in bound.items() if k != "ctx"}
            step_path = out_dir / f"step_{name}.json"
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                ms = (time.monotonic() - t0) * 1000
                err_out = {"error": str(exc), "error_type": type(exc).__name__}
                logger.record(name, "workflow", input_data=inp, output_data=err_out, ms=ms)
                step_path.write_text(
                    json.dumps(
                        {
                            "input": _serialize(inp),
                            "output": err_out,
                            "duration_ms": round(ms, 1),
                            "failed": True,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                raise
            ms = (time.monotonic() - t0) * 1000
            if name == "extract_rubric":
                out = {"rubric": result[0], "meta": result[1]}
            elif name == "extract_profile":
                out = {"profile": result[0], "meta": result[1]}
            elif name == "analyze_and_score":
                out = {
                    "analysis": result[0],
                    "score": result[1],
                    "breakdown": result[2],
                    "meta": result[3],
                }
            elif name == "generate_pack":
                out = {"questions": result[0], "follow_ups": result[1], "meta": result[2]}
            else:
                out = result
            logger.record(name, "workflow", input_data=inp, output_data=out, ms=ms)
            step_path.write_text(
                json.dumps(
                    {"input": _serialize(inp), "output": _serialize(out), "duration_ms": round(ms, 1)},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return result

        return wrapped

    for name, fn in originals.items():
        setattr(steps, name, _wrap(name, fn))

    t_run = time.monotonic()
    execute_run(run_id)
    run_ms = (time.monotonic() - t_run) * 1000
    logger.record(
        "execute_run",
        "orchestration",
        input_data={"run_id": run_id},
        output_data={"run_id": run_id},
        ms=run_ms,
    )

    # Restore patched functions
    for name, fn in originals.items():
        setattr(steps, name, fn)

    run = repository.get_run(run_id)
    results = repository.get_candidate_results(run_id)
    events = repository.get_events(run_id)

    summary = {
        "run_id": run_id,
        "status": run.status if run else "unknown",
        "error": run.error if run else None,
        "metrics": run.metrics.model_dump() if run and run.metrics else None,
        "candidate_count": len(results),
        "candidates": [
            {
                "candidate_id": r.candidate_id,
                "candidate_name": r.candidate_name,
                "status": r.status,
                "overall_score": (
                    r.dossier.score.overall_score
                    if r.dossier and hasattr(r.dossier, "score")
                    else None
                ),
                "recommendation": (
                    r.dossier.score.recommendation
                    if r.dossier and hasattr(r.dossier, "score")
                    else None
                ),
                "errors": r.errors,
            }
            for r in results
        ],
        "ledger_event_count": len(events),
    }

    _write_report(out_dir, logger, summary, parse_artifacts, failed=False)

    total_ms = sum(e["duration_ms"] for e in logger.entries)
    print(f"\n=== Done run_id={run_id} status={summary['status']} ===", flush=True)
    print(f"Total logged step time: {total_ms:.0f}ms", flush=True)
    print(f"Report: {out_dir / 'report.json'}", flush=True)
    return 0 if summary["status"] == "completed" else 3


def _write_report(
    out_dir: Path,
    logger: StepLogger,
    summary: dict | None,
    parse_artifacts: dict[str, str],
    *,
    failed: bool,
) -> None:
    report = {
        "failed_early": failed,
        "parse_artifacts": parse_artifacts,
        "steps": logger.entries,
        "summary": summary,
        "timing_totals_ms": {
            "ingest": sum(e["duration_ms"] for e in logger.entries if e["phase"] == "ingest"),
            "workflow": sum(e["duration_ms"] for e in logger.entries if e["phase"] == "workflow"),
            "orchestration": sum(
                e["duration_ms"] for e in logger.entries if e["phase"] == "orchestration"
            ),
            "all_logged": sum(e["duration_ms"] for e in logger.entries),
        },
    }
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
