import pytest
from fastapi.testclient import TestClient
import io

import ethics_engine.api.main as api 
client = TestClient(api.app)

def test_watch_text_url_offline(monkeypatch):
    def fake_run_watchdog(text, k, stream, model):
        class R: label="LOW"; overall_risk=0.2; signals=[]; related_incidents=[]; llm_summary=text
        return R()
    monkeypatch.setattr(api, "run_watchdog", fake_run_watchdog)

    r = client.post("/watch/text", json={"url":"https://example.com/some", "online": False})
    assert r.status_code == 200
    assert "(Offline mode) URL provided:" in r.json()["summary"]

def test_watch_text_url_online(monkeypatch):
    # mock fetch to avoid network
    import ethics_engine.ui.app as app_mod
    monkeypatch.setattr(app_mod, "_fetch_url_text", lambda url, **_: "Fetched text from " + url)

    def fake_run_watchdog(text, k, stream, model):
        class R: label="MEDIUM"; overall_risk=0.5; signals=[]; related_incidents=[]; llm_summary=text
        return R()
    monkeypatch.setattr(api, "run_watchdog", fake_run_watchdog)

    r = client.post("/watch/text", json={"url":"https://example.com/page", "online": True})
    assert r.status_code == 200
    assert r.json()["summary"].startswith("Fetched text from")

def test_watch_file_image_ocr(monkeypatch):
    def fake_run_watchdog(text, k, stream, model):
        class R: label="LOW"; overall_risk=0.1; signals=[]; related_incidents=[]; llm_summary="sum"
        return R()
    monkeypatch.setattr(api, "run_watchdog", fake_run_watchdog)

    # small white PNG
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB",(50,20),"white").save(buf, format="PNG")
    buf.seek(0)

    # mock OCR to avoid Tesseract
    monkeypatch.setattr("pytesseract.image_to_string", lambda *a, **k: "ocr text", raising=False)

    files = {"file": ("t.png", buf, "image/png")}
    r = client.post("/watch/file", files=files, data={"k":"3","model":"llama3:8b","streaming":"false"})
    assert r.status_code == 200
    assert r.json()["label"] == "LOW"
    assert r.json()["risk"] == 0.1

def test_watch_file_text_upload(monkeypatch):
    def fake_run_watchdog(text, k, stream, model):
        class R: label="MEDIUM"; overall_risk=0.5; signals=[]; related_incidents=[]; llm_summary="sum"
        return R()
    monkeypatch.setattr(api, "run_watchdog", fake_run_watchdog)

    data = io.BytesIO(b"BREAKING: secret plan!")
    files = {"file": ("claim.txt", data, "text/plain")}
    r = client.post("/watch/file", files=files)
    assert r.status_code == 200
    assert r.json()["label"] == "MEDIUM"
