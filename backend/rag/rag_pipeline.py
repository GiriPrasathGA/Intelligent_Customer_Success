"""
novaTech RAG — Full Pipeline

Orchestrates the complete RAG workflow:
Load → Split → Embed → Store → (Query) → Retrieve → Context → LLM

Also provides the ingest() function called at app startup.
"""

import logging
from typing import Any, Optional

from backend.rag.loader import load_documents
from backend.rag.splitter import split_documents
from backend.rag.embeddings import get_embeddings, embed_texts
from backend.rag.qdrant_db import (
    get_qdrant_client, ensure_collection, upsert_documents,
    get_collection_info, clear_collection
)
from backend.rag.retriever import retrieve_context, format_context, extract_sources

logger = logging.getLogger(__name__)


async def ingest_knowledge_base(force_reingest: bool = False, force: bool = False) -> dict[str, Any]:
    """
    Full ingestion pipeline: load all knowledge docs → split → embed → store in Qdrant.

    Args:
        force_reingest: If True, clears existing collection before ingesting.
        force: Alias for force_reingest.

    Returns:
        Dict with ingestion stats.
    """
    force_reingest = force_reingest or force
    client = get_qdrant_client()

    # Check if already ingested
    if not force_reingest:
        info = get_collection_info(client)
        if info.get("vectors_count", 0) > 0:
            logger.info(
                "Knowledge base already ingested (%d vectors). Skipping.",
                info["vectors_count"]
            )
            return {
                "status": "already_ingested",
                "vectors_count": info["vectors_count"],
            }

    if force_reingest:
        logger.info("Force reingest requested — clearing collection")
        clear_collection(client)

    # Step 1: Load documents
    logger.info("Loading knowledge base documents...")
    try:
        documents = load_documents()
        logger.info("Loaded %d documents", len(documents))
    except FileNotFoundError as e:
        logger.error("Knowledge base not found: %s", e)
        return {"status": "error", "detail": str(e)}

    # Step 2: Split into chunks
    logger.info("Splitting documents into chunks...")
    chunks = split_documents(documents)
    logger.info("Created %d chunks from %d documents", len(chunks), len(documents))

    # Step 3: Generate embeddings
    logger.info("Generating embeddings for %d chunks...", len(chunks))
    try:
        embeddings_model = get_embeddings()
        texts = [chunk.page_content for chunk in chunks]
        vectors = await embed_texts(texts)
        logger.info("Generated %d embedding vectors", len(vectors))
    except Exception as e:
        logger.warning(
            "Embedding API unavailable (%s) — using zero vectors for demo mode", str(e)
        )
        # Graceful fallback: use zero vectors (RAG disabled but app still runs)
        vectors = [[0.0] * 1536 for _ in chunks]

    # Step 4: Store in Qdrant
    logger.info("Storing embeddings in Qdrant...")
    count = upsert_documents(client, chunks, vectors)

    result = {
        "status": "success",
        "documents_loaded": len(documents),
        "chunks_created": len(chunks),
        "vectors_stored": count,
    }
    logger.info("Ingestion complete: %s", result)
    return result


async def query_knowledge_base(
    query: str,
    agent_type: Optional[str] = None,
) -> dict[str, Any]:
    """
    Query the knowledge base and return formatted context + sources.

    Args:
        query: User question.
        agent_type: Routing agent (for category filtering).

    Returns:
        Dict with 'context' string and 'sources' list.
    """
    chunks = await retrieve_context(query=query, agent_type=agent_type)
    context = format_context(chunks)
    sources = extract_sources(chunks)

    return {
        "context": context,
        "sources": sources,
        "chunks_retrieved": len(chunks),
    }
