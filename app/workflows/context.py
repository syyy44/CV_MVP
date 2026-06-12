from __future__ import annotations

import threading
from dataclasses import dataclass, field

from app.core.config import Settings
from app.ledger.events import LedgerRecorder
from app.models.contracts import RunMetrics
from app.observability.tracing import Tracer


class MetricsCollector:
    """Thread-safe: candidate branches run in parallel under LangGraph Send."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.llm_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def record_call(self, input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            self.llm_calls += 1
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens

    def to_run_metrics(self, settings: Settings, duration_s: float) -> RunMetrics:
        cost = (
            self.input_tokens / 1000 * settings.cost_input_per_1k
            + self.output_tokens / 1000 * settings.cost_output_per_1k
        )
        return RunMetrics(
            llm_calls=self.llm_calls,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost_estimate_usd=round(cost, 6),
            duration_s=round(duration_s, 2),
        )


@dataclass
class WorkflowContext:
    run_id: str
    mode: str
    settings: Settings
    provider: object
    ledger: LedgerRecorder
    tracer: Tracer
    metrics: MetricsCollector = field(default_factory=MetricsCollector)
    red_team_slugs: frozenset[str] = frozenset()
