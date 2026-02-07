"""Presenters – format use-case responses for terminal or JSON output."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from research_toolkit.application.use_cases.doctor_checks import DoctorResponse
from research_toolkit.application.use_cases.list_resources import ListResponse
from research_toolkit.application.use_cases.query_library import QueryResponse
from research_toolkit.application.use_cases.review_artifact import ReviewResponse
from research_toolkit.application.use_cases.run_search import RunSearchResponse
from research_toolkit.application.use_cases.summarize_resource import SummarizeResponse
from research_toolkit.domain.entities import Resource

console = Console()


def _json_out(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------
def present_doctor(resp: DoctorResponse, *, as_json: bool = False) -> None:
    if as_json:
        _json_out({"checks": [{"name": c.name, "passed": c.passed, "message": c.message} for c in resp.checks]})
        return

    table = Table(title="Doctor Checks", show_lines=True)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details")
    for c in resp.checks:
        status = "[green]PASS[/green]" if c.passed else "[red]FAIL[/red]"
        table.add_row(c.name, status, c.message)
    console.print(table)
    if resp.all_passed:
        console.print("\n[bold green]All checks passed![/bold green]")
    else:
        console.print("\n[bold red]Some checks failed. See above.[/bold red]")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def present_search(resp: RunSearchResponse, *, as_json: bool = False) -> None:
    if as_json:
        _json_out({
            "session_id": resp.session.session_id,
            "resources": [r.to_dict() for r in resp.resources],
            "skipped": resp.skipped,
        })
        return

    console.print(f"\n[bold]Session:[/bold] {resp.session.session_id}")
    console.print(f"[bold]Resources stored:[/bold] {len(resp.resources)}  |  Skipped: {resp.skipped}\n")

    if resp.resources:
        table = Table(show_lines=True)
        table.add_column("ID", style="cyan")
        table.add_column("Title")
        table.add_column("URL", style="dim")
        for r in resp.resources:
            table.add_row(str(r.id), r.title[:60], str(r.url)[:80])
        console.print(table)


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------
def present_ingest(resource: Resource, already_existed: bool, *, as_json: bool = False) -> None:
    if as_json:
        _json_out({"resource": resource.to_dict(), "already_existed": already_existed})
        return

    if already_existed:
        console.print(f"[yellow]Already exists:[/yellow] [{resource.id}] {resource.title}")
    else:
        console.print(f"[green]Ingested:[/green] [{resource.id}] {resource.title}")
    console.print(f"  URL: {resource.url}")
    console.print(f"  Captured: {resource.captured_at}")


# ---------------------------------------------------------------------------
# Summarize
# ---------------------------------------------------------------------------
def present_summarize(resp: SummarizeResponse, *, as_json: bool = False) -> None:
    if as_json:
        _json_out({
            "resource": resp.resource.to_dict(),
            "summary": resp.summary.to_dict(),
        })
        return

    console.print(f"\n[bold]Summary of [{resp.resource.id}]: {resp.resource.title}[/bold]\n")
    console.print(resp.summary.text)
    console.print("\n[bold]Citations:[/bold]")
    for c in resp.summary.citations:
        console.print(f"  - [{c.resource_id}] {c.resource_title}")
        console.print(f"    URL: {c.url}")
        console.print(f"    Local: {c.local_path}")
        console.print(f"    Captured: {c.captured_at}")


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------
def present_query(resp: QueryResponse, *, as_json: bool = False) -> None:
    if as_json:
        _json_out({
            "answer": resp.answer.to_dict(),
            "sources": [r.to_dict() for r in resp.sources],
        })
        return

    console.print("\n[bold]Answer:[/bold]\n")
    console.print(resp.answer.text)
    if resp.answer.citations:
        console.print("\n[bold]Sources:[/bold]")
        for c in resp.answer.citations:
            console.print(f"  [{c.resource_id}] {c.resource_title}")
            console.print(f"    URL: {c.url}  |  Local: {c.local_path}")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
def present_list(resp: ListResponse, *, as_json: bool = False) -> None:
    if as_json:
        _json_out({"resources": [r.to_dict() for r in resp.resources], "total": resp.total})
        return

    console.print(f"\n[bold]Library: {resp.total} resources[/bold]\n")
    if not resp.resources:
        console.print("[dim]No resources stored yet. Use 'tool search' or 'tool ingest' to add some.[/dim]")
        return

    table = Table(show_lines=True)
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("URL", style="dim")
    table.add_column("Captured", style="dim")
    for r in resp.resources:
        table.add_row(str(r.id), r.title[:50], str(r.url)[:60], str(r.captured_at)[:19])
    console.print(table)


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------
def present_review(resp: ReviewResponse, *, as_json: bool = False, as_md: bool = False) -> None:
    report = resp.report
    if as_json:
        _json_out(resp.report_json)
        return

    if as_md:
        from research_toolkit.application.use_cases.review_artifact import ReviewArtifact
        print(ReviewArtifact._report_to_markdown(report))
        return

    # Rich table view (default)
    status = "[green bold]PASS[/green bold]" if report.passed else "[red bold]FAIL[/red bold]"
    console.print(f"\n[bold]Artifact Review[/bold]  Score: {report.overall_score}/100  {status}")
    if report.artifact:
        console.print(f"  File: {report.artifact.filename}  ({report.artifact.mime_type})")
    console.print(f"  Model: {report.model}  |  Stored: {resp.review_dir}")
    console.print(f"\n[bold]Summary:[/bold] {report.summary}\n")

    if report.issues:
        table = Table(title="Issues", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Severity", width=10)
        table.add_column("Title")
        table.add_column("Location", style="dim")
        table.add_column("Fix")
        for i, issue in enumerate(report.issues, 1):
            sev_color = {
                "critical": "red bold",
                "major": "yellow",
                "minor": "cyan",
                "suggestion": "dim",
            }.get(issue.severity.value, "white")
            table.add_row(
                str(i),
                f"[{sev_color}]{issue.severity.value.upper()}[/{sev_color}]",
                issue.title,
                issue.location[:40],
                issue.fix[:60],
            )
        console.print(table)

    if report.next_steps:
        console.print("\n[bold]Next Steps:[/bold]")
        for step in report.next_steps:
            console.print(f"  • {step}")
    console.print()
