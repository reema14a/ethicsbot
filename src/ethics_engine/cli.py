from __future__ import annotations
import argparse
from rich import print
from .store import seed_from_jsonl
from .analyze import analyze_use_case
from .watchdog.pipeline import run_watchdog
from .watchdog.report import print_report

def _cmd_seed(file: str) -> None:
    n = seed_from_jsonl(file)
    print(f"[green]Seeded {n} incidents into Chroma[/green]")

def _cmd_run(q: str, k: int, stream: bool, model: str | None, show_incidents: bool) -> None:
    print("[bold]Analyzing Use Case[/bold]:", q, "\n")
    if show_incidents:
        from .store import get_vectorstore
        vs = get_vectorstore()
        sims = vs.similarity_search(q, k=k)
        print("[dim]Retrieved incidents:[/dim]")
        for i, d in enumerate(sims, 1):
            print(f"[dim]{i}.[/dim] {d.page_content}")

    out = analyze_use_case(q, k=k, stream=stream, model=model)
    if not stream:
        print(out)

def _cmd_watch(text: str, k: int, model: str | None, no_stream: bool) -> None:
    print("[bold]Running Watchdog[/bold]\n")
    rep = run_watchdog(text, k=k, stream=not no_stream, model=model)
    print_report(rep)

def main():
    ap = argparse.ArgumentParser("Ethics Engine CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed", help="Seed ChromaDB from a JSONL incidents file")
    p_seed.add_argument("--file", default="data/incidents/seed_incidents.jsonl")

    p_run = sub.add_parser("run", help="Analyze an AI use case with retrieved incidents")
    p_run.add_argument("--q", required=True, help="Describe your AI use case")
    p_run.add_argument("--k", type=int, default=3, help="Top-K similar incidents to fetch")
    p_run.add_argument("--no-stream", action="store_true", help="Disable token streaming")
    p_run.add_argument("--model", help="Override model name (e.g., llama3:8b)")
    p_run.add_argument("--show-incidents", action="store_true", help="Print retrieved incidents before analysis")

    p_watch = sub.add_parser("watch", help="Assess text for likely misinformation")
    p_watch.add_argument("--text", required=True, help="Paste the text to assess (quotes recommended)")
    p_watch.add_argument("--k", type=int, default=3)
    p_watch.add_argument("--model", help="Override model (e.g., llama3:8b)")
    p_watch.add_argument("--no-stream", action="store_true")

    args = ap.parse_args()

    if args.cmd == "seed":
        _cmd_seed(args.file)
    elif args.cmd == "run":
        stream = not args.no_stream  # default True unless --no-stream is provided
        _cmd_run(args.q, args.k, stream, args.model, args.show_incidents)
    elif args.cmd == "watch":
        _cmd_watch(args.text, args.k, args.model, args.no_stream)
