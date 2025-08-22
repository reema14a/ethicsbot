from __future__ import annotations
from typing import Iterable

WATCHDOG_GUIDE_TEMPLATE = """You are a misinformation watchdog assistant. The user gave this content:

{content}

Claims (rough):
{claims_md}

Heuristic signals (0..1):
{signals_md}

Similar past incidents:
{incidents_md}

Task:
- Briefly explain the top 2–3 risks and why they apply.
- Suggest 3 concrete verification steps a non-technical person can do offline (dates, reverse image steps, local corroboration, sourcing).
- Keep it under 180 words, bullet points preferred.
"""

def build_watchdog_summary_prompt(
    content: str,
    claims: Iterable,
    signals: Iterable,
    related_incidents: Iterable,
) -> str:
    claims_md = "\n".join(f"- {getattr(c, 'text', str(c))}" for c in (claims or [])) or "None"
    signals_md = "\n".join(
        f"- {getattr(s, 'name', 'signal')}: {float(getattr(s, 'score', 0.0)):.2f}"
        for s in (signals or [])
    ) or "None"
    incidents_md = "\n".join(
        f"- {getattr(e, 'snippet', '')}" for e in (related_incidents or [])
    ) or "None"

    return WATCHDOG_GUIDE_TEMPLATE.format(
        content=content, claims_md=claims_md, signals_md=signals_md, incidents_md=incidents_md
    )
