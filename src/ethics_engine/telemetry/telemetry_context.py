from __future__ import annotations
import logging
from contextvars import ContextVar

# Context var that holds the current run_id for this task
run_id_var: ContextVar[str | None] = ContextVar("ethicsbot_run_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("ethicsbot_session_id", default=None)

class RunIdFilter(logging.Filter):
    """Injects run_id/session_id from ContextVars into every log record."""
    def filter(self, record: logging.LogRecord) -> bool:
        rid = run_id_var.get()
        sid = session_id_var.get()
        if rid:
            setattr(record, "run_id", rid)
        if sid:
            setattr(record, "session_id", sid)
        return True
