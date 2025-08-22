from __future__ import annotations
import json, logging, os, sys, re
from logging.handlers import RotatingFileHandler

# --- OpenTelemetry (local-friendly) ---
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
except Exception:  # pragma: no cover
    OTLPSpanExporter = None  # optional dep

# ---- extras extraction -------------------------------------------------------
# Standard LogRecord keys we DON'T want to duplicate in "extras"
_STD_KEYS = {
    "name","msg","args","levelname","levelno","pathname","filename","module","exc_info",
    "exc_text","stack_info","lineno","funcName","created","msecs","relativeCreated",
    "thread","threadName","processName","process","message","asctime","stacklevel", "taskName"
}

def _extract_extras(record: logging.LogRecord) -> dict:
    """Return all custom attributes set via `extra=...`."""
    # record.__dict__ contains both standard and custom fields
    return {k: v for k, v in record.__dict__.items() if k not in _STD_KEYS}

# Basic redaction for safety (emails, phone-ish, tokens)
_RE_EMAIL  = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_RE_PHONE  = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_RE_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]+")
_RE_APIKEY = re.compile(r"(?i)(api[-_\s]?key)\s*[:=]\s*[A-Za-z0-9._-]+")

def _redact(text: str) -> str:
    try:
        text = _RE_EMAIL.sub("<redacted:email>", text)
        text = _RE_PHONE.sub("<redacted:phone>", text)
        text = _RE_BEARER.sub("<redacted:token>", text)
        text = _RE_APIKEY.sub(r"\1=<redacted:token>", text)
        return text
    except Exception:
        return text

# ---- formatters --------------------------------------------------------------
class DynamicJsonFormatter(logging.Formatter):
    """JSON formatter that merges arbitrary `extra` fields automatically."""
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Add all custom extras
        extras = _extract_extras(record)
        if extras:
            # stringify anything not JSON-serializable
            def _js(v):
                try:
                    json.dumps(v)  # test
                    return v
                except Exception:
                    return str(v)
            payload.update({k: _js(v) for k, v in extras.items()})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Optional redaction of msg/extras if you want (keep simple here)
        return json.dumps(payload, ensure_ascii=False)

class SafeKVFormatter(logging.Formatter):
    """
    Text formatter that appends arbitrary extras as 'k=v' pairs.
    It won't crash if fields are missing.
    """
    def format(self, record: logging.LogRecord) -> str:
        # Ensure base message
        base = super().format(record)
        # Build k=v tail from extras
        extras = _extract_extras(record)
        if extras:
            # sort for stable output
            kv = " ".join(f"{k}={extras[k]}" for k in sorted(extras))
            # Redact obvious secrets in the tail (not touching the main message)
            kv = _redact(kv)
            return f"{base} | {kv}"
        return base

# ---- setup -------------------------------------------------------------------
def setup_logging() -> logging.Logger:
    """
    Configure root 'ethicsbot' logger:
    - Console + optional rotating file
    - Plain text by default; JSON if ETHICSBOT_LOG_JSON=1
    Env:
      ETHICSBOT_LOG_LEVEL=DEBUG|INFO|...
      ETHICSBOT_LOG_JSON=0|1
      ETHICSBOT_LOG_FILE=/path/to/file.log
    """
    lvl = os.getenv("ETHICSBOT_LOG_LEVEL", "INFO").upper()
    json_mode = os.getenv("ETHICSBOT_LOG_JSON", "0") == "1"
    log_file = os.getenv("ETHICSBOT_LOG_FILE", "").strip() or None

    logger = logging.getLogger("ethicsbot")
    logger.setLevel(lvl)
    logger.propagate = False
    logger.handlers.clear()

    fmt = DynamicJsonFormatter() if json_mode else SafeKVFormatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    )

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(lvl)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3)
        fh.setLevel(lvl)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger

def setup_tracing(service_name: str = "ethicsbot", exporter: str = "console"):
    """
    Initialize OpenTelemetry tracing.
    exporter: 'console' (default) or 'otlp' (needs collector; optional).
    Env (for OTLP):
      OTEL_EXPORTER_OTLP_ENDPOINT=grpc://localhost:4317
    """
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if exporter == "otlp" and OTLPSpanExporter is not None:
        span_exporter = OTLPSpanExporter()  # respects OTEL_* env vars
    else:
        span_exporter = ConsoleSpanExporter()  # prints spans to stdout

    provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)
