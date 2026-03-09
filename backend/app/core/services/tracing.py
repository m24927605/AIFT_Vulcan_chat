"""Lightweight Langfuse tracing wrapper for LLM observability."""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)
_singleton: TracingService | None = None


class TracingService:
    """Wraps Langfuse SDK. No-ops gracefully when keys are missing."""

    def __init__(
        self,
        public_key: str = "",
        secret_key: str = "",
        host: str = "https://cloud.langfuse.com",
    ):
        self._client = None
        if public_key and secret_key:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
                logger.info("Langfuse tracing enabled")
            except Exception:
                logger.warning(
                    "Langfuse init failed; tracing disabled", exc_info=True
                )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def trace_llm_call(
        self,
        *,
        name: str,
        model: str,
        input_text: str,
        output_text: str,
        temperature: float = 0.3,
        latency_ms: float | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any | None:
        if not self._client:
            return None
        try:
            trace = self._client.trace(name=name, metadata=metadata or {})
            trace.generation(
                name=name,
                model=model,
                input=input_text,
                output=output_text,
                model_parameters={"temperature": temperature},
                usage={"input": tokens_input, "output": tokens_output},
                metadata={
                    "latency_ms": latency_ms,
                    **(metadata or {}),
                },
            )
            return trace
        except Exception:
            logger.warning("Langfuse trace failed", exc_info=True)
            return None

    def flush(self) -> None:
        if self._client:
            self._client.flush()


def get_tracer() -> TracingService:
    global _singleton
    if _singleton is None:
        from app.core.config import settings

        _singleton = TracingService(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    return _singleton
