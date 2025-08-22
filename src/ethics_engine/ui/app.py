from __future__ import annotations
import os
import logging
from typing import Tuple, List

import gradio as gr

from ethics_engine.watchdog.pipeline import run_watchdog
from ethics_engine.watchdog.schemas import WatchReport  
from ethics_engine.store import get_vectorstore  

from ethics_engine.telemetry.telemetry import setup_logging, SafeKVFormatter
from ethics_engine.telemetry.telemetry_context import RunIdFilter
import uuid
from ethics_engine.telemetry.telemetry_context import run_id_var, session_id_var

setup_logging()
logging.getLogger("ethicsbot").addFilter(RunIdFilter())

# Optional tracing 
# from ethics_engine.telemetry import setup_tracing
# setup_tracing(service_name="ethicsbot")

# Keep a named UI logger for convenience
logger = logging.getLogger("ethicsbot.watchdog.ui")

# Ensure vectorstore can initialize even if not yet seeded (will just be empty)
_ = get_vectorstore()

class _ListHandler(logging.Handler):
    def __init__(self, sink_list):
        super().__init__(level=logging.DEBUG) 
        self.sink = sink_list
        # SafeKVFormatter appends any extras (run_id, stage, payload_type, elapsed_ms, …) as k=v
        self.setFormatter(SafeKVFormatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
        ))

    def emit(self, record: logging.LogRecord):
        try:
            self.sink.append(self.format(record))
        except Exception:
            pass


DEFAULT_PLACEHOLDER = (
    "Paste a post, message, or claim here. Example:\n\n"
    "BREAKING: Secret plan exposed! A new AI will fire all nurses by next week.\n"
)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _html_spinner(show: bool) -> str:
    display = "inline-block" if show else "none"
    return (
        f"""<div id="spinner" style="display:{display};align-items:center;gap:8px">
                <div style="width:18px;height:18px;border:3px solid #ccc;border-top-color:#333;border-radius:50%;animation:spin 1s linear infinite"></div>
                <span>Working…</span>
            </div>
            <style>@keyframes spin{{to{{transform:rotate(360deg)}}}}</style>"""
    )

def _as_markdown(text: str | None) -> str:
    return text if isinstance(text, str) and text.strip() else ""

# -----------------------------------------------------------------------------
# Core assess function with progress + UI logs
# -----------------------------------------------------------------------------
def assess_text(
    text: str,
    k: int,
    model: str,
    streaming: bool,
    progress: gr.Progress = gr.Progress(track_tqdm=False),
    session_id: str | None = None,
) -> Tuple[str, str, List[List[str]], str, str]:
    """
    Returns:
      - badge text (Markdown)
      - signals markdown
      - incidents table (rows)
      - summary markdown
      - ui logs (string)
    """
    ui_logs: List[str] = []
    
    # Attach a per-run handler that mirrors *all* ethicsbot logs to UI
    list_handler = _ListHandler(ui_logs)
    root = logging.getLogger("ethicsbot")
    root.addHandler(list_handler)

    # Set correlation IDs for this run (visible in console + UI logs)
    run_id_token = run_id_var.set(uuid.uuid4().hex[:8])
    session_token = session_id_var.set(session_id)

    def log(msg: str):
        logger.info(msg)
        ui_logs.append(msg)

    try:
        log("Assess: start")
        if not text or len(text.strip()) < 8:
            log("Validation: input too short or empty.")
            return ("Please paste some content.", "", [], "", "\n".join(ui_logs))

        clean_text = text.strip()
        progress(0, desc="Initializing")
        log("Initializing pipeline & dependencies")

        progress(0.2, desc="Loading casebase / vector store")
        # get_vectorstore() already called at import; this is illustrative
        log("Vector store ready")

        progress(0.45, desc="Running watchdog analysis")
        rep: WatchReport = run_watchdog(
            clean_text,
            k=int(k) if k is not None else 3,
            stream=False,                 # UI shows final; streaming in CLI
            model=(model or None),
        )
        log("Watchdog analysis complete")

        progress(0.7, desc="Aggregating results")

        # Badge (string)
        badge = f"**{rep.label}**  _(risk = {rep.overall_risk:.2f})_"

        # Signals (Markdown string)
        if getattr(rep, "signals", None):
            sig_lines = [
                f"- **{s.name}**: {s.score:.2f}" + (f" — {s.details}" if getattr(s, 'details', '') else "")
                for s in rep.signals
            ]
            signals_md = "\n".join(sig_lines)
        else:
            signals_md = "_No signals detected_"

        # Incidents (list of rows)
        incidents_rows: List[List[str]] = []
        for i, e in enumerate(getattr(rep, "related_incidents", []) or [], 1):
            snippet = getattr(e, "snippet", "") or ""
            source = getattr(e, "source", "") or "-"
            incidents_rows.append([str(i), snippet, source])

        # Summary (Markdown string)
        summary = rep.llm_summary or "(Streaming disabled in UI; showing final summary.)"

        progress(1.0, desc="Done")
        log("Assess: done")

        # Ensure all text outputs are strings (Markdown/Textbox-safe)
        return (
            _as_markdown(badge),
            _as_markdown(signals_md),
            incidents_rows,
            _as_markdown(summary),
            "\n".join(ui_logs),
        )

    except Exception as e:
        logger.exception("Unhandled error during assessment")
        ui_logs.append(f"ERROR: {e!r}")
        # Return safe fallbacks to keep UI responsive
        return ("**Error**", "", [], "An error occurred. Check logs.", "\n".join(ui_logs))

    finally:
        # Clean up per-run handler and restore contextvars
        root.removeHandler(list_handler)
        run_id_var.reset(run_id_token)
        session_id_var.reset(session_token)

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
def build_ui():
    with gr.Blocks(
        title="EthicsBot Watchdog",
        css=".wrap {max-width: 900px; margin: auto;}"
    ) as demo:
        session_state = gr.State()  # holds session_id

        def _init_session():
            # short, human-friendly id
            return uuid.uuid4().hex[:6]

        demo.load(fn=_init_session, inputs=None, outputs=session_state)

        gr.Markdown("# 🛡️ EthicsBot Watchdog\nPaste a claim and get an offline assessment with next steps to verify.")

        with gr.Row():
            text = gr.Textbox(lines=8, placeholder=DEFAULT_PLACEHOLDER, label="Content to assess", elem_classes=["wrap"])

        with gr.Row():
            k = gr.Slider(1, 6, value=3, step=1, label="Similar incidents (Top‑K)")
            model = gr.Textbox(value=os.getenv("ETHICSBOT_MODEL", "llama3:8b"), label="Model (Ollama tag)")
            streaming = gr.Checkbox(value=False, label="Stream tokens (CLI only; UI shows final)")

        with gr.Row():
            btn = gr.Button("Assess", variant="primary")
            spinner = gr.HTML(_html_spinner(show=False))

        # Outputs
        badge = gr.Markdown(label="Risk Badge")
        with gr.Accordion("Signals", open=False):
            signals_md = gr.Markdown()
        with gr.Accordion("Related incidents", open=False):
            incidents = gr.Dataframe(
                headers=["#", "Snippet", "Source"],
                row_count=3,
                col_count=(3, "fixed"),
                wrap=True
            )
        with gr.Accordion("Summary & Next steps", open=True):
            summary = gr.Markdown()
        with gr.Accordion("Run logs (this session)", open=False):
            ui_logs = gr.Textbox(lines=10, show_label=False)

        # Event chain:
        # 1) Show spinner (no progress bar yet)
        ev = btn.click(
            fn=lambda: _html_spinner(True),
            outputs=[spinner],
            show_progress=False,
            queue=False,  # instant UI toggle
        )
        # 2) Run assess (with built-in progress bar)
        ev = ev.then(
            fn=assess_text,
            inputs=[text, k, model, streaming, session_state],
            outputs=[badge, signals_md, incidents, summary, ui_logs],
            show_progress="full",
        )
        # 3) Hide spinner and toast
        ev = ev.then(
            fn=lambda: _html_spinner(False),
            outputs=[spinner],
            show_progress=False,
            queue=False,
        ).then(lambda: gr.Info("Analysis complete."), show_progress=False, queue=False)

        gr.Markdown(
            "### Notes\n"
            "- Runs locally with your Ollama model and local Chroma casebase.\n"
            "- No internet required. Nothing is uploaded.\n"
            "- For faster demos, use a smaller model (e.g., `llama3:8b`)."
        )

    # Queue so long tasks don't freeze the UI; tweak concurrency if you expect parallel users
    demo.queue(default_concurrency_limit=2, max_size=32)

    return demo

if __name__ == "__main__":
    ui = build_ui()
    # debug=True: easier to see tracebacks while developing
    ui.launch(server_name="0.0.0.0", server_port=7860, debug=True)
