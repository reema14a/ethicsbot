from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Claim:
    text: str

@dataclass
class Evidence:
    snippet: str
    source: Optional[str] = None
    note: Optional[str] = None

@dataclass
class Signal:
    name: str
    score: float
    details: str

@dataclass
class WatchReport:
    overall_risk: float           # 0..1
    label: str                    # "Low", "Needs Verification", "Likely Misinfo"
    claims: List[Claim]
    signals: List[Signal]
    related_incidents: List[Evidence]
    llm_summary: str
