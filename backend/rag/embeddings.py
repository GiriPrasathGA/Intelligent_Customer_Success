"""
novaTech RAG — Embeddings

Nexus embedding model wrapper using OpenAI-compatible interface.
All embedding calls go through this module — model configured centrally.
"""

from functools import lru_cache
from typing import List

from langchain_openai import OpenAIEmbeddings

from backend.config.config import settings


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """
    Return a cached OpenAIEmbeddings instance pointing at Nexus API.
    Model name is read from central config — never hardcoded here.
    """
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_key=settings.nexus_api_key,
        openai_api_base=settings.nexus_base_url,
        # Dimensions for nova text-embedding-3 (OpenAI compatible)
        dimensions=1536,
        # Batch size for embedding requests
        chunk_size=500,
    )


from backend.utils.retry import async_retry


@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts and return their vector representations."""
    embeddings = get_embeddings()
    return await embeddings.aembed_documents(texts)


@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def embed_query(query: str) -> List[float]:
    """Embed a single query string."""
    embeddings = get_embeddings()
    return await embeddings.aembed_query(query)

