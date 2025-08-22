from __future__ import annotations
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File, Form
from typing import Optional

from ethics_engine.analyze import analyze_use_case
from ethics_engine.watchdog.pipeline import run_watchdog
from ethics_engine.watchdog.schemas import WatchReport

app = FastAPI(title="EthicsBot API", version="0.1.0")

# CORS so a browser extension can call localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "chrome-extension://*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeReq(BaseModel):
    query: str
    k: int = 3

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/analyze")
def analyze(req: AnalyzeReq):
    result = analyze_use_case(req.query, k=req.k)
    return {"result": result}

class WatchReq(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None
    online: bool = False
    k: int = 3
    model: Optional[str] = None
    streaming: bool = False

@app.post("/watch/text")
def watch_text(payload: WatchReq):
    txt = (payload.text or "").strip()
    if not txt and payload.url:
        if payload.online:
            from ethics_engine.ui.app import _fetch_url_text  # reuse same helper
            fetched = _fetch_url_text(payload.url)
            txt = fetched or f"(Online fetch failed; please paste text)\nURL: {payload.url}"
        else:
            txt = f"(Offline mode) URL provided: {payload.url}\nGive verification steps (domain checks, date checks, source tracing)."

    rep: WatchReport = run_watchdog(txt, k=payload.k, stream=payload.streaming, model=payload.model)
    return {
        "label": rep.label,
        "overall_risk": rep.overall_risk,
        "signals": [{"name": s.name, "score": s.score, "details": getattr(s, "details", "")} for s in rep.signals or []],
        "incidents": [{"snippet": e.snippet, "source": e.source} for e in rep.related_incidents or []],
        "summary": rep.llm_summary or "",
    }

@app.post("/watch/file")
async def watch_file(file: UploadFile = File(...), k: int = Form(3), model: str | None = Form(None)):
    # Basic image OCR; extend to PDF/video later
    from PIL import Image
    import io
    import pytesseract

    data = await file.read()
    try:
        img = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(img)
    except Exception:
        # Fallback: treat as plain text file
        text = data.decode(errors="ignore")

    rep = run_watchdog(text, k=k, stream=False, model=model)
    return {
        "label": rep.label,
        "risk": rep.overall_risk,
        "signals": [{ "name": s.name, "score": s.score, "details": s.details } for s in rep.signals],
        "incidents": [{ "snippet": e.snippet, "source": e.source } for e in rep.related_incidents],
        "summary": rep.llm_summary,
    }