from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# Model to use via Ollama (must be pulled separately with `ollama pull`)
MODEL = os.getenv("ETHICSBOT_MODEL", "gpt-oss-20b-fast")  # e.g. "gpt-oss:20b" or "llama3"
EMBED_MODEL = os.getenv("ETHICSBOT_EMBED_MODEL", "nomic-embed-text")  # e.g. "gpt-oss:20b" or "llama3"

# Where to persist the Chroma vector DB
PERSIST_DIR = os.getenv("ETHICSBOT_DB", "./data/chroma")

# Optional: default k for retrieval
DEFAULT_K = int(os.getenv("ETHICSBOT_TOPK", "3"))

# Ensure persist dir exists (ok if it already does)
Path(PERSIST_DIR).mkdir(parents=True, exist_ok=True)
