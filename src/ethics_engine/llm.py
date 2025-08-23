from __future__ import annotations
from typing import Any, Dict, Optional
from langchain_ollama import ChatOllama
from .config import MODEL

# sensible CPU defaults for Intel Mac (adjust if you see RAM pressure)
_DEFAULT_MODEL_KWARGS: Dict[str, Any] = {
    "num_ctx": 2048,        # cap giant 131k ctx
    "num_predict": 128,     # short JSON/summary outputs
    "keep_alive": "15m",    # don't unload between stages
    "num_thread": 8,       # match physical cores
    "num_batch": 512,      # safer on 32 GB RAM, reduces stalls
    "temperature": 0.2,
    "top_k": 40,
    "top_p": 0.9,
}

def get_llm(
    *,
    model: Optional[str] = None,
    streaming: bool = False,
    options: Optional[Dict[str, Any]] = None,
    **kwargs: Dict[str, Any],
) -> ChatOllama:
    """
    Returns a ChatOllama with good CPU defaults.
    Override any ollama option via `options` (e.g., num_ctx, num_predict, keep_alive).
    """
    # merge caller overrides over our defaults
    model_kwargs = {**_DEFAULT_MODEL_KWARGS, **(options or {})}
    # temperature exists in both places; keep model_kwargs as source of truth
    kwargs.pop("temperature", None)
    
    return ChatOllama(
        model=model or MODEL,
        streaming=streaming,
        model_kwargs=model_kwargs,
        **kwargs,
    )
