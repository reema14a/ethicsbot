ANALYZE_TEMPLATE = """Analyze the following AI use case for ethical risks.
Return JSON-like sections:

- Risks: bullet list with short labels + 1-line rationale
- RelatedIncidents: 2–4 items; each include what happened and the risk theme
- Mitigations: prioritized, concrete steps (policy, data, modeling, evaluation, oversight)

UseCase:
{use_case}

RelevantIncidents:
{incidents}
"""
