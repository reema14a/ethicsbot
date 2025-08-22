from __future__ import annotations
import os
import logging
from typing import Tuple, List
from PIL import Image
import pytesseract
import mimetypes
import gradio as gr
from urllib.parse import urlparse

from ethics_engine.watchdog.pipeline import run_watchdog
from ethics_engine.watchdog.schemas import WatchReport  
from ethics_engine.store import get_vectorstore  

from ethics_engine.telemetry.telemetry import setup_logging, SafeKVFormatter
from ethics_engine.telemetry.telemetry_context import RunIdFilter, ui_logging_session
import uuid

setup_logging()
logging.getLogger("ethicsbot").addFilter(RunIdFilter())

# Optional tracing 
# from ethics_engine.telemetry import setup_tracing
# setup_tracing(service_name="ethicsbot")

# # Keep a named UI logger for convenience
logger = logging.getLogger("ethicsbot.watchdog.ui")

# Ensure vectorstore can initialize even if not yet seeded (will just be empty)
_ = get_vectorstore()

# Dependency capability flags
try:
    _ = pytesseract.get_tesseract_version()
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

try:
    import requests  # noqa: F401
    HAVE_REQUESTS = True
except Exception:
    HAVE_REQUESTS = False

try:
    import bs4  # noqa: F401
    HAVE_BS4 = True
except Exception:
    HAVE_BS4 = False

ONLINE_HTML_AVAILABLE = HAVE_REQUESTS and HAVE_BS4

DEFAULT_PLACEHOLDER = (
    "Paste a post, message, or claim here. Example:\n\n"
    "BREAKING: Secret plan exposed! A new AI will fire all nurses by next week.\n"
)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _html_progress(pct: int, label: str = "Working…") -> str:
    pct = max(0, min(100, int(pct)))
    return f"""
    <div style="display:inline-flex;align-items:center;gap:8px">
      <div style="width:160px;height:10px;background:#eee;border-radius:6px;overflow:hidden">
        <div style="height:100%;width:{pct}%;background:#ff7a00;transition:width .25s ease"></div>
      </div>
      <span>{label} — {pct}%</span>
    </div>
    """

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
):
    """
    Yields:
      - badge text (Markdown)
      - signals markdown
      - incidents table (rows)
      - summary markdown
      - ui logs (string)
    """
    with ui_logging_session(session_id) as ui_logs:
        log = logger.info # alias only

        
        
        # 0% — starting
        yield (_html_progress(0, "Starting"), gr.update(), gr.update(), gr.update(), gr.update(), "\n".join(ui_logs))
        
        log("Assess: start")

        # Yield immediately so the logs box populates
        if not text or len(text.strip()) < 8:
            log("Validation: input too short or empty.")
            # yield immediately so the logs box populates
            yield (_html_progress(100, "Done"), gr.update(), gr.update(), gr.update(), gr.update(), "\n".join(ui_logs))
            return

        clean_text = text.strip()
        log("Initializing pipeline & dependencies")
        yield (_html_progress(10, "Initializing"), gr.update(), gr.update(), gr.update(), gr.update(), "\n".join(ui_logs))

        log("Vector store ready")
        # get_vectorstore() already called at import; this is illustrative
        yield (_html_progress(20, "Loading casebase"), gr.update(), gr.update(), gr.update(), gr.update(), "\n".join(ui_logs))

        log("Running watchdog analysis")
        yield (_html_progress(45, "Running watchdog analysis"), gr.update(), gr.update(), gr.update(), gr.update(), "\n".join(ui_logs))

        
        rep: WatchReport = run_watchdog(
            clean_text,
            k=int(k) if k is not None else 3,
            stream=False,                 # UI shows final; streaming in CLI
            model=(model or None),
        )
        log("Watchdog analysis complete")

        log("Aggregating results")
        yield (_html_progress(70, "Aggregating results"), gr.update(), gr.update(), gr.update(), gr.update(), "\n".join(ui_logs))

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

        log("Assess: done")

        # Final yield with all outputs + the full logs
        yield (
            _html_progress(100, "Done"),
            _as_markdown(badge),
            _as_markdown(signals_md),
            incidents_rows,
            _as_markdown(summary),
            "\n".join(ui_logs),
        )

        

def _read_text_from_file(path: str) -> str:
    # Try best-effort decodes for text-like files
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    # Binary fallback: allow some content extraction
    with open(path, "rb") as f:
        return f.read().decode(errors="ignore")

def _ocr_image(path: str) -> str:
    img = Image.open(path)
    return pytesseract.image_to_string(img)

def _fetch_url_text(url: str, *, timeout=15, max_bytes=2_000_000) -> str:
    """Download & extract readable text. Returns "" on failure."""

    log = logging.getLogger("ethicsbot.watchdog.ui")
    if not ONLINE_HTML_AVAILABLE:
        log.warning("online.fetch.unavailable", extra={"stage": "ingest"})
        return ""
    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception:
        return ""
    
    # allow only http(s)
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        return ""
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "EthicsBot/1.0"})
    except Exception as e:
        log.warning("online.fetch.error", extra={"stage": "ingest", "err": repr(e)})
        return ""
    
    ct = (r.headers.get("Content-Type") or "").lower()
    content = r.content[:max_bytes]
    text = ""

    # PDFs
    if "application/pdf" in ct or url.lower().endswith(".pdf"):
        try:
            import pypdf
            from io import BytesIO
            reader = pypdf.PdfReader(BytesIO(content))
            pages = [(p.extract_text() or "") for p in reader.pages[:10]]
            return "\n\n".join(pages).strip()
        except Exception:
            return ""

    # Images -> OCR if available
    if ct.startswith("image/") or any(url.lower().endswith(ext) for ext in (".png",".jpg",".jpeg",".webp",".bmp",".tif",".tiff")):
        if not OCR_AVAILABLE:
            return ""
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(content))
            return pytesseract.image_to_string(img).strip()
        except Exception:
            return ""

    # HTML -> extract title + paragraphs
    if "html" in ct or content.startswith(b"<!") or b"<html" in content[:1024].lower():
        if not HAVE_BS4:
            return ""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")
            title = (soup.title.string.strip() if soup.title and soup.title.string else "")
            paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            body = "\n".join(p for p in paras if p)
            return ("\n".join([title, body])).strip()
        except Exception:
            return ""

    # Otherwise, treat as text-ish
    try:
        return content.decode("utf-8")
    except Exception:
        return content.decode("latin-1", errors="ignore")


def assess_route(
    text: str,
    url: str,
    upload,  # gr.File returns a tempfile path-like object; use .name
    online: bool,
    k: int,
    model: str,
    streaming: bool,
    session_id: str | None = None
):
    """
    Generator.
    Precedence: file → text → url (offline/online).
    Yields the SAME 5 outputs as assess_text.
    """
    with ui_logging_session(session_id) as ui_logs:
        log = logging.getLogger("ethicsbot.watchdog.ui").info

        chosen_text = (text or "").strip()
        log("Route: start (ingest)")
        yield (_html_progress(5, "Reading input"), gr.update(), gr.update(), gr.update(), gr.update(), "\n".join(ui_logs))

        if upload is not None:
            # Gradio 5.x: upload is a TemporaryFile with .name
            fp = getattr(upload, "name", None) or str(upload)
            mt, _ = mimetypes.guess_type(fp)
            log("file.uploaded", extra={"stage": "ingest", "path": fp, "mimetype": mt or "-"})

            try:
                if mt and mt.startswith("image/"):
                    if not OCR_AVAILABLE:
                        chosen_text = "(OCR unavailable: install Tesseract to extract text from images.)"
                    else:
                        try:
                            chosen_text = _ocr_image(fp).strip() or "(OCR produced no text)"
                        except Exception as e:
                            logging.getLogger("ethicsbot.watchdog.ui").exception("ocr.failed", extra={"stage": "ingest"})
                            chosen_text = f"(OCR failed: {e})"
                elif (mt and mt in ("application/pdf",)) or (fp.lower().endswith(".pdf")):
                    # Optional: very light PDF text extraction without extra deps
                    try:
                        import pypdf  # pip install pypdf
                        reader = pypdf.PdfReader(fp)
                        pages = []
                        for i, page in enumerate(reader.pages[:10]):  # limit pages for UI responsiveness
                            pages.append(page.extract_text() or "")
                        chosen_text = "\n\n".join(pages).strip() or "(No extractable text from PDF)"
                    except Exception:
                        # Fallback as plain bytes decode
                        chosen_text = _read_text_from_file(fp)
                else:
                    chosen_text = _read_text_from_file(fp)
            except Exception as e:
                logging.getLogger("ethicsbot.watchdog.ui").exception("file.read.failed", extra={"stage": "ingest"})
                chosen_text = f"(File read error: {e})"

        elif not chosen_text and url:
            if online:
                if ONLINE_HTML_AVAILABLE:
                    yield (_html_progress(15, "Fetching URL"), gr.update(), gr.update(), gr.update(), gr.update(), "\n".join(ui_logs))
                
                    fetched = _fetch_url_text(url)
                    chosen_text = fetched or f"(Online fetch failed or produced no text)\nURL: {url}"
                else:
                    chosen_text = f"(Online fetch unavailable on this install)\nURL: {url}"
            else:
                chosen_text = f"(Offline mode) URL provided: {url}\nGive verification steps (domain checks, date checks, source tracing)."

        # Show ingest complete before LLM
        yield (_html_progress(20, "Ready to analyze"), gr.update(), gr.update(), gr.update(), gr.update(), "\n".join(ui_logs))

        # Delegate to assess_text (also a generator) and forward its yields
        for out in assess_text(chosen_text, k, model, streaming, session_id=session_id):
            yield out

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

        # Capability banner
        def _capabilities_md():
            ocr = "✅ OCR available" if OCR_AVAILABLE else "⚠️ OCR unavailable (install Tesseract to OCR images)"
            net = "✅ Online fetch available" if ONLINE_HTML_AVAILABLE else "⚠️ Online fetch unavailable (install requests + beautifulsoup4)"
            return f"**Capabilities**: {ocr} · {net}"

        gr.Markdown(_capabilities_md())

        with gr.Row(equal_height=True, variant="compact"):
            # Left column: URL + checkbox (and tip if deps missing)
            with gr.Column(scale=2, min_width=360):
                url = gr.Textbox(
                    label="URL (optional)",
                    placeholder="Paste a link",
                )
                online = gr.Checkbox(
                    value=False,
                    label="Fetch URL online",
                    interactive=ONLINE_HTML_AVAILABLE,
                )
                if not ONLINE_HTML_AVAILABLE:
                    gr.Markdown(
                        "*(Install `requests` and `beautifulsoup4` to enable online fetching.)*"
                    )

            # Right column: File upload
            with gr.Column(scale=1, min_width=320):
                upload = gr.File(
                    label="Upload image or text file (optional)",
                    file_count="single",
                    file_types=["image", ".txt", ".md", ".csv", ".pdf", ".html"],
                )

        with gr.Row():
            k = gr.Slider(1, 6, value=3, step=1, label="Similar incidents (Top‑K)")
            model = gr.Textbox(value=os.getenv("ETHICSBOT_MODEL", "llama3.2"), label="Model (Ollama tag)")
            streaming = gr.Checkbox(value=False, label="Stream tokens (CLI only; UI shows final)")

        with gr.Row():
            btn = gr.Button("Assess", variant="primary")
            spinner = gr.HTML(value=_html_progress(0, "Starting"), visible=False)

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
            fn=lambda: gr.update(value=_html_progress(0, "Starting"), visible=True),
            outputs=[spinner],
            show_progress=False,
            queue=False,  # instant UI toggle
        )

        # Long step: NO Gradio progress, we update spinner + logs ourselves
        ev = ev.then(
            fn=assess_route,
            inputs=[text, url, upload, online, k, model, streaming, session_state],
            outputs=[spinner, badge, signals_md, incidents, summary, ui_logs],
            show_progress=False,
        )

        # Hide bar at the end (optional)
        ev = ev.then(
            fn=lambda: _html_progress(100, "Done"),
            outputs=[spinner],
            show_progress=False,
            queue=False,
        ).then(lambda: gr.Info("Analysis complete."), show_progress=False, queue=False)

        gr.Markdown(
            "### Notes\n"
            "- Runs locally with your Ollama model and local Chroma casebase.\n"
            "- No internet required. Nothing is uploaded.\n"
            "- For faster demos, use a smaller model (e.g., `llama3.2`)."
        )

    # Queue so long tasks don't freeze the UI; tweak concurrency if you expect parallel users
    demo.queue(default_concurrency_limit=2, max_size=32)

    return demo

if __name__ == "__main__":
    ui = build_ui()
    # debug=True: easier to see tracebacks while developing
    ui.launch(server_name="0.0.0.0", server_port=7860, debug=True)
