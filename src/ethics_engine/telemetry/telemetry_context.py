from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import List, Optional

# Import your formatter that appends arbitrary extras as k=v
# (from ethics_engine/telemetry/telemetry.py)
from .telemetry import SafeKVFormatter

# ---------------------------------------------------------------------------
# Correlation IDs carried via ContextVars
# ---------------------------------------------------------------------------
run_id_var: ContextVar[Optional[str]] = ContextVar("ethicsbot_run_id", default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar("ethicsbot_session_id", default=None)

class RunIdFilter(logging.Filter):
    """
    Injects run_id/session_id from ContextVars into every log record so formatters
    (or JSON encoders) can render them. Attach this once to the 'ethicsbot' logger:
        logging.getLogger("ethicsbot").addFilter(RunIdFilter())
    """
    def filter(self, record: logging.LogRecord) -> bool:
        rid = None
        sid = None
        try:
            rid = run_id_var.get()
        except LookupError:
            pass
        try:
            sid = session_id_var.get()
        except LookupError:
            pass
        if rid:
            setattr(record, "run_id", rid)
        if sid:
            setattr(record, "session_id", sid)
        return True

# ---------------------------------------------------------------------------
# UI log mirroring handler (puts formatted records into an in-memory list)
# ---------------------------------------------------------------------------
class UIListHandler(logging.Handler):
    """
    Mirrors all 'ethicsbot.*' logs into an in-memory list (sink) so the UI can
    display them live. Use via `ui_logging_session(...)` below.
    """
    def __init__(self, sink_list: List[str]):
        super().__init__(level=logging.DEBUG)  # capture DEBUG+ for the UI
        self.sink = sink_list
        self.setFormatter(SafeKVFormatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
        ))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.sink.append(self.format(record))
        except Exception:
            # Never let UI logging crash the app
            pass

def _find_ui_list_handler() -> Optional[UIListHandler]:
    root = logging.getLogger("ethicsbot")
    for h in root.handlers:
        if isinstance(h, UIListHandler):
            return h
    return None

# ---------------------------------------------------------------------------
# Context manager to ensure a UI handler + correlation IDs are set
# ---------------------------------------------------------------------------
@contextmanager
def ui_logging_session(
    session_id: Optional[str] = None,
    *,
    prefer_existing: bool = True,
):
    """
    Ensures there's a UIListHandler attached to the 'ethicsbot' logger and that
    run_id/session_id context vars are set for the duration of the block.

    - Reuses an existing UIListHandler if present (safe to nest).
    - If a run_id/session_id already exists and prefer_existing=True, it keeps them.
      Otherwise it sets a new run_id and/or the provided session_id.

    Yields:
        ui_logs (List[str]): the sink you can '\n'.join() to render in the UI.
    """
    root = logging.getLogger("ethicsbot")

    # Attach or reuse the UI list handler
    handler = _find_ui_list_handler()
    attached_here = False
    if handler is None:
        ui_logs: List[str] = []
        handler = UIListHandler(ui_logs)
        root.addHandler(handler)
        attached_here = True
    else:
        ui_logs = handler.sink  # reuse existing sink

    # Manage ContextVars tokens so we can reset only what we set
    run_token = None
    sess_token = None

    # run_id: generate if none present, or if caller prefers to override
    try:
        existing_run = run_id_var.get()
    except LookupError:
        existing_run = None
    if not (prefer_existing and existing_run):
        run_token = run_id_var.set(uuid.uuid4().hex[:8])

    # session_id: set only if provided or none exists and prefer_existing is False
    try:
        existing_session = session_id_var.get()
    except LookupError:
        existing_session = None
    if session_id is not None:
        sess_token = session_id_var.set(session_id)
    elif not (prefer_existing and existing_session):
        # leave as-is (None) if not provided
        pass

    try:
        yield ui_logs
    finally:
        if attached_here:
            root.removeHandler(handler)
        # Defensive: resets may be called on a different context/thread
        if run_token is not None:
            try:
                run_id_var.reset(run_token)
            except ValueError:
                # Fall back: clear in this context so we don't leak
                try:
                    run_id_var.set(None)
                except Exception:
                    pass
        if sess_token is not None:
            try:
                session_id_var.reset(sess_token)
            except ValueError:
                try:
                    session_id_var.set(None)
                except Exception:
                    pass

