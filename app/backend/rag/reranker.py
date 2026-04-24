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

logger = logging.getLogger(__name__)

# Module-level model cache — loaded once, reused across calls
_cross_encoder: "CrossEncoder | None" = None


def _get_cross_encoder() -> "CrossEncoder":
    """Lazily load and cache the cross-encoder model."""
    global _cross_encoder
    if _cross_encoder is None:
        from backend.config import RERANKER_MODEL

        from sentence_transformers import CrossEncoder

        logger.info("Loading cross-encoder model: %s", RERANKER_MODEL)
        _cross_encoder = CrossEncoder(RERANKER_MODEL)
        logger.info("Cross-encoder model loaded successfully")
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
    scored = [
        {**c, "cross_encoder_score": float(scores[i])}
        for i, c in enumerate(chunks)
    ]
    scored.sort(key=lambda x: x["cross_encoder_score"], reverse=True)

    return scored[:top_k]
