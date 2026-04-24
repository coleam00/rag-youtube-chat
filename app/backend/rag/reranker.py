"""Cross-encoder reranker for post-retrieval re-ranking.

Re-scores RRF candidates with a query-document cross-encoder model trained
on MS MARCO query-document relevance. Better at distinguishing explicit
recommendations from passing mentions than RRF score alone.

Wraps the blocking torch call in asyncio.to_thread to avoid blocking the
async event loop. Model is lazy-loaded on first call and cached in a
module-level variable.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

# Module-level model cache — loaded once, reused across calls
_cross_encoder: CrossEncoder | None = None  # type: ignore[valid-type]


def _get_cross_encoder() -> CrossEncoder:  # type: ignore[valid-type]
    """Lazily load and cache the cross-encoder model."""
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        from backend.config import RERANKER_MODEL

        try:
            logger.info("Loading cross-encoder model: %s", RERANKER_MODEL)
            _cross_encoder = CrossEncoder(RERANKER_MODEL)
            logger.info("Cross-encoder model loaded successfully")
        except Exception as exc:
            logger.error("Failed to load cross-encoder model %s: %s", RERANKER_MODEL, exc)
            raise RuntimeError(f"Cross-encoder model loading failed: {exc}") from exc
    return _cross_encoder


async def rerank_chunks(
    query: str,
    chunks: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """
    Re-rank chunks using a cross-encoder model.

    Args:
        query: Original user query string.
        chunks: List of chunk dicts to re-rank. Each must have a ``content`` key.
        top_k: Maximum number of chunks to return after re-ranking.

    Returns:
        List of up to ``top_k`` chunks, sorted by cross-encoder score descending.
        Each returned chunk has an added ``cross_encoder_score`` field.
        Returns [] when input ``chunks`` is empty.
    """
    if not chunks:
        return []

    if top_k <= 0:
        return []

    # Build (query, document) pairs for the cross-encoder
    pairs: list[tuple[str, str]] = [(query, c.get("content", "")) for c in chunks]

    def _score() -> list[float]:
        model = _get_cross_encoder()
        return model.predict(pairs)

    # Run the blocking torch predict in a thread pool to avoid blocking the event loop
    scores: list[float] = await asyncio.to_thread(_score)

    # Attach score to each chunk and sort by score descending
    scored = [{**c, "cross_encoder_score": float(scores[i])} for i, c in enumerate(chunks)]
    scored.sort(key=lambda x: x["cross_encoder_score"], reverse=True)

    return scored[:top_k]
