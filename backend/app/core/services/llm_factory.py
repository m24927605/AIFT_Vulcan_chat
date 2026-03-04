import logging

from app.core.services.llm_client import LLMClient
from app.core.services.openai_client import OpenAIClient
from app.core.services.anthropic_client import AnthropicClient
from app.core.services.fallback_client import FallbackLLMClient

logger = logging.getLogger(__name__)


def _get_api_key(provider: str, settings) -> str:
    if provider == "openai":
        return settings.openai_api_key
    if provider == "anthropic":
        return settings.anthropic_api_key
    return ""


def _build(provider: str, settings) -> LLMClient:
    if provider == "openai":
        return OpenAIClient(api_key=settings.openai_api_key, model=settings.openai_model)
    if provider == "anthropic":
        return AnthropicClient(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
    raise ValueError(f"Unknown LLM provider: {provider}")


def create_llm_client(settings) -> LLMClient:
    primary = _build(settings.primary_llm, settings)

    fallback_provider = settings.fallback_llm
    if fallback_provider and _get_api_key(fallback_provider, settings):
        fallback = _build(fallback_provider, settings)
        return FallbackLLMClient(primary=primary, fallback=fallback)

    if fallback_provider and not _get_api_key(fallback_provider, settings):
        logger.warning(
            "Fallback LLM '%s' configured but API key is empty — fallback disabled.",
            fallback_provider,
        )

    return primary
