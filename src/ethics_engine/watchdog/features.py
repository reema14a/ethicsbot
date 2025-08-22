from __future__ import annotations
import re
from typing import Dict

SENSATIONAL_PATTERNS = [
    r"shocking", r"you won't believe", r"exposed", r"the truth (they|they're) hiding",
    r"secret plan", r"BREAKING", r"urgent", r"!!!"
]

def heuristic_scores(text: str) -> Dict[str, float]:
    lower = text.lower()

    # 1) sensational language
    sensational_hits = sum(1 for p in SENSATIONAL_PATTERNS if re.search(p, lower))
    sensational_score = min(1.0, sensational_hits / 3.0)

    # 2) missing source cues
    # crude: if mentions "study"/"report"/"research" w/o any link or org name
    mentions_study = bool(re.search(r"\b(study|report|research)\b", lower))
    has_link = bool(re.search(r"https?://", text))
    missing_source_score = 0.6 if (mentions_study and not has_link) else 0.0

    # 3) date-time ambiguity (claims like "today"/"now" with no date)
    vague_time = bool(re.search(r"\b(today|now|currently|breaking)\b", lower))
    date_present = bool(re.search(r"\b\d{4}\b", text))
    time_ambig_score = 0.5 if (vague_time and not date_present) else 0.0

    # Overall simple blend (keep it simple & explainable)
    return {
        "sensational_language": sensational_score,
        "missing_source": missing_source_score,
        "time_ambiguity": time_ambig_score,
    }
