from __future__ import annotations
from langchain_ollama import OllamaEmbeddings
from .config import EMBED_MODEL

def get_embeddings():
    """
    Returns an embedding function.
    If you have a dedicated embedding model in Ollama (e.g., "nomic-embed-text"),
    set ETHICSBOT_EMBED_MODEL to that in .env.
    """
    return OllamaEmbeddings(model=EMBED_MODEL)
