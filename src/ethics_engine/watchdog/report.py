from __future__ import annotations
from rich.table import Table
from rich.console import Console
from .schemas import WatchReport

def print_report(rep: WatchReport) -> None:
    console = Console()

    console.rule(f"[bold]Watchdog Assessment: {rep.label} ({rep.overall_risk:.2f})[/bold]")

    if rep.claims:
        t = Table(title="Claims (extracted)")
        t.add_column("#"); t.add_column("Claim")
        for i, c in enumerate(rep.claims, 1):
            t.add_row(str(i), c.text)
        console.print(t)

    t2 = Table(title="Signals")
    t2.add_column("Signal"); t2.add_column("Score"); t2.add_column("Details")
    for s in rep.signals:
        t2.add_row(s.name, f"{s.score:.2f}", s.details)
    console.print(t2)

    if rep.related_incidents:
        t3 = Table(title="Related Incidents (similar patterns)")
        t3.add_column("#"); t3.add_column("Snippet"); t3.add_column("Source")
        for i, e in enumerate(rep.related_incidents, 1):
            src = e.source or "-"
            t3.add_row(str(i), e.snippet, src)
        console.print(t3)

    if rep.llm_summary:
        console.rule("[bold]Summary & Next Steps[/bold]")
        console.print(rep.llm_summary)
