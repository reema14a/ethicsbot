from __future__ import annotations
from typing import Any, Dict, Optional
from langchain_ollama import ChatOllama
from .config import MODEL

def get_llm(*, model: Optional[str] = None, streaming: bool = False, **kwargs: Dict[str, Any]) -> ChatOllama:
    params = {"model": model or MODEL, "temperature": 0.2}
    if streaming:
        params["streaming"] = True
    params.update(kwargs or {})
    return ChatOllama(**params)