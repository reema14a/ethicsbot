CLAIM_EXTRACT_TEMPLATE = """Extract concise factual claims (1 sentence each) from the content below.
Only include verifiable, concrete assertions (who/what/when/where). Skip opinions.

Return as bullet points.

Content:
{content}
"""
def build_claim_extraction_prompt(content: str) -> str:
    return CLAIM_EXTRACT_TEMPLATE.format(content=content)
