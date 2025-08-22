from __future__ import annotations
from typing import List
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from ..store import get_vectorstore
from ..llm import get_llm
from ..prompt import ANALYZE_TEMPLATE  # reuse for summary tone or make a new one
from .schemas import WatchReport, Claim, Evidence, Signal
from .extract import extract_claims
from .features import heuristic_scores

def _score_to_label(x: float) -> str:
    if x >= 0.7: return "Likely Misinfo"
    if x >= 0.4: return "Needs Verification"
    return "Low"

def run_watchdog(text: str, *, k: int = 3, stream: bool = True, model: str | None = None) -> WatchReport:
    # 1) claims
    claims: List[Claim] = extract_claims(text)

    # 2) retrieve similar incidents
    vs = get_vectorstore()
    sims = vs.similarity_search(text, k=k)
    related = [Evidence(snippet=d.page_content, source=d.metadata.get("source")) for d in sims]

    # 3) heuristics
    hs = heuristic_scores(text)
    signals = [Signal(name=k, score=v, details=f"{k}={v:.2f}") for k, v in hs.items()]

    # 4) compute overall risk (simple blend: max of signals, raised by similarity hits)
    base = max(hs.values()) if hs else 0.0
    boost = 0.1 * len(related)  # more similar incidents → higher risk of pattern
    overall = max(0.0, min(1.0, base + min(0.3, boost)))

    # 5) LLM reasoning summary (stream if requested)
    incidents_text = "\n".join(f"- {e.snippet}" for e in related) or "None"
    guide_prompt = f"""
You are a misinformation watchdog assistant. The user gave this content:

{text}

Claims (rough):
{chr(10).join(f"- {c.text}" for c in claims) or "None"}

Heuristic signals (0..1):
{chr(10).join(f"- {s.name}: {s.score:.2f}" for s in signals) or "None"}

Similar past incidents:
{incidents_text}

Task:
- Briefly explain the top 2–3 risks and why they apply.
- Suggest 3 concrete verification steps a non-technical person can do offline (dates, reverse image steps, local corroboration, sourcing).
- Keep it under 180 words, bullet points preferred.
"""
    if stream:
        llm = get_llm(model=model, streaming=True, callbacks=[StreamingStdOutCallbackHandler()], temperature=0.2)
        llm.invoke(guide_prompt)
        llm_text = ""  # already streamed
    else:
        llm = get_llm(model=model, temperature=0.2)
        llm_text = llm.invoke(guide_prompt)

    return WatchReport(
        overall_risk=overall,
        label=_score_to_label(overall),
        claims=claims,
        signals=signals,
        related_incidents=related,
        llm_summary=llm_text,
    )
