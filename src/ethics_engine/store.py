from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from langchain_chroma import Chroma
from langchain.schema import Document

from .embeddings import get_embeddings
from .config import PERSIST_DIR

_COLLECTION = "incidents"  # stable name for seed data

def _sanitize_metadata(md: Dict[str, Any]) -> Dict[str, Any]:
    """Chroma requires scalar metadata. Coerce lists/dicts to strings."""
    clean = {}
    for k, v in (md or {}).items():
        if isinstance(v, list):
            # join list values (e.g., tags) into a comma-separated string
            clean[k] = ", ".join(map(str, v))
        elif isinstance(v, dict):
            # serialize nested dicts
            clean[k] = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        elif isinstance(v, (str, int, float, bool)) or v is None:
            clean[k] = v
        else:
            # fallback to string
            clean[k] = str(v)
    return clean

def get_vectorstore() -> Chroma:
    """
    Use a persistent Chroma client. No explicit .persist() call is needed—
    the PersistentClient writes to disk automatically.
    """
    client = chromadb.PersistentClient(path=PERSIST_DIR)
    return Chroma(
        client=client,
        collection_name=_COLLECTION,
        embedding_function=get_embeddings(),
    )

def seed_from_jsonl(jsonl_path: str) -> int:
    """
    Load incidents from a JSONL file with records like:
      {"page_content": "...", "metadata": {"tags": ["bias"]}}
    and add to Chroma.
    """
    path = Path(jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {jsonl_path}")

    docs: List[Document] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            page = rec["page_content"]
            meta = _sanitize_metadata(rec.get("metadata", {}))
            docs.append(Document(page_content=page, metadata=meta))

    vs = get_vectorstore()
    if docs:
        vs.add_documents(docs)
        # Chroma automatically persists when created with persist_directory
        # No need to call persist() explicitly
    return len(docs)
