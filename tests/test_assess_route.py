import types
from types import SimpleNamespace
from pathlib import Path
import builtins
import pytest

# Import the module that defines assess_route and assess_text
import ethics_engine.ui.app as app

def drain(gen):
    """Consume a generator and return the last yielded value."""
    last = None
    for x in gen:
        last = x
    return last

@pytest.fixture
def tmp_text(tmp_path):
    p = tmp_path / "claim.txt"
    p.write_text("BREAKING: Secret plan exposed! AI fires all nurses next week.")
    return p

@pytest.fixture
def tmp_image(tmp_path):
    # Reuse one of the generated files if present; else make a tiny PNG
    from PIL import Image
    p = tmp_path / "img.png"
    Image.new("RGB", (200, 60), "white").save(p)
    return p

def test_assess_route_text_file(monkeypatch, tmp_text):
    captured = {}
    def fake_assess_text(text, k, model, streaming, **kwargs):
        captured["text"] = text
        # match your real assess_text return arity (badge, signals, incidents, summary, logs)
        yield ("badge","signals",[], "summary", "logs")

    monkeypatch.setattr(app, "assess_text", fake_assess_text)
    upload = SimpleNamespace(name=str(tmp_text))
    badge, signals, incidents, summary, logs = drain(app.assess_route(
        text="", url="", upload=upload, online=False, k=3, model="llama3.2", streaming=False
    ))
    assert "Secret plan" in captured["text"]
    assert badge == "badge"

def test_assess_route_url_offline(monkeypatch):
    captured = {}
    def fake_assess_text(text, k, model, streaming, **kwargs):
        captured["text"] = text
        yield ("b","s",[], "sum", "log")
    monkeypatch.setattr(app, "assess_text", fake_assess_text)

    # empty text, no file, URL provided
    drain(app.assess_route(text="", url="https://example.com", upload=None, online=False, k=3, model="llama3.2", streaming=False))
    assert "(Offline mode) URL provided" in captured["text"]

def test_assess_route_url_online(monkeypatch):
    import ethics_engine.ui.app as app2
    monkeypatch.setattr(app2, "_fetch_url_text", lambda url, **_: "ONLINE TEXT OK")
    def fake_assess_text(text, k, model, streaming, **kwargs):
        yield ("b","s",[], text, "log")
    monkeypatch.setattr(app2, "assess_text", fake_assess_text)

    out = drain(app2.assess_route(text="", url="https://example.com/x", upload=None, online=True, k=3, model="llama3.2", streaming=False))
    assert out[3] == "ONLINE TEXT OK"

def test_assess_route_image_ocr(monkeypatch, tmp_image):
    # Mock pytesseract to avoid requiring Tesseract binary in CI
    import ethics_engine.ui.app as app2
    def fake_ocr(path): return "OCR RESULT: Hello world"
    monkeypatch.setattr(app2, "_ocr_image", fake_ocr)

    captured = {}
    def fake_assess_text(text, k, model, streaming, **kwargs):
        captured["text"] = text
        yield ("b","s",[], "sum", "log")
    monkeypatch.setattr(app2, "assess_text", fake_assess_text)

    upload = SimpleNamespace(name=str(tmp_image))
    drain(app2.assess_route(text="", url="", upload=upload, online=False, k=3, model="llama3.2", streaming=False))
    assert captured["text"].startswith("OCR RESULT:")

def test_assess_route_img_ocr_failure(monkeypatch, tmp_image):
    # Simulate Tesseract missing
    import ethics_engine.ui.app as app2
    def fake_ocr(path): raise RuntimeError("TesseractNotFoundError")
    monkeypatch.setattr(app2, "_ocr_image", fake_ocr)

    def fake_assess_text(text, k, model, streaming, **kwargs):
        yield ("b","s",[], text, "log")  # return text in summary to inspect
    monkeypatch.setattr(app2, "assess_text", fake_assess_text)

    upload = SimpleNamespace(name=str(tmp_image))
    out = drain(app2.assess_route(text="", url="", upload=upload, online=False, k=3, model="llama3.2", streaming=False))
    # out[3] is summary in our UI; check error marker flowed through
    assert "OCR failed" in out[3] or "File read error" in out[3]

def test_assess_route_ext_pdf_fallback(monkeypatch, tmp_path):
    p = tmp_path / "fake.pdf"
    p.write_text("This is actually text but .pdf extension")
    captured = {}
    def fake_assess_text(text, k, model, streaming, **kwargs):
        captured["text"] = text
        yield ("b","s",[], "sum", "log")
    monkeypatch.setattr(app, "assess_text", fake_assess_text)

    upload = SimpleNamespace(name=str(p))
    drain(app.assess_route(text="", url="", upload=upload, online=False, k=3, model="llama3.2", streaming=False))
    assert "actually text" in captured["text"]
