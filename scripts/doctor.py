"""Readiness check: fail with instructions, not stack traces.

Distinguishes replay-mode requirements (must pass for `make demo`) from
live-mode credentials (optional warnings).
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def check_python() -> tuple[str, str]:
    version = sys.version_info
    if version >= (3, 11):
        return PASS, f"Python {version.major}.{version.minor}.{version.micro}"
    return FAIL, f"Python {version.major}.{version.minor} found; need >= 3.11"


def check_dependencies() -> tuple[str, str]:
    required = ["fastapi", "uvicorn", "pydantic", "langgraph", "openai",
                "httpx", "pypdf", "docx"]
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if missing:
        return FAIL, f"missing packages: {', '.join(missing)} - run 'make install'"
    return PASS, "all required packages importable"


def check_frontend() -> tuple[str, str]:
    frontend = ROOT / "frontend"
    if not (frontend / "package.json").exists():
        return FAIL, f"frontend project missing: {frontend}"
    if (frontend / "dist" / "index.html").exists():
        return PASS, "frontend build present (served by API at /)"
    if (frontend / "node_modules").is_dir():
        return WARN, "frontend deps installed; run 'make ui-build' for prod, or 'make ui' for dev"
    return WARN, "frontend deps not installed - run 'make ui-install' (dev) or 'make ui-build'"


def check_fixtures() -> tuple[str, str]:
    manifest_path = ROOT / "fixtures" / "demo" / "manifest.json"
    if not manifest_path.exists():
        return FAIL, f"demo manifest missing: {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    demo_dir = manifest_path.parent
    missing: list[str] = []
    for rel in [manifest["jd"], *manifest["resumes"]]:
        if not (demo_dir / rel).exists():
            missing.append(rel)
    outputs_dir = demo_dir / "llm_outputs"
    if not (outputs_dir / "rubric.json").exists():
        missing.append("llm_outputs/rubric.json")
    for rel in manifest["resumes"]:
        slug = Path(rel).stem
        for kind in ("profile", "score", "interview_pack"):
            if not (outputs_dir / slug / f"{kind}.json").exists():
                missing.append(f"llm_outputs/{slug}/{kind}.json")
    if missing:
        return FAIL, f"missing replay fixtures: {', '.join(missing[:6])}"
    return PASS, "demo fixtures complete (JD, resumes, captured outputs)"


def check_database() -> tuple[str, str]:
    sys.path.insert(0, str(ROOT))
    from app.core.config import get_settings

    path = get_settings().database_path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        probe = path.parent / ".doctor-probe"
        probe.write_text("ok")
        probe.unlink()
    except OSError as exc:
        return FAIL, f"database directory not writable: {path.parent} ({exc})"
    return PASS, f"SQLite path writable: {path}"


def check_env_file() -> tuple[str, str]:
    if (ROOT / ".env").exists():
        return PASS, ".env present"
    return WARN, ".env not found - defaults apply (replay mode); copy .env.example to customize"


def check_live_mode() -> tuple[str, str]:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.demo_mode == "replay":
        if settings.llm_api_key:
            return PASS, "replay mode active; LLM_API_KEY also set (live mode ready)"
        return PASS, "replay mode active; no LLM key needed"
    if settings.llm_api_key:
        return PASS, (
            f"live mode ready: provider={settings.llm_provider} "
            f"model={settings.model_name} base={settings.openai_base_url}"
        )
    return FAIL, "DEMO_MODE=live but LLM_API_KEY is empty - set it or use DEMO_MODE=replay"


def check_langfuse() -> tuple[str, str]:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.langfuse_configured:
        return PASS, f"Langfuse enabled: {settings.langfuse_host}"
    return WARN, "Langfuse disabled - local ledger/log fallback active (fine for replay demo)"


def main() -> int:
    checks = [
        ("python", check_python),
        ("dependencies", check_dependencies),
        ("frontend", check_frontend),
        ("replay fixtures", check_fixtures),
        ("database", check_database),
        (".env", check_env_file),
        ("llm credentials", check_live_mode),
        ("langfuse", check_langfuse),
    ]
    failed = False
    print("recruiting-assistant doctor\n" + "-" * 60)
    for name, check in checks:
        try:
            status, detail = check()
        except Exception as exc:
            status, detail = FAIL, f"check crashed: {exc}"
        if status == FAIL:
            failed = True
        print(f"[{status:4}] {name:16} {detail}")
    print("-" * 60)
    print("FAIL: fix the items above." if failed else "All required checks passed. Try: make demo")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
