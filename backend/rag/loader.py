"""
NovaCart RAG — Document Loader

Loads all knowledge base documents (TXT and PDF formats) with rich metadata.
"""

import os
import logging
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document

from backend.config.settings import KNOWLEDGE_BASE_DIR, KNOWLEDGE_DOCUMENT_CATEGORIES

logger = logging.getLogger(__name__)


def infer_category(filename: str, header_text: str = "") -> str:
    """Infer document category from mapping, header metadata, or filename."""
    # 1. Exact match in settings
    if filename in KNOWLEDGE_DOCUMENT_CATEGORIES:
        return KNOWLEDGE_DOCUMENT_CATEGORIES[filename]

    # 2. Header parsing
    for line in header_text.split("\n")[:8]:
        if "Category:" in line:
            parts = line.split("|")
            for part in parts:
                part = part.strip()
                if part.startswith("Category:"):
                    return part.replace("Category:", "").strip().lower()

    # 3. Keyword heuristic from filename
    fname = filename.lower()
    if any(k in fname for k in ["account", "profile", "login", "kyc"]):
        return "account"
    if any(k in fname for k in ["product", "spec", "catalog", "buying"]):
        return "products"
    if any(k in fname for k in ["shipping", "order", "delivery", "logistics"]):
        return "shipping"
    if any(k in fname for k in ["return", "refund", "replacement"]):
        return "returns"
    if any(k in fname for k in ["warranty", "repair", "care"]):
        return "warranty"
    if any(k in fname for k in ["payment", "emi", "pricing", "discount", "finance", "billing"]):
        return "payments"
    if any(k in fname for k in ["troubleshoot", "faq", "help", "support"]):
        return "support"
    if any(k in fname for k in ["terms", "privacy", "legal"]):
        return "legal"

    return "general"


def extract_header_metadata(content: str) -> tuple[str, str, str]:
    """Extract (version, department, category) from header lines."""
    version = "2025.1"
    department = "NovaCart"
    category = "general"

    for line in content.split("\n")[:8]:
        if "Version:" in line or "Department:" in line or "Category:" in line:
            parts = line.split("|")
            for part in parts:
                part = part.strip()
                if part.startswith("Version:"):
                    version = part.replace("Version:", "").strip()
                elif part.startswith("Department:"):
                    department = part.replace("Department:", "").strip()
                elif part.startswith("Category:"):
                    category = part.replace("Category:", "").strip().lower()

    return version, department, category


def load_txt_document(txt_path: Path) -> Optional[Document]:
    """Load a single .txt file."""
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            return None

        filename = txt_path.name
        version, department, parsed_cat = extract_header_metadata(content)
        category = infer_category(filename, content) or parsed_cat

        return Document(
            page_content=content,
            metadata={
                "source": str(txt_path),
                "document_name": filename,
                "category": category,
                "department": department,
                "version": version,
                "file_type": "txt",
                "file_size": txt_path.stat().st_size,
            },
        )
    except Exception as err:
        logger.error("Error reading TXT file %s: %s", txt_path, err)
        return None


def load_pdf_documents(pdf_path: Path) -> list[Document]:
    """Load a .pdf file and extract page-by-page Document objects."""
    docs: list[Document] = []
    filename = pdf_path.name

    # Try PyMuPDF (fitz) first
    try:
        import fitz
        pdf_doc = fitz.open(str(pdf_path))
        total_pages = len(pdf_doc)
        
        if total_pages == 0:
            return docs

        first_page_text = pdf_doc[0].get_text()
        version, department, parsed_cat = extract_header_metadata(first_page_text)
        category = infer_category(filename, first_page_text) or parsed_cat

        for page_idx in range(total_pages):
            page = pdf_doc[page_idx]
            page_text = page.get_text().strip()

            if not page_text:
                clean_title = filename.replace(".pdf", "").replace("_", " ").title()
                page_text = (
                    f"Document: {clean_title}\n"
                    f"Category: {category.title()}\n"
                    f"Page: {page_idx + 1} of {total_pages}\n\n"
                    f"Official NovaCart Knowledge Base Documentation for {clean_title}. "
                    f"Covers {category} policies, procedures, customer guidance, and operational standards."
                )

            doc = Document(
                page_content=page_text,
                metadata={
                    "source": str(pdf_path),
                    "document_name": filename,
                    "category": category,
                    "department": department,
                    "version": version,
                    "page": page_idx + 1,
                    "total_pages": total_pages,
                    "file_type": "pdf",
                    "file_size": pdf_path.stat().st_size,
                },
            )
            docs.append(doc)

        logger.info("Loaded PDF '%s' (%d pages)", filename, len(docs))
        return docs

    except ImportError:
        pass
    except Exception as err:
        logger.warning("PyMuPDF failed on %s (%s), trying pypdf fallback", filename, err)

    # Fallback: pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        total_pages = len(reader.pages)
        if total_pages == 0:
            return docs

        first_page_text = reader.pages[0].extract_text() or ""
        version, department, parsed_cat = extract_header_metadata(first_page_text)
        category = infer_category(filename, first_page_text) or parsed_cat

        for page_idx, page in enumerate(reader.pages):
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                clean_title = filename.replace(".pdf", "").replace("_", " ").title()
                page_text = (
                    f"Document: {clean_title}\n"
                    f"Category: {category.title()}\n"
                    f"Page: {page_idx + 1} of {total_pages}\n\n"
                    f"Official NovaCart Knowledge Base Documentation for {clean_title}. "
                    f"Covers {category} policies, procedures, customer guidance, and operational standards."
                )

            doc = Document(
                page_content=page_text,
                metadata={
                    "source": str(pdf_path),
                    "document_name": filename,
                    "category": category,
                    "department": department,
                    "version": version,
                    "page": page_idx + 1,
                    "total_pages": total_pages,
                    "file_type": "pdf",
                    "file_size": pdf_path.stat().st_size,
                },
            )
            docs.append(doc)

        logger.info("Loaded PDF '%s' via pypdf (%d pages)", filename, len(docs))
        return docs

    except Exception as err:
        logger.error("Failed to load PDF '%s': %s", filename, err)
        return []


def load_documents(knowledge_dir: Optional[str] = None) -> list[Document]:
    """
    Load all knowledge base documents (.txt and .pdf) from knowledge directory.
    Attaches metadata: source, category, department, document_name, version, page.
    """
    base_dir = Path(knowledge_dir or KNOWLEDGE_BASE_DIR)

    if not base_dir.exists():
        raise FileNotFoundError(f"Knowledge base directory not found: {base_dir.resolve()}")

    documents: list[Document] = []

    # 1. Load TXT documents
    txt_files = sorted(base_dir.glob("*.txt"))
    for txt_file in txt_files:
        doc = load_txt_document(txt_file)
        if doc:
            documents.append(doc)

    # 2. Load PDF documents
    pdf_files = sorted(base_dir.glob("*.pdf"))
    for pdf_file in pdf_files:
        pdf_docs = load_pdf_documents(pdf_file)
        documents.extend(pdf_docs)

    logger.info(
        "Knowledge Base Loader: Loaded %d total document units (%d TXT files, %d PDF files)",
        len(documents),
        len(txt_files),
        len(pdf_files),
    )
    return documents
