from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.models.contracts import JobRubric
from app.models.drafts import CandidateProfileDraft, InterviewPackDraft, ScoreAnalysisDraft

ROOT = Path(__file__).resolve().parent.parent


def _validate(path: Path, schema) -> list[str]:
    try:
        schema.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        return [f"{path}: {exc}"]
    return []


def main() -> int:
    errors: list[str] = []
    demo_outputs = ROOT / "fixtures" / "demo" / "llm_outputs"
    eval_outputs = ROOT / "fixtures" / "eval" / "llm_outputs"

    errors.extend(_validate(demo_outputs / "rubric.json", JobRubric))
    for base in [demo_outputs, eval_outputs]:
        if not base.exists():
            continue
        for candidate_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            errors.extend(_validate(candidate_dir / "profile.json", CandidateProfileDraft))
            errors.extend(_validate(candidate_dir / "score.json", ScoreAnalysisDraft))
            pack = candidate_dir / "interview_pack.json"
            if pack.exists():
                errors.extend(_validate(pack, InterviewPackDraft))

    if errors:
        print("Fixture schema drift detected:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("All replay/eval fixtures validate against current schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
