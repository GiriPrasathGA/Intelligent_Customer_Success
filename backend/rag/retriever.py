"""
novaTech RAG — Retriever

Combines embedding and Qdrant search to retrieve relevant document chunks.
Supports category filtering for targeted retrieval by agent type.
"""

import logging
from typing import Any, Optional

from backend.config.settings import RAG_TOP_K, RAG_SCORE_THRESHOLD
from backend.rag.embeddings import get_embeddings, embed_query
from backend.rag.qdrant_db import get_qdrant_client, similarity_search

logger = logging.getLogger(__name__)

# Category mapping for each agent type
AGENT_CATEGORY_MAP = {
    "product_agent": "products",
    "order_agent": "shipping",
    "billing_agent": "payments",
    "warranty_agent": "warranty",
    "account_agent": "account",
    "support_agent": "support",
    "human_agent": None,           # search all categories
    "supervisor": None,            # search all categories
}


async def retrieve_context(
    query: str,
    agent_type: Optional[str] = None,
    top_k: int = RAG_TOP_K,
    score_threshold: float = RAG_SCORE_THRESHOLD,
) -> list[dict[str, Any]]:
    """
    Retrieve relevant document chunks for a query.

    Args:
        query: User's question or message.
        agent_type: Agent routing this query (used for category filter).
        top_k: Number of chunks to retrieve.
        score_threshold: Minimum similarity score.

    Returns:
        List of dicts with content, score, and metadata.
    """
    try:
        # Embed the query
        query_vector = await embed_query(query)

        # Determine category filter based on agent type
        category_filter = None
        if agent_type and agent_type in AGENT_CATEGORY_MAP:
            category_filter = AGENT_CATEGORY_MAP[agent_type]

        client = get_qdrant_client()

        # Try category-filtered search first
        results = similarity_search(
            client=client,
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            category_filter=category_filter,
        )

        # If category filter yields too few results, fall back to global search
        if len(results) < 2 and category_filter:
            logger.debug("Category filter yielded few results, falling back to global search")
            results = similarity_search(
                client=client,
                query_vector=query_vector,
                top_k=top_k,
                score_threshold=score_threshold,
                category_filter=None,
            )

        logger.info(
            "Retrieved %d chunks for query: '%s' (agent: %s)",
            len(results), query[:50], agent_type
        )
        return results

    except Exception as e:
        logger.error("RAG retrieval error: %s", str(e))
        return []


def format_context(retrieved_chunks: list[dict[str, Any]]) -> str:
    """
    Format retrieved chunks into a context string for the LLM prompt.
    Includes source citations.
    """
    if not retrieved_chunks:
        return ""

    context_parts = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        doc_name = chunk.get("document_name", "NovaCart Knowledge Base")
        category = chunk.get("category", "general")
        score = chunk.get("score", 0.0)
        content = chunk.get("content", "")
        page = chunk.get("page")
        page_info = f" | Page: {page}" if page is not None else ""

        context_parts.append(
            f"[Source {i}: {doc_name}{page_info} | Category: {category} | Relevance: {score:.2f}]\n{content}"
        )

    return "\n\n---\n\n".join(context_parts)


def extract_sources(retrieved_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract unique source references with retrieved snippet content for inspector/highlighting."""
    seen = set()
    sources = []

    for chunk in retrieved_chunks:
        doc_name = chunk.get("document_name", "")
        if not doc_name:
            continue

        page = chunk.get("page")
        key = f"{doc_name}:{page}" if page is not None else doc_name

        if key not in seen:
            seen.add(key)
            sources.append({
                "document": doc_name,
                "category": chunk.get("category", "general"),
                "relevance_score": round(chunk.get("score", 0.0), 3),
                "page": page,
                "total_pages": chunk.get("total_pages"),
                "content": chunk.get("content", ""),
                "chunk_index": chunk.get("chunk_index", 0),
            })

    return sources
