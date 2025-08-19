from __future__ import annotations
from fastapi import FastAPI
from pydantic import BaseModel
from ..analyze import analyze_use_case

app = FastAPI(title="EthicsBot API", version="0.1.0")

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
