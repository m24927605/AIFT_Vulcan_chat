"""
Shared secure answer pipeline used by both chat and deep-analysis endpoints.

Covers: refusal gate, guarded generation, and verification.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.agents.executor import ExecutorAgent
from app.core.agents.verifier import VerificationResult, VerifierAgent
from app.core.security import guard_model_output

_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

_REFUSAL_EN = (
    "I'm unable to retrieve verified up-to-date information for this query "
    "right now. Please try again later."
)
_REFUSAL_ZH = "目前無法取得經過驗證的最新資訊，請稍後再試。"

_SEARCH_FAILED_EN = "Web search returned no results. Unable to retrieve verified information."
_SEARCH_FAILED_ZH = "網路搜尋未回傳任何結果，無法取得經過驗證的資訊。"


def is_cjk_query(message: str) -> bool:
    """Return True if the message contains any CJK Unified Ideograph characters."""
    return bool(_CJK_PATTERN.search(message))


def get_search_failed_message(message: str) -> str:
    """Return a localized search-failed warning matching the user's language."""
    return _SEARCH_FAILED_ZH if is_cjk_query(message) else _SEARCH_FAILED_EN


async def secure_answer_pipeline(
    *,
    message: str,
    needs_search: bool,
    normalized_results: list,
    executor: ExecutorAgent,
    verifier: VerifierAgent,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    """Execute the secured answer path with refusal gate, output guarding, and verification.

    Returns a dict with keys: refused, refusal_message, answer, guarded_chunks, verification.
    """
    # --- Refusal gate ---
    if needs_search and not normalized_results:
        refusal_message = _REFUSAL_ZH if is_cjk_query(message) else _REFUSAL_EN
        return {
            "refused": True,
            "refusal_message": refusal_message,
            "answer": "",
            "guarded_chunks": [],
            "verification": None,
        }

    # --- Guarded generation ---
    guarded_chunks: list[str] = []
    async for chunk in executor.execute(message, normalized_results, history=history):
        guarded = guard_model_output(chunk)
        guarded_chunks.append(guarded)

    answer = "".join(guarded_chunks)

    # --- Verification ---
    verification: VerificationResult | None = None
    if normalized_results:
        verification = await verifier.verify(message, answer, normalized_results)

    return {
        "refused": False,
        "refusal_message": "",
        "answer": answer,
        "guarded_chunks": guarded_chunks,
        "verification": verification,
    }
