from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from app.locale import zh_CN as msg

TModel = TypeVar("TModel", bound=BaseModel)

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}(?!\w)"
)
ADDRESS_RE = re.compile(
    r"\b(?:address|home address|residence)\s*[:：]\s*[^,\n;]+(?:[,;][^\n;]+)?",
    re.IGNORECASE,
)


def scrub_pii_text(text: str) -> str:
    text = EMAIL_RE.sub(msg.EMAIL_REDACTED, text)
    text = PHONE_RE.sub(msg.PHONE_REDACTED, text)
    text = ADDRESS_RE.sub(msg.ADDRESS_REDACTED, text)
    return text


def scrub_pii_data(value: Any) -> Any:
    if isinstance(value, str):
        return scrub_pii_text(value)
    if isinstance(value, list):
        return [scrub_pii_data(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub_pii_data(item) for key, item in value.items()}
    return value


def scrub_pii_model(model: TModel, schema: type[TModel]) -> TModel:
    """Scrub recursively and re-validate so exports stay schema-conformant."""
    payload = model.model_dump(mode="json")
    scrubbed = scrub_pii_data(json.loads(json.dumps(payload)))
    return schema.model_validate(scrubbed)
