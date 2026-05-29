"""
RAG Memory module using ChromaDB + Gemini Embeddings.

Stores and retrieves past irrigation decisions for the Botanist Agent.
Supports optional crop-type metadata filtering for targeted retrieval.
"""
import logging
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from config import settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Vector Store Setup
# ---------------------------------------------------------------------------
def _get_vectorstore() -> Chroma:
    """Return a ChromaDB vectorstore with local HuggingFace embeddings."""
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return Chroma(
        collection_name="agri_decisions",
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,
    )


def add_memory(text: str, metadata: dict | None = None) -> None:
    """Save a past decision into ChromaDB for future RAG retrieval."""
    log.info("Saving memory to ChromaDB: %s", text[:80])
    try:
        vectorstore = _get_vectorstore()
        vectorstore.add_texts(texts=[text], metadatas=[metadata] if metadata else [{}])
    except Exception as e:
        log.warning("Failed to save memory to ChromaDB: %s", e)


def search_memory(query: str, k: int = 3, crop_type: str | None = None) -> list[str]:
    """
    Retrieve similar past scenarios from ChromaDB.

    Args:
        query: The natural language search query.
        k: Number of results to return.
        crop_type: Optional — filter results to a specific crop type.

    Returns:
        List of matching memory text snippets.
    """
    vectorstore = _get_vectorstore()

    # Apply metadata filter if crop_type is specified
    search_kwargs: dict = {"k": k}
    if crop_type:
        search_kwargs["filter"] = {"crop_type": crop_type}

    try:
        results = vectorstore.similarity_search(query, **search_kwargs)
        log.info("RAG memory retrieved %d results (crop_type=%s)", len(results), crop_type)
        return [res.page_content for res in results]
    except Exception as e:
        # If filtered search fails (e.g. no metadata), fall back to unfiltered
        log.warning("Filtered RAG search failed (%s), falling back to unfiltered", e)
        results = vectorstore.similarity_search(query, k=k)
        return [res.page_content for res in results]
