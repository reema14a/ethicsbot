# ethics_engine/watchdog/claims.py
import os
from typing import List
from ethics_engine.prompts.claims import build_claim_extraction_prompt
from ethics_engine.llm import get_llm
from ethics_engine.watchdog.schemas import Claim

USE_LLM_CLAIMS = os.getenv("ETHICSBOT_USE_LLM_CLAIMS", "0") == "1"

def extract_claims(text: str) -> List[Claim]:
    if not USE_LLM_CLAIMS:
        from .extract import extract_claims as rule_extract
        return rule_extract(text)

    prompt = build_claim_extraction_prompt(text)
    llm = get_llm(temperature=0.0)
    out = llm.invoke(prompt)
    # naive parse: lines starting with '- '
    claims = [Claim(text=line[2:].strip()) for line in out.splitlines() if line.strip().startswith("- ")]
    return claims
