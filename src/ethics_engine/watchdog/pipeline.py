# ethics_engine/watchdog/pipeline.py
from __future__ import annotations
import logging, secrets, time
from typing import List, Optional

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from ethics_engine.store import get_vectorstore
from ethics_engine.prompts.watchdog import build_watchdog_summary_prompt
from ethics_engine.watchdog.schemas import Claim, Evidence, Signal, WatchReport
from ethics_engine.watchdog.features import heuristic_scores
from ethics_engine.watchdog.extract import extract_claims 
from ethics_engine.llm import get_llm
from ethics_engine.telemetry.promptlog import log_prompt

logger = logging.getLogger("ethicsbot.watchdog.pipeline")
tracer = trace.get_tracer("ethicsbot.watchdog")

def _score_to_label(x: float) -> str:
    if x >= 0.7: return "Likely Misinfo"
    if x >= 0.4: return "Needs Verification"
    return "Low"

def _coerce_text(x) -> str:
    """Best-effort: turn common LLM outputs into a plain string."""
    if x is None:
        return ""
    if isinstance(x, str):
        return x

    # LangChain message-like objects
    content = getattr(x, "content", None)
    if content is not None:
        # content can be str or a list of parts (e.g., [{"type":"text","text":"..."}])
        if isinstance(content, str):
            return content
        if isinstance(content, (list, tuple)):
            parts = []
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    parts.append(str(part["text"]))
                else:
                    parts.append(str(part))
            return "\n".join(parts)
        return str(content)

    # Sequence → join
    if isinstance(x, (list, tuple)):
        return "".join(_coerce_text(i) for i in x)

    # Dict with content
    if isinstance(x, dict) and "content" in x:
        return _coerce_text(x["content"])

    # Fallback
    return str(x)


def run_watchdog(
    text: str,
    *,
    k: int = 3,
    stream: bool = True,
    model: str | None = None
) -> WatchReport:
    """
    Run the misinformation watchdog pipeline with tracing + structured logs.
    """
    run_id = secrets.token_hex(4)
    t0 = time.perf_counter()

    with tracer.start_as_current_span(
        "watchdog.run",
        attributes={"watchdog.k": k, "watchdog.model": model or "", "watchdog.stream": stream},
    ) as parent_span:
        parent_span.set_attribute("watchdog.run_id", run_id)
        logger.info("watchdog.run.start", extra={"run_id": run_id, "stage": "start"})

        try:
            # 1) claims -----------------------------------------------------------------
            with tracer.start_as_current_span("claims") as span:
                s0 = time.perf_counter()
                claims: List[Claim] = extract_claims(text)
                span.set_attribute("claims.count", len(claims))
                logger.info(
                    "claims.done",
                    extra={"run_id": run_id, "stage": "claims", "elapsed_ms": int((time.perf_counter()-s0)*1000),
                           "claims.count": len(claims)},
                )

            # 2) retrieve similar incidents ---------------------------------------------
            with tracer.start_as_current_span("retrieve") as span:
                s0 = time.perf_counter()
                vs = get_vectorstore()
                sims = vs.similarity_search(text, k=k) if vs else []
                related = [Evidence(snippet=d.page_content, source=(d.metadata or {}).get("source")) for d in sims]
                span.set_attribute("retrieve.count", len(related))
                logger.info(
                    "retrieve.done",
                    extra={"run_id": run_id, "stage": "retrieve", "elapsed_ms": int((time.perf_counter()-s0)*1000),
                           "retrieve.count": len(related)},
                )

            # 3) heuristics --------------------------------------------------------------
            with tracer.start_as_current_span("heuristics") as span:
                s0 = time.perf_counter()
                hs = heuristic_scores(text)
                signals = [Signal(name=k, score=v, details=f"{k}={v:.2f}") for k, v in hs.items()]
                base = max(hs.values()) if hs else 0.0
                boost = 0.1 * len(related)  # more similar incidents → higher risk of pattern
                overall = max(0.0, min(1.0, base + min(0.3, boost)))
                span.set_attribute("signals.count", len(signals))
                span.set_attribute("risk.base", base)
                span.set_attribute("risk.boost", boost)
                span.set_attribute("risk.overall", overall)
                logger.info(
                    "heuristics.done",
                    extra={"run_id": run_id, "stage": "heuristics", "elapsed_ms": int((time.perf_counter()-s0)*1000),
                           "signals.count": len(signals), "risk.base": round(base,3),
                           "risk.boost": round(boost,3), "risk.overall": round(overall,3)},
                )

            # 4) LLM reasoning summary ---------------------------------------------------
            with tracer.start_as_current_span("llm.summary", attributes={"model": model or "", "stream": stream}) as span:
                s0 = time.perf_counter()
                prompt = build_watchdog_summary_prompt(
                    content=text, claims=claims, signals=signals, related_incidents=related
                )

                log_prompt(prompt, run_id=run_id, stage="llm", claims_cnt=len(claims), signals_cnt=len(signals), incidents_cnt=len(related), span=span)

                if stream:
                    llm = get_llm(model=model, streaming=True, callbacks=[StreamingStdOutCallbackHandler()], temperature=0.2)
                    raw = llm.invoke(prompt)
                    llm_text = ""  # already streamed
                else:
                    llm = get_llm(model=model, temperature=0.2)
                    raw = llm.invoke(prompt)
                    llm_text = _coerce_text(raw)

                logger.debug(
                    "llm.invoke.return_type",
                    extra={"run_id": run_id, "stage": "llm", "type": type(llm_text).__name__}
                )

                span.set_attribute("summary.len", len(llm_text))
                logger.info("llm.summary.done", extra={
                    "run_id": run_id, "stage": "llm", "elapsed_ms": int((time.perf_counter()-s0)*1000),
                })

            # 5) Aggregate final report ---------------------------------------------------
            with tracer.start_as_current_span("aggregate") as span:
                s0 = time.perf_counter()
                label = _score_to_label(overall)
                report = WatchReport(
                    overall_risk=overall,
                    label=label,
                    claims=claims,
                    signals=signals,
                    related_incidents=related,
                    llm_summary=llm_text,
                )
                span.set_attribute("label", label)
                logger.info(
                    "aggregate.done",
                    extra={"run_id": run_id, "stage": "aggregate", "elapsed_ms": int((time.perf_counter()-s0)*1000),
                           "label": label},
                )

            logger.info(
                "watchdog.run.end",
                extra={"run_id": run_id, "stage": "end", "elapsed_ms": int((time.perf_counter()-t0)*1000),
                       "label": report.label, "risk": round(report.overall_risk, 2)},
            )
            return report

        except Exception as e:
            logger.exception("watchdog.run.error", extra={"run_id": run_id})
            parent_span.record_exception(e)
            parent_span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
