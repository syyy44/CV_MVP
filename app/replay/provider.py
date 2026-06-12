"""Replay-mode provider.

Returns captured fixture outputs instead of calling a live model. Everything
downstream — JSON parsing, Pydantic validation, evidence resolution,
deterministic scoring, ledger, storage, UI — runs exactly the same contracts
as live mode. This is deterministic replay, not a faked demo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.errors import ReplayFixtureMissingError
from app.llm.client import CompletionResult
from app.locale import zh_CN as msg

REPLAY_MODEL_NAME = "replay-fixture"


class ReplayProvider:
    name = "replay"

    def __init__(self, settings: Settings):
        self._search_dirs = [
            settings.fixtures_dir / "demo" / "llm_outputs",
            settings.fixtures_dir / "eval" / "llm_outputs",
        ]

    def _resolve(self, fixture_key: str) -> Path:
        for base in self._search_dirs:
            path = base / f"{fixture_key}.json"
            if path.exists():
                return path
        searched = ", ".join(str(d) for d in self._search_dirs)
        raise ReplayFixtureMissingError(msg.replay_fixture_missing(fixture_key, searched))

    def complete(
        self,
        messages: list[dict],
        *,
        fixture_key: str | None = None,
        temperature: float | None = None,
        response_schema: dict[str, Any] | None = None,
        response_schema_name: str | None = None,
    ) -> CompletionResult:
        if not fixture_key:
            raise ReplayFixtureMissingError(msg.replay_without_fixture_key())
        text = self._resolve(fixture_key).read_text(encoding="utf-8")
        return CompletionResult(text=text, model=REPLAY_MODEL_NAME)
