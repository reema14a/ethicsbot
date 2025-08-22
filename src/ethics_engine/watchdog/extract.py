from __future__ import annotations
import re
from typing import List
from .schemas import Claim

# Minimal claim splitter: split on sentence boundaries; keep sentences with verbs/nouns
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

def extract_claims(text: str) -> List[Claim]:
    parts = [p.strip() for p in _SENT_SPLIT.split(text) if p.strip()]
    # keep medium length statements only (avoid too short/too long)
    claims = [Claim(p) for p in parts if 20 <= len(p) <= 280]
    return claims[:6]  # cap for speed
