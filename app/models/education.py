"""Education coercion helpers shared by workflow steps and API contracts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.locale import zh_CN as msg

if TYPE_CHECKING:
    from app.models.contracts import EducationItem
    from app.models.drafts import EducationItemDraft


def _parse_highlights(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(h).strip() for h in raw if str(h).strip()]
    if not isinstance(raw, str):
        return []
    text = raw.strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text.replace("'", '"'))
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(h).strip() for h in parsed if str(h).strip()]
    return [text]


def coerce_education_item(item: EducationItemDraft | str | dict) -> EducationItem:
    from app.models.contracts import EducationItem
    from app.models.drafts import EducationItemDraft

    if isinstance(item, EducationItem):
        return item
    if isinstance(item, EducationItemDraft):
        return EducationItem(
            school=item.school,
            degree=item.degree,
            major=item.major,
            start_date=item.start_date,
            end_date=item.end_date,
            gpa=item.gpa,
            highlights=item.highlights,
        )
    if isinstance(item, str):
        text = item.strip()
        if "school:" in text.lower():
            lowered = text.lower()
            school = text[lowered.index("school:") + len("school:") :].split(",", 1)[0].strip()
            degree = ""
            major = ""
            start_date = ""
            end_date = ""
            gpa: str | None = None
            highlights: list[str] = []
            for part in text.split(","):
                segment = part.strip()
                lower = segment.lower()
                if lower.startswith("degree:"):
                    degree = segment.split(":", 1)[1].strip()
                elif lower.startswith("major:"):
                    major = segment.split(":", 1)[1].strip()
                elif lower.startswith("start_date:"):
                    start_date = segment.split(":", 1)[1].strip()
                elif lower.startswith("end_date:"):
                    end_date = segment.split(":", 1)[1].strip()
                elif lower.startswith("gpa:"):
                    raw_gpa = segment.split(":", 1)[1].strip()
                    gpa = None if raw_gpa.upper() in {"NA", "N/A", "NONE", ""} else raw_gpa
                elif lower.startswith("highlights:"):
                    highlights = _parse_highlights(segment.split(":", 1)[1].strip())
            return EducationItem(
                school=school or text,
                degree=degree,
                major=major,
                start_date=start_date,
                end_date=end_date,
                gpa=gpa,
                highlights=highlights,
            )
        return EducationItem(school=text)
    gpa_raw = item.get("gpa")
    gpa = None if gpa_raw in (None, "", "NA", "N/A") else str(gpa_raw)
    return EducationItem(
        school=str(item.get("school") or item.get("institution") or msg.UNKNOWN_SCHOOL),
        degree=str(item.get("degree") or ""),
        major=str(item.get("major") or item.get("field") or ""),
        start_date=str(item.get("start_date") or item.get("start") or ""),
        end_date=str(item.get("end_date") or item.get("end") or item.get("graduation") or ""),
        gpa=gpa,
        highlights=_parse_highlights(item.get("highlights") or []),
    )
