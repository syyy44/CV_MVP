"""Structured output generation with validation and bounded repair.

LLM output is untrusted until it has passed: JSON extraction, Pydantic schema
validation, and domain post-validation (for example evidence grounding). Each
failure is recorded in the decision ledger; repair is a visible, bounded loop
(`MAX_REPAIR_ATTEMPTS`), not hidden exception handling. Exhaustion raises
`RepairExhaustedError`, which callers convert into a `needs_review` result
instead of a silent drop.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.errors import RepairExhaustedError, StructuredOutputParseError
from app.llm.prompts import REPAIR_STRUCTURED_OUTPUT, PromptTemplate
from app.locale import zh_CN as msg
from app.models.contracts import ValidationSummary
from app.observability.tracing import sanitize_trace_output

TModel = TypeVar("TModel", bound=BaseModel)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_json_block(text: str) -> str:
    """Strip markdown fences / prose around the first top-level JSON object."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        cleaned = cleaned[first_newline + 1 :] if first_newline != -1 else cleaned
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise StructuredOutputParseError(msg.no_json_in_output())
    return cleaned[start : end + 1]


@dataclass
class GenerationMeta:
    prompt_name: str
    prompt_version: str
    model: str = ""
    attempts: int = 1
    repaired: bool = False
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    input_hash: str = ""
    output_hash: str = ""
    errors: list[str] = field(default_factory=list)


REPAIR_INVALID_OUTPUT_MAX_CHARS = 6000
REPAIR_ASSISTANT_OUTPUT_MAX_CHARS = 3500


def _truncate_for_repair(text: str, limit: int = REPAIR_INVALID_OUTPUT_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [输出已截断，共 {len(text)} 字符]"


def _validation_messages(exc: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
    ][:10]


def _numbered_line_count(numbered_source: str) -> int:
    """Max valid line_no in a `render_numbered_source` block (one entry per line)."""
    if not numbered_source.strip():
        return 0
    return numbered_source.count("\n") + 1


# Problems that are best fixed by re-reading the numbered source: invalid line
# numbers, misattributed (irrelevant) citations, and ungrounded numbers.
_REANCHOR_MARKERS = ("行号无效", "几乎无关", "未在简历原文中出现", "均未出现")


def _evidence_repair_source_block(variables: dict, problems: list[str]) -> str:
    """Re-anchor repair on valid line numbers when a cited line_no was invalid.

    The numbered source already lives in the first user message, so it is NOT
    duplicated here. We only restate the valid `[R*]`/`[J*]` ranges to steer the
    model back to a real line number — keeping the repair prompt small. Also
    fires for misattributed citations and ungrounded numbers, which are likewise
    fixed by returning to the numbered source.
    """
    if not any(
        marker in problem for problem in problems for marker in _REANCHOR_MARKERS
    ):
        return ""
    hints: list[str] = []
    if resume_text := variables.get("resume_text"):
        count = _numbered_line_count(resume_text)
        if count:
            hints.append(f"简历有效行号：R1 至 R{count}（source_type=resume）")
    if jd_text := variables.get("jd_text"):
        count = _numbered_line_count(jd_text)
        if count:
            hints.append(f"JD 有效行号：J1 至 J{count}（source_type=jd）")
    if not hints:
        return ""
    return (
        "证据修复：请回到**本对话第一条用户消息**中的「带编号原文」，"
        "把每条 evidence 的 line_no 改成其中真实存在的编号；"
        "line_no 只填数字，不要复制或改写文本。\n"
        + "\n".join(hints)
    )


def generate_structured(
    ctx,
    prompt: PromptTemplate,
    schema: type[TModel],
    variables: dict,
    *,
    node_name: str,
    candidate_id: str | None = None,
    fixture_key: str | None = None,
    post_validate: Callable[[TModel], list[str]] | None = None,
) -> tuple[TModel, GenerationMeta]:
    """ctx: WorkflowContext (provider, ledger, settings, metrics)."""

    messages = prompt.render(**variables)

    meta = GenerationMeta(prompt_name=prompt.name, prompt_version=prompt.version)
    meta.input_hash = sha256_hex(json.dumps(messages, ensure_ascii=False))

    max_attempts = 1 + ctx.settings.max_repair_attempts
    started = time.monotonic()
    last_problems: list[str] = []
    raw_text = ""

    temperature = ctx.settings.default_temperature
    with ctx.tracer.generation(
        node_name,
        model=ctx.settings.model_name,
        messages=messages,
        metadata={
            "prompt_name": prompt.name,
            "prompt_version": prompt.version,
            "schema_name": schema.__name__,
            "candidate_id": candidate_id,
        },
        temperature=temperature,
    ) as generation:
        for attempt in range(1, max_attempts + 1):
            meta.attempts = attempt
            ctx.ledger.emit(
                "llm_call_started",
                node_name=node_name,
                candidate_id=candidate_id,
                prompt_name=prompt.name,
                prompt_version=prompt.version,
                model=ctx.settings.model_name,
                metadata={"schema_name": schema.__name__, "attempt": attempt},
            )
            result = ctx.provider.complete(
                messages,
                fixture_key=fixture_key,
                temperature=temperature,
                response_schema=schema.model_json_schema(),
                response_schema_name=schema.__name__,
            )
            raw_text = result.text
            meta.model = result.model
            meta.input_tokens += result.input_tokens
            meta.output_tokens += result.output_tokens
            ctx.metrics.record_call(result.input_tokens, result.output_tokens)
            generation.update(
                model=result.model,
                output=sanitize_trace_output(raw_text),
                usage_details={
                    "input": meta.input_tokens,
                    "output": meta.output_tokens,
                },
                metadata={
                    "attempt": attempt,
                    "repaired": attempt > 1,
                },
            )

            problems: list[str] = []
            parsed: TModel | None = None
            try:
                # strict=False：容忍字符串值中的裸换行/控制字符（json_object 模式
                # 下长中文输出的常见缺陷，否则整次尝试因一个字符报废）。
                payload = json.loads(extract_json_block(raw_text), strict=False)
                parsed = schema.model_validate(payload)
            except StructuredOutputParseError as exc:
                problems = [exc.message]
            except json.JSONDecodeError as exc:
                problems = [f"invalid JSON: {exc}"]
            except ValidationError as exc:
                problems = _validation_messages(exc)

            if parsed is not None and post_validate is not None and not problems:
                problems = post_validate(parsed)

            if parsed is not None and not problems:
                meta.latency_ms = int((time.monotonic() - started) * 1000)
                meta.output_hash = sha256_hex(raw_text)
                meta.repaired = attempt > 1
                status = "repaired" if meta.repaired else "valid"
                generation.update(
                    metadata={
                        "attempt": attempt,
                        "repaired": meta.repaired,
                        "validation_status": status,
                        "prompt_name": prompt.name,
                        "prompt_version": prompt.version,
                        "latency_ms": meta.latency_ms,
                    }
                )
                if meta.repaired:
                    ctx.ledger.emit(
                        "repair_succeeded",
                        node_name=node_name,
                        candidate_id=candidate_id,
                        schema_name=schema.__name__,
                        prompt_name=prompt.name,
                        prompt_version=prompt.version,
                        model=meta.model,
                        repair_attempt=attempt - 1,
                        output_hash=meta.output_hash,
                    )
                ctx.ledger.add_validation(
                    ValidationSummary(
                        schema_name=schema.__name__,
                        node_name=node_name,
                        candidate_id=candidate_id,
                        status=status,
                        error_count=len(meta.errors),
                        repair_attempts=attempt - 1,
                        messages=meta.errors[:10],
                    )
                )
                return parsed, meta

            last_problems = problems
            meta.errors.extend(problems)
            generation.update(
                level="WARNING",
                status_message="; ".join(problems[:3]),
                metadata={
                    "attempt": attempt,
                    "validation_status": "failed",
                    "error_count": len(problems),
                },
            )
            ctx.ledger.emit(
                "schema_validation_failed",
                node_name=node_name,
                candidate_id=candidate_id,
                schema_name=schema.__name__,
                prompt_name=prompt.name,
                prompt_version=prompt.version,
                model=meta.model,
                validation_status="failed",
                repair_attempt=attempt - 1,
                metadata={"errors": problems[:5]},
            )

            if attempt < max_attempts:
                ctx.tracer.span_event(
                    "repair_attempt",
                    {
                        "attempt": attempt,
                        "error_count": len(problems),
                        "errors": problems[:3],
                    },
                )
                ctx.ledger.emit(
                    "repair_attempted",
                    node_name=node_name,
                    candidate_id=candidate_id,
                    schema_name=schema.__name__,
                    prompt_name=REPAIR_STRUCTURED_OUTPUT.name,
                    prompt_version=REPAIR_STRUCTURED_OUTPUT.version,
                    model=meta.model,
                    repair_attempt=attempt,
                )
                repair_user = REPAIR_STRUCTURED_OUTPUT.user_template.format(
                    errors="\n".join(problems),
                    invalid_output=_truncate_for_repair(raw_text),
                )
                source_block = _evidence_repair_source_block(variables, problems)
                repair_content = f"{REPAIR_STRUCTURED_OUTPUT.system}\n\n{repair_user}"
                if source_block:
                    repair_content = f"{repair_content}\n\n{source_block}"
                truncated_assistant = _truncate_for_repair(
                    raw_text, limit=REPAIR_ASSISTANT_OUTPUT_MAX_CHARS
                )
                messages = [
                    *messages,
                    {"role": "assistant", "content": truncated_assistant},
                    {
                        "role": "user",
                        "content": repair_content,
                    },
                ]

        meta.latency_ms = int((time.monotonic() - started) * 1000)
        generation.update(
            level="ERROR",
            status_message="; ".join(last_problems[:3]),
            metadata={
                "validation_status": "failed",
                "attempts": max_attempts,
                "latency_ms": meta.latency_ms,
                "prompt_name": prompt.name,
                "prompt_version": prompt.version,
            },
        )

    ctx.ledger.emit(
        "repair_failed",
        node_name=node_name,
        candidate_id=candidate_id,
        schema_name=schema.__name__,
        model=meta.model,
        validation_status="failed",
        repair_attempt=max_attempts - 1,
        metadata={"errors": last_problems[:5]},
    )
    ctx.ledger.add_validation(
        ValidationSummary(
            schema_name=schema.__name__,
            node_name=node_name,
            candidate_id=candidate_id,
            status="failed",
            error_count=len(meta.errors),
            repair_attempts=max_attempts - 1,
            messages=meta.errors[:10],
        )
    )
    raise RepairExhaustedError(
        msg.repair_exhausted(schema.__name__, max_attempts, "; ".join(last_problems[:3])),
        attempts=max_attempts,
    )
