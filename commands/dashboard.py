from collections import Counter

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import database
import utils
from enums import FindingStatus, Severity

SEVERITY_COLORS = {
    "info": "cyan", "low": "green", "medium": "yellow",
    "high": "red", "critical": "bold magenta",
}


def dashboard():
    """Show an overview of the active project."""
    project, targets, findings, notes, evidence = database.project_snapshot(utils.require_active_project())
    if project is None:
        utils.fail("Active project does not exist.")

    console = Console()
    overview = Text(f"{project['name']}\n")
    if project["description"]:
        overview.append(f"{project['description']}\n")
    overview.append(f"Targets: {len(targets)}  Findings: {len(findings)}  Notes: {notes}  Evidence: {evidence}")
    console.print(Panel(overview, title="Pentworks dashboard", expand=False))

    severity_counts = Counter(item["severity"] for item in findings)
    status_counts = Counter(item["status"] for item in findings)
    summary = Table()
    summary.add_column("Severity")
    summary.add_column("Findings", justify="right")
    summary.add_column("Status")
    summary.add_column("Findings", justify="right")
    for severity, status in zip(reversed(list(Severity)), list(FindingStatus) + [None]):
        summary.add_row(
            Text(severity.value, style=SEVERITY_COLORS[severity.value]), str(severity_counts[severity.value]),
            status.value if status else "", str(status_counts[status.value]) if status else "",
        )
    console.print(summary)

    if not findings:
        console.print("No findings yet.")
        return

    recent = Table(title="Recent findings")
    for column in ("ID", "Finding", "Target", "Severity", "Status", "Created (UTC)"):
        recent.add_column(column)
    for item in findings[:5]:
        recent.add_row(str(item["id"]), Text(item["name"]), Text(item["address"]),
                       Text(item["severity"], style=SEVERITY_COLORS[item["severity"]]),
                       item["status"], item["created_at"])
    console.print(recent)
