from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.observability.tracing import (
    Tracer,
    langfuse_credentials_verified,
    sanitize_trace_messages,
    sanitize_trace_output,
)


def test_tracer_disabled_when_langfuse_not_configured():
    tracer = Tracer(Settings(enable_langfuse=False))
    assert tracer.enabled is False
    with tracer.run("run-1", "replay") as obs:
        assert obs.update(level="INFO") is obs
    tracer.flush()


def test_sanitize_trace_messages_scrubs_pii():
    messages = [{"role": "user", "content": "Contact candidate@example.com for details"}]
    sanitized = sanitize_trace_messages(messages)
    assert "[邮箱已脱敏]" in sanitized[0]["content"]


def test_sanitize_trace_messages_truncates_long_content():
    long_body = "x" * 600
    messages = [{"role": "user", "content": long_body}]
    sanitized = sanitize_trace_messages(messages)
    assert "truncated 600 chars" in sanitized[0]["content"]


def test_sanitize_trace_output_truncates_large_json():
    payload = '{"items": [' + ",".join(['"a"'] * 500) + "]}"
    sanitized = sanitize_trace_output(payload)
    assert len(sanitized) <= 2100
    assert "truncated" in sanitized


def test_langfuse_credentials_verified_false_when_not_configured():
    assert langfuse_credentials_verified(Settings(enable_langfuse=False)) is False


def test_tracer_run_uses_propagate_attributes_and_records_trace_id():
    from app.observability import tracing as tracing_module

    tracing_module._VERIFIED_CREDENTIALS.clear()
    settings = Settings(
        enable_langfuse=True,
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )
    fake_root = SimpleNamespace(trace_id="trace-abc", update=MagicMock())
    fake_client = MagicMock()
    fake_client.start_as_current_observation.return_value.__enter__.return_value = fake_root
    fake_client.start_as_current_observation.return_value.__exit__.return_value = None

    with patch.object(tracing_module, "_verify_credentials", return_value=True), patch(
        "langfuse.Langfuse", return_value=fake_client
    ), patch("langfuse.propagate_attributes") as propagate:
        propagate.return_value.__enter__.return_value = None
        propagate.return_value.__exit__.return_value = None
        tracer = Tracer(settings)
        assert tracer.enabled is True
        with tracer.run(
            "run-42",
            "live",
            resume_count=2,
            provider="siliconflow",
            model_name="deepseek",
            eval_suite="demo",
        ) as root:
            root.update(output={"status": "completed"})
        assert tracer.last_trace_id == "trace-abc"
        propagate.assert_called_once()
        call_kwargs = propagate.call_args.kwargs
        assert call_kwargs["session_id"] == "run-42"
        assert "mode:live" in call_kwargs["tags"]
        assert "provider:siliconflow" in call_kwargs["tags"]
        assert "eval:demo" in call_kwargs["tags"]


def test_tracer_generation_records_model_and_usage():
    from app.observability import tracing as tracing_module

    tracing_module._VERIFIED_CREDENTIALS.clear()
    settings = Settings(
        enable_langfuse=True,
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )
    fake_gen = SimpleNamespace(trace_id="trace-gen", update=MagicMock())
    fake_client = MagicMock()
    fake_client.start_as_current_observation.return_value.__enter__.return_value = fake_gen
    fake_client.start_as_current_observation.return_value.__exit__.return_value = None

    with patch.object(tracing_module, "_verify_credentials", return_value=True), patch(
        "langfuse.Langfuse", return_value=fake_client
    ):
        tracer = Tracer(settings)

    messages = [{"role": "user", "content": "short prompt"}]
    with tracer.generation(
        "extract_jd_rubric",
        model="qwen-plus",
        messages=messages,
        metadata={"prompt_name": "extract_jd_rubric"},
        temperature=0.2,
    ) as generation:
        generation.update(
            output='{"ok": true}',
            usage_details={"input": 10, "output": 5},
        )

    create_kwargs = fake_client.start_as_current_observation.call_args.kwargs
    assert create_kwargs["as_type"] == "generation"
    assert create_kwargs["name"] == "extract_jd_rubric"
    assert create_kwargs["model"] == "qwen-plus"


def test_tracer_candidate_scope_and_score():
    from app.observability import tracing as tracing_module

    tracing_module._VERIFIED_CREDENTIALS.clear()
    settings = Settings(
        enable_langfuse=True,
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
        langfuse_host="https://jp.cloud.langfuse.com",
    )
    fake_span = SimpleNamespace(trace_id="cand-trace", update=MagicMock())
    fake_client = MagicMock()
    fake_client.start_as_current_observation.return_value.__enter__.return_value = fake_span
    fake_client.start_as_current_observation.return_value.__exit__.return_value = None

    with patch.object(tracing_module, "_verify_credentials", return_value=True), patch(
        "langfuse.Langfuse", return_value=fake_client
    ), patch("langfuse.propagate_attributes") as propagate:
        propagate.return_value.__enter__.return_value = None
        propagate.return_value.__exit__.return_value = None
        tracer = Tracer(settings)

        with tracer.candidate_scope("run-1", "strong_fit", mode="live", red_team=True):
            pass

        tracer.score("overall_score", 89, trace_id="cand-trace", comment="completed")
        assert tracer.trace_url("cand-trace") == (
            "https://jp.cloud.langfuse.com/trace/cand-trace"
        )

    fake_client.create_score.assert_called_once_with(
        name="overall_score",
        value=89.0,
        trace_id="cand-trace",
        comment="completed",
    )


def test_tracer_span_event():
    from app.observability import tracing as tracing_module

    tracing_module._VERIFIED_CREDENTIALS.clear()
    settings = Settings(
        enable_langfuse=True,
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )
    fake_client = MagicMock()
    fake_event = SimpleNamespace(trace_id="evt-trace")
    fake_client.start_as_current_observation.return_value.__enter__.return_value = fake_event
    fake_client.start_as_current_observation.return_value.__exit__.return_value = None

    with patch.object(tracing_module, "_verify_credentials", return_value=True), patch(
        "langfuse.Langfuse", return_value=fake_client
    ):
        tracer = Tracer(settings)
        tracer.span_event("repair_attempt", {"attempt": 2})

    fake_client.start_as_current_observation.assert_called_with(
        as_type="span",
        name="repair_attempt",
        metadata={"attempt": 2},
    )
