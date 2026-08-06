"""
novaTech RAG — Text Splitter

Splits documents into chunks for embedding and retrieval.
Preserves metadata across all chunks.
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config.settings import RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP


def split_documents(documents: list[Document]) -> list[Document]:
    """
    Split documents into chunks using RecursiveCharacterTextSplitter.
    Each chunk retains the parent document's metadata, plus chunk index.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=RAG_CHUNK_SIZE,
        chunk_overlap=RAG_CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks: list[Document] = []

    for doc in documents:
        chunks = splitter.split_documents([doc])
        # Add chunk index metadata for traceability
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)
            chunk.metadata["parent_document"] = doc.metadata.get("document_name", "unknown")
        all_chunks.extend(chunks)

    return all_chunks
