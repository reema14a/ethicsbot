from __future__ import annotations
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from .store import get_vectorstore
from .llm import get_llm
from .prompt import ANALYZE_TEMPLATE
from .config import DEFAULT_K

def analyze_use_case(query: str, k: int = DEFAULT_K, *, stream: bool = False, model: str | None = None) -> str:
    """
    1) Retrieve similar incidents from Chroma
    2) Build a prompt
    3) Ask the local LLM for risks + mitigations
    """
    vs = get_vectorstore()
    results = vs.similarity_search(query, k=k)
    incidents = "\n".join(f"- {r.page_content}" for r in results) or "None"

    if stream:
        llm = get_llm(model=model, streaming=True, callbacks=[StreamingStdOutCallbackHandler()])
        prompt = ANALYZE_TEMPLATE.format(use_case=query, incidents=incidents)
        # Streaming prints tokens as they arrive; return an empty string so CLI doesn’t duplicate output
        llm.invoke(prompt)
        return ""
    else:
        llm = get_llm(model=model)
        prompt = ANALYZE_TEMPLATE.format(use_case=query, incidents=incidents)
        return llm.invoke(prompt)


def analyze_use_case(query: str, k: int = DEFAULT_K, *, stream: bool = False, model: str | None = None) -> str:
    vs = get_vectorstore()
    results = vs.similarity_search(query, k=k)
    incidents = "\n".join(f"- {r.page_content}" for r in results) or "None"

    if stream:
        llm = get_llm(model=model, streaming=True, callbacks=[StreamingStdOutCallbackHandler()])
        prompt = ANALYZE_TEMPLATE.format(use_case=query, incidents=incidents)
        # Streaming prints tokens as they arrive; return an empty string so CLI doesn’t duplicate output
        llm.invoke(prompt)
        return ""
    else:
        llm = get_llm(model=model)
        prompt = ANALYZE_TEMPLATE.format(use_case=query, incidents=incidents)
        return llm.invoke(prompt)