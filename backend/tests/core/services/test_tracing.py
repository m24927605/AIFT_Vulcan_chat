import pytest
from unittest.mock import patch, MagicMock
from app.core.services.tracing import TracingService


def test_tracing_service_disabled_when_no_keys():
    tracer = TracingService(public_key="", secret_key="")
    assert tracer.enabled is False


def test_tracing_service_enabled_when_keys_present():
    with patch("langfuse.Langfuse") as MockLangfuse:
        MockLangfuse.return_value = MagicMock()
        tracer = TracingService(public_key="pk-test", secret_key="sk-test")
        assert tracer.enabled is True


def test_get_tracer_returns_singleton():
    from app.core.services.tracing import get_tracer
    t1 = get_tracer()
    t2 = get_tracer()
    assert t1 is t2


def test_trace_llm_call_noop_when_disabled():
    tracer = TracingService(public_key="", secret_key="")
    ctx = tracer.trace_llm_call(name="test", model="gpt-4o", input_text="hi", output_text="hello", temperature=0.3)
    assert ctx is None


def test_trace_llm_call_creates_generation_when_enabled():
    with patch("langfuse.Langfuse") as MockLangfuse:
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_client.trace.return_value = mock_trace
        MockLangfuse.return_value = mock_client
        tracer = TracingService(public_key="pk-test", secret_key="sk-test")
        tracer.trace_llm_call(name="planner", model="gpt-4o", input_text="What is TSMC?", output_text='{"needs_search": true}', temperature=0.1, latency_ms=150.0, tokens_input=50, tokens_output=20, metadata={"agent": "planner"})
        mock_client.trace.assert_called_once()
        mock_trace.generation.assert_called_once()
