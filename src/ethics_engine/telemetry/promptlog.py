import os, hashlib, re, logging

logger = logging.getLogger("ethicsbot.telemetry.prompt")

LOG_PROMPT_MODE = os.getenv("ETHICSBOT_LOG_PROMPT", "preview").lower()  # "off" | "preview" | "full"
PROMPT_PREVIEW = int(os.getenv("ETHICSBOT_PROMPT_MAX_PREVIEW", "240"))

def _fingerprint(s: str) -> str:
    try:
        return hashlib.sha256(s.encode("utf-8", "ignore")).hexdigest()[:12]
    except Exception:
        return "na"

def _redact(s: str) -> str:
    if not s:
        return s
    # emails
    s = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<redacted:email>", s)
    # phone-ish
    s = re.sub(r"\+?\d[\d\s().-]{7,}\d", "<redacted:phone>", s)
    # bearer/api tokens
    s = re.sub(r"(?i)bearer\s+[A-Za-z0-9._-]+", "<redacted:token>", s)
    s = re.sub(r"(?i)(api[-_\s]?key)\s*[:=]\s*[A-Za-z0-9._-]+", r"\1=<redacted:token>", s)
    return s

def _preview(s: str, n: int = PROMPT_PREVIEW) -> str:
    if s is None:
        return ""
    s = s.replace("\r", "")
    if len(s) <= n:
        return s
    return f"{s[:n]} … [+{len(s)-n}]"

def log_prompt(prompt: str, *, run_id: str, stage: str, claims_cnt: int, signals_cnt: int, incidents_cnt: int, span=None):
    # Always attach metrics to span; content logging controlled by env
    sha = _fingerprint(prompt)
    attrs = {
        "prompt.len": len(prompt),
        "prompt.sha": sha,
        "claims.count": claims_cnt,
        "signals.count": signals_cnt,
        "incidents.count": incidents_cnt,
    }
    if span:  # OpenTelemetry
        span.add_event("prompt.built", attributes=attrs)

    if LOG_PROMPT_MODE == "off":
        logger.info(
            "llm.prompt (logging=off) len=%d sha=%s claims=%d signals=%d incidents=%d",
            attrs["prompt.len"], sha, claims_cnt, signals_cnt, incidents_cnt,
            extra={"run_id": run_id, "stage": stage},
        )
        return

    to_log = prompt if LOG_PROMPT_MODE == "full" else _preview(prompt)
    to_log = _redact(to_log)
    label = "full" if LOG_PROMPT_MODE == "full" else "preview"
    logger.info(
        "llm.prompt (%s) len=%d sha=%s claims=%d signals=%d incidents=%d :: %s",
        label, attrs["prompt.len"], sha, claims_cnt, signals_cnt, incidents_cnt, to_log,
        extra={"run_id": run_id, "stage": stage},
    )
