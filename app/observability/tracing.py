"""Langfuse wrapper with a guaranteed-non-blocking local fallback.

Langfuse is maintainer observability; the decision ledger is the product-facing
audit trail. Any Langfuse failure must never break a run, so every call is
wrapped and degrades to logging.

Tracing follows Langfuse instrumentation best practices:
- Descriptive span/generation names and nested hierarchy
- LLM calls recorded as ``generation`` observations with model + token usage
- ``session_id`` groups all traces for one screening run
- Resume/JD bodies and PII are scrubbed before export to Langfuse
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from typing import Any, Protocol

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.redaction import scrub_pii_data

log = get_logger(__name__)

_VERIFIED_CREDENTIALS: set[tuple[str, str, str]] = set()

_MAX_TRACE_OUTPUT_CHARS = 2000
_MAX_TRACE_MESSAGE_CHARS = 500


class _Observation(Protocol):
    def update(self, **kwargs: Any) -> Any: ...

    @property
    def trace_id(self) -> str | None: ...

    @property
    def observation_id(self) -> str | None: ...


class _NoopObservation:
    trace_id: str | None = None
    observation_id: str | None = None

    def update(self, **kwargs: Any) -> _NoopObservation:
        return self


def _sha256_short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def sanitize_trace_messages(messages: list[dict]) -> list[dict]:
    """Redact PII and truncate long document bodies before sending to Langfuse."""
    sanitized = scrub_pii_data(messages)
    result: list[dict] = []
    for msg in sanitized:
        if not isinstance(msg, dict):
            result.append(msg)
            continue
        original_content = msg.get("content", "")
        content = original_content
        if isinstance(content, str) and len(content) > _MAX_TRACE_MESSAGE_CHARS:
            content = (
                f"[truncated {len(original_content)} chars, hash={_sha256_short(original_content)}]"
            )
        result.append({**msg, "content": content})
    return result


def sanitize_trace_output(text: str) -> str:
    scrubbed = scrub_pii_data(text)
    if not isinstance(scrubbed, str):
        scrubbed = str(scrubbed)
    if len(scrubbed) > _MAX_TRACE_OUTPUT_CHARS:
        return (
            f"{scrubbed[:_MAX_TRACE_OUTPUT_CHARS]}..."
            f" [truncated, hash={_sha256_short(text)}]"
        )
    return scrubbed


def langfuse_credentials_verified(settings: Settings) -> bool:
    """Return whether Langfuse keys were verified for the current settings."""
    if not settings.langfuse_configured:
        return False
    cache_key = (
        settings.langfuse_public_key or "",
        settings.langfuse_secret_key or "",
        settings.langfuse_host,
    )
    return cache_key in _VERIFIED_CREDENTIALS


def _verify_credentials(settings: Settings) -> bool:
    """Ping Langfuse once per process; surfaces region/key mismatches early."""
    cache_key = (
        settings.langfuse_public_key or "",
        settings.langfuse_secret_key or "",
        settings.langfuse_host,
    )
    if cache_key in _VERIFIED_CREDENTIALS:
        return True

    import httpx

    try:
        response = httpx.get(
            f"{settings.langfuse_host.rstrip('/')}/api/public/projects",
            auth=(settings.langfuse_public_key, settings.langfuse_secret_key),
            timeout=10.0,
        )
    except Exception as exc:
        log.error("Langfuse credential check failed for %s: %s", settings.langfuse_host, exc)
        return False

    if response.status_code != 200:
        log.error(
            "Langfuse rejected credentials (HTTP %s) for %s. "
            "LANGFUSE_HOST must match the region where the project was created "
            "(EU: https://cloud.langfuse.com, US: https://us.cloud.langfuse.com, "
            "JP: https://jp.cloud.langfuse.com). Response: %s",
            response.status_code,
            settings.langfuse_host,
            response.text[:200],
        )
        return False

    _VERIFIED_CREDENTIALS.add(cache_key)
    log.info("Langfuse credentials verified for %s", settings.langfuse_host)
    return True


class Tracer:
    def __init__(self, settings: Settings):
        self.enabled = False
        self._client = None
        self._settings = settings
        self.last_trace_id: str | None = None
        if not settings.langfuse_configured:
            return
        if not _verify_credentials(settings):
            return
        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                environment=settings.demo_mode,
            )
            self.enabled = True
        except Exception as exc:  # never block the workflow on observability
            log.warning("Langfuse unavailable, using local fallback: %s", exc)

    def current_trace_id(self) -> str | None:
        return self.last_trace_id

    def trace_url(self, trace_id: str | None = None) -> str | None:
        tid = trace_id or self.last_trace_id
        if not self.enabled or not tid:
            return None
        return f"{self._settings.langfuse_host.rstrip('/')}/trace/{tid}"

    def _remember_trace_id(self, observation: Any) -> None:
        trace_id = getattr(observation, "trace_id", None)
        if trace_id:
            self.last_trace_id = str(trace_id)

    def _run_tags(
        self,
        mode: str,
        *,
        provider: str | None = None,
        eval_suite: str | None = None,
    ) -> list[str]:
        tags = ["screening", f"mode:{mode}"]
        if provider:
            tags.append(f"provider:{provider}")
        if eval_suite:
            tags.append(f"eval:{eval_suite}")
        return tags

    @contextmanager
    def run(
        self,
        run_id: str,
        mode: str,
        *,
        resume_count: int = 0,
        provider: str | None = None,
        model_name: str | None = None,
        eval_suite: str | None = None,
    ):
        """Top-level trace for a screening run with session grouping and tags."""
        if not self.enabled:
            yield _NoopObservation()
            return
        try:
            from langfuse import propagate_attributes

            trace_input = {
                "run_id": run_id,
                "mode": mode,
                "resume_count": resume_count,
            }
            if provider:
                trace_input["provider"] = provider
            if model_name:
                trace_input["model_name"] = model_name
            if eval_suite:
                trace_input["eval_suite"] = eval_suite

            with propagate_attributes(
                session_id=run_id,
                tags=self._run_tags(mode, provider=provider, eval_suite=eval_suite),
                metadata={"feature": "candidate_screening", "mode": mode},
            ):
                with self._client.start_as_current_observation(
                    as_type="span",
                    name="screening_run",
                    input=trace_input,
                ) as root:
                    self._remember_trace_id(root)
                    try:
                        yield root
                    except Exception as exc:
                        root.update(level="ERROR", status_message=str(exc))
                        raise
        except Exception as exc:
            log.warning("Langfuse run trace failed: %s", exc)
            yield _NoopObservation()

    @contextmanager
    def candidate_scope(
        self,
        run_id: str,
        slug: str,
        *,
        mode: str,
        red_team: bool = False,
    ):
        """Re-apply session/tags inside parallel candidate branches."""
        if not self.enabled:
            yield _NoopObservation()
            return
        tags = [f"candidate:{slug}"]
        if red_team:
            tags.append("red_team")
        try:
            from langfuse import propagate_attributes

            with propagate_attributes(session_id=run_id, tags=tags):
                with self._client.start_as_current_observation(
                    as_type="span",
                    name="process_candidate",
                    input={"run_id": run_id, "slug": slug, "mode": mode},
                ) as span:
                    self._remember_trace_id(span)
                    yield span
        except Exception as exc:
            log.warning("Langfuse candidate scope failed: %s", exc)
            yield _NoopObservation()

    @contextmanager
    def span(
        self,
        name: str,
        metadata: dict | None = None,
        *,
        input: Any = None,
    ):
        if not self.enabled:
            yield _NoopObservation()
            return
        cm = None
        entered = None
        try:
            cm = self._client.start_as_current_observation(
                as_type="span",
                name=name,
                input=input if input is not None else metadata,
                metadata=metadata,
            )
            entered = cm.__enter__()
            self._remember_trace_id(entered)
        except Exception as exc:
            log.warning("Langfuse span '%s' failed: %s", name, exc)
            cm = None
            yield _NoopObservation()
            return
        try:
            yield entered
        finally:
            if cm is not None:
                try:
                    cm.__exit__(None, None, None)
                except Exception as exc:
                    log.warning("Langfuse span close failed: %s", exc)

    @contextmanager
    def generation(
        self,
        name: str,
        *,
        model: str,
        messages: list[dict],
        metadata: dict | None = None,
        temperature: float | None = None,
    ):
        """Record an LLM call as a Langfuse generation with redacted I/O."""
        if not self.enabled:
            yield _NoopObservation()
            return
        gen_meta = dict(metadata or {})
        if temperature is not None:
            gen_meta["temperature"] = temperature
        cm = None
        entered = None
        try:
            cm = self._client.start_as_current_observation(
                as_type="generation",
                name=name,
                model=model,
                input=sanitize_trace_messages(messages),
                metadata=gen_meta or None,
            )
            entered = cm.__enter__()
            self._remember_trace_id(entered)
        except Exception as exc:
            log.warning("Langfuse generation '%s' failed: %s", name, exc)
            yield _NoopObservation()
            return
        try:
            yield entered
        finally:
            if cm is not None:
                try:
                    cm.__exit__(None, None, None)
                except Exception as exc:
                    log.warning("Langfuse generation close failed: %s", exc)

    def span_event(self, name: str, metadata: dict | None = None) -> None:
        """Short-lived nested span for repair/validation milestones."""
        if not self.enabled:
            return
        try:
            with self._client.start_as_current_observation(
                as_type="span",
                name=name,
                metadata=metadata,
            ) as event:
                self._remember_trace_id(event)
        except Exception as exc:
            log.warning("Langfuse event '%s' failed: %s", name, exc)

    def score(
        self,
        name: str,
        value: float | int,
        *,
        trace_id: str | None = None,
        comment: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        try:
            self._client.create_score(
                name=name,
                value=float(value),
                trace_id=trace_id or self.last_trace_id,
                comment=comment,
            )
        except Exception as exc:
            log.warning("Langfuse score '%s' failed: %s", name, exc)

    def flush(self) -> None:
        if self.enabled:
            try:
                self._client.flush()
            except Exception as exc:
                log.warning("Langfuse flush failed: %s", exc)
