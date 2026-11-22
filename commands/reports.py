from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
import unicodedata
from urllib.parse import quote
from uuid import uuid4

import typer

import database
import utils
from enums import Severity
from services import storage

report = typer.Typer(no_args_is_help=True)


def markdown_text(value: str):
    # Escape Markdown punctuation and neutralize raw HTML and terminal controls.
    return "".join(
        char if char in "\n\t" or char == " " or char.isalnum()
        else " " if unicodedata.category(char).startswith("C")
        else f"\\{char}" if char.isascii()
        else char
        for char in value.replace("\r\n", "\n").replace("\r", "\n")
    )


def inline(value: str):
    return markdown_text(" ".join(value.split())) or "—"


def description(value: str | None):
    # Blockquote each line so indentation, line breaks and headings cannot alter the document structure.
    lines = markdown_text(value).split("\n") if value else ["—"]
    return ["", *(f"> {line.replace(chr(9), '    ')}{('  ' if line else '')}" for line in lines), ""]


def reference(item, resolve_path):
    label = inline(item["name"])
    try:
        file = resolve_path(item["file_path"])
    except FileNotFoundError:
        return f"{label} (file missing)"
    except (OSError, ValueError):
        return f"{label} (file unavailable)"
    relative = file.relative_to(storage.WORKSPACE_DIR).as_posix()
    return f"[{label}](../{quote(relative)})"


def note_references(lines, notes):
    if notes:
        lines.extend(["", "**Notes**", ""])
        lines.extend(f"- {reference(note, storage.resolve_note_path)}" for note in notes)


def render_report(project, targets, findings, notes, evidence, generated):
    by_severity = Counter(item["severity"] for item in findings)
    by_target = Counter(item["target_id"] for item in findings)
    evidence_by_finding = defaultdict(list)
    notes_by_scope = defaultdict(list)
    for item in evidence:
        evidence_by_finding[item["finding_id"]].append(item)
    for note in notes:
        notes_by_scope[note["target_id"], note["finding_id"]].append(note)

    lines = [f"# {inline(project['name'])}", "", "## Project description"]
    lines.extend(description(project["description"]))
    lines.extend([
        f"Generated: {generated:%Y-%m-%d %H:%M:%S} UTC", "",
        "## Executive summary", "",
        f"The project contains {len(targets)} targets, {len(findings)} findings, "
        f"{len(notes)} notes and {len(evidence)} evidence attachments.",
    ])
    note_references(lines, notes_by_scope[None, None])
    lines.extend(["", "## Target overview", ""])
    if not targets:
        lines.append("No targets recorded.")
    for target in targets:
        lines.extend([f"### {inline(target['address'])}", "",
                      f"Findings: {by_target[target['id']]}"])
        if target["description"]:
            lines.extend(description(target["description"]))
        note_references(lines, notes_by_scope[target["id"], None])
        lines.append("")

    lines.extend(["", "## Findings by severity", "", "| Severity | Count |", "| --- | ---: |"])
    lines.extend(f"| {severity.value} | {by_severity[severity.value]} |" for severity in reversed(list(Severity)))
    lines.extend(["", "## Detailed findings", ""])
    if not findings:
        lines.append("No findings recorded.")
    for finding in findings:
        lines.extend([
            f"### {inline(finding['name'])} (#{finding['id']})", "",
            f"- Target: {inline(finding['address'])}",
            f"- Severity: {inline(finding['severity'])}",
            f"- Status: {inline(finding['status'])}",
            f"- Created: {inline(finding['created_at'])} UTC",
        ])
        if finding["endpoint"]:
            lines.append(f"- Endpoint: {inline(finding['endpoint'])}")
        lines.extend(description(finding["description"]))
        attachments = evidence_by_finding[finding["id"]]
        if attachments:
            lines.extend(["**Evidence**", ""])
            for item in attachments:
                link = reference(item, storage.resolve_evidence_path)
                lines.append(f"- {link} (SHA-256: {inline(item['sha256'])})")
        note_references(lines, notes_by_scope[finding["target_id"], finding["id"]])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


@report.command("generate")
def generate_report():
    """Write an evidence-linked Markdown report for the active project."""
    project, targets, findings, notes, evidence = database.project_snapshot(
        utils.require_active_project(), include_references=True
    )
    if project is None:
        utils.fail("Active project does not exist.")

    generated = datetime.now(timezone.utc)
    content = render_report(project, targets, findings, notes, evidence, generated)
    folder = storage.REPORTS_DIR
    temporary = None
    try:
        destination = folder / f"project-{project['id']}-{generated:%Y%m%dT%H%M%SZ}-{uuid4().hex}.md"
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        # Reserve a unique name before publishing the complete file.
        with storage.new_file(destination, "x") as reservation:
            reservation.close()
            temporary.replace(destination)
    except OSError as exc:
        utils.fail(f"Unable to save report: {exc}")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    typer.echo(f"Report: {destination}")
