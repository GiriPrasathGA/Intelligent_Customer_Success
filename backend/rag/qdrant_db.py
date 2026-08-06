"""
novaTech RAG — Qdrant Database

Qdrant client setup, collection management, and document operations.
Supports both local (embedded) mode and remote server mode.
"""

import os
import uuid
import logging
from typing import Any, Optional

from langchain_core.documents import Document
from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
)

from backend.config.config import settings
from backend.config.settings import (
    QDRANT_COLLECTION_NAME, EMBEDDING_DIMENSION, QDRANT_DISTANCE_METRIC
)

logger = logging.getLogger(__name__)


_qdrant_client_instance: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    """
    Create and return a Qdrant client (singleton).
    Uses local embedded mode (path) or remote (url), based on settings.
    Handles stale lock files and provides fallback to in-memory mode.
    """
    global _qdrant_client_instance
    if _qdrant_client_instance is not None:
        return _qdrant_client_instance

    # 1. Try remote Qdrant first if configured
    if settings.qdrant_url and settings.qdrant_url != "http://localhost:6333":
        try:
            client = QdrantClient(url=settings.qdrant_url, timeout=30)
            logger.info("Connected to remote Qdrant at %s", settings.qdrant_url)
            _qdrant_client_instance = client
            return client
        except Exception as err:
            logger.warning("Remote Qdrant unavailable (%s), falling back to local mode", err)

    # 2. Local embedded mode with lock recovery
    try:
        client = QdrantClient(path=settings.qdrant_storage_path)
        logger.info("Qdrant client initialized (path: %s)", settings.qdrant_storage_path)
        _qdrant_client_instance = client
        return client
    except Exception as err:
        logger.warning("Local Qdrant initialization error: %s", err)
        
        # Check and attempt to remove stale lock file if present
        storage_path = settings.qdrant_storage_path
        lock_file = os.path.join(storage_path, ".lock")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                logger.info("Removed stale Qdrant lock file: %s", lock_file)
                client = QdrantClient(path=storage_path)
                _qdrant_client_instance = client
                return client
            except Exception as lock_err:
                logger.warning("Could not remove lock file or re-init Qdrant: %s", lock_err)

        # 3. Fallback to in-memory Qdrant instance if disk storage cannot be acquired
        logger.warning("Falling back to in-memory Qdrant instance to prevent application crash")
        _qdrant_client_instance = QdrantClient(location=":memory:")
        return _qdrant_client_instance


def ensure_collection(client: QdrantClient, collection_name: str = QDRANT_COLLECTION_NAME) -> None:
    """Create the vector collection if it does not exist."""
    existing = [c.name for c in client.get_collections().collections]

    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Created Qdrant collection: %s", collection_name)
    else:
        logger.info("Qdrant collection exists: %s", collection_name)


from backend.utils.retry import sync_retry


@sync_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
def upsert_documents(
    client: QdrantClient,
    documents: list[Document],
    embeddings: list[list[float]],
    collection_name: str = QDRANT_COLLECTION_NAME,
) -> int:
    """
    Upsert document chunks with their embeddings into Qdrant.
    Returns number of points upserted.
    """
    ensure_collection(client, collection_name)

    points = []
    for doc, vector in zip(documents, embeddings):
        point_id = str(uuid.uuid4())
        payload = {
            "content": doc.page_content,
            "document_name": doc.metadata.get("document_name", ""),
            "category": doc.metadata.get("category", "general"),
            "department": doc.metadata.get("department", ""),
            "source": doc.metadata.get("source", ""),
            "version": doc.metadata.get("version", ""),
            "chunk_index": doc.metadata.get("chunk_index", 0),
            "total_chunks": doc.metadata.get("total_chunks", 1),
            "page": doc.metadata.get("page"),
            "total_pages": doc.metadata.get("total_pages"),
            "file_type": doc.metadata.get("file_type", "pdf"),
        }

        points.append(
            PointStruct(id=point_id, vector=vector, payload=payload)
        )

    # Batch upsert (Qdrant handles large batches efficiently)
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(collection_name=collection_name, points=batch)

    logger.info("Upserted %d points into collection %s", len(points), collection_name)
    return len(points)


@sync_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
def similarity_search(
    client: QdrantClient,
    query_vector: list[float],
    top_k: int = 5,
    score_threshold: float = 0.35,
    collection_name: str = QDRANT_COLLECTION_NAME,
    category_filter: Optional[str] = None,
) -> list[dict[str, Any]]:

    """
    Perform similarity search in Qdrant.
    Returns ranked list of matching documents with scores.
    """
    ensure_collection(client, collection_name)
    search_filter = None
    if category_filter:
        search_filter = Filter(
            must=[FieldCondition(key="category", match=MatchValue(value=category_filter))]
        )

    if hasattr(client, "query_points"):
        res = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=search_filter,
            with_payload=True,
        )
        results = res.points
    else:
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=search_filter,
            with_payload=True,
        )

    return [
        {
            "content": r.payload.get("content", ""),
            "score": r.score,
            "document_name": r.payload.get("document_name", ""),
            "category": r.payload.get("category", ""),
            "department": r.payload.get("department", ""),
            "source": r.payload.get("source", ""),
            "chunk_index": r.payload.get("chunk_index", 0),
            "page": r.payload.get("page"),
            "total_pages": r.payload.get("total_pages"),
            "file_type": r.payload.get("file_type", "pdf"),
        }
        for r in results
    ]


def get_collection_info(
    client: QdrantClient,
    collection_name: str = QDRANT_COLLECTION_NAME,
) -> dict[str, Any]:
    """Return collection statistics."""
    try:
        info = client.get_collection(collection_name)
        return {
            "name": collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": str(info.status),
        }
    except Exception:
        return {"name": collection_name, "status": "not_found"}


def clear_collection(
    client: QdrantClient,
    collection_name: str = QDRANT_COLLECTION_NAME,
) -> None:
    """Delete and recreate a collection (clear all data)."""
    try:
        client.delete_collection(collection_name)
        logger.info("Deleted collection: %s", collection_name)
    except Exception:
        pass
    ensure_collection(client, collection_name)
