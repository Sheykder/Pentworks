import sqlite3
from pathlib import Path

import typer

import database
import utils
from services import storage

evidence = typer.Typer(no_args_is_help=True)


def require_finding(finding_id: int):
    target_id = utils.require_active_target()
    if not database.get_finding_by_id(target_id, finding_id):
        utils.fail("Finding not found in the active target.")


def require_evidence(evidence_id: int):
    project_id = utils.require_active_project()
    target_id = utils.require_active_target(project_id)
    item = database.get_evidence_in_context(project_id, target_id, evidence_id)
    if not item:
        utils.fail("Evidence not found in the active target.")
    return item


@evidence.command("add")
def add_evidence(source: Path, finding: int = typer.Option(..., "--finding")):
    """Copy an attachment into the workspace and record its SHA-256."""
    require_finding(finding)
    try:
        relative = storage.save_evidence_file(str(source))
    except (OSError, ValueError) as exc:
        utils.fail(f"Unable to copy evidence: {exc}")
    try:
        digest = storage.calculate_sha256(storage.resolve_evidence_path(relative))
        database.insert_evidence(finding, source.name, digest, relative)
    except (sqlite3.Error, OSError, ValueError) as exc:
        try:
            storage.delete_evidence_file(relative)
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as cleanup_error:
            typer.echo(f"Unable to clean up {relative!r}: {cleanup_error}", err=True)
            database.queue_file_deletion("evidence", relative)
        if isinstance(exc):
            raise
        utils.fail(f"Unable to add evidence: {exc}")
    typer.echo(f"Attached {source.name} to finding {finding}.")


@evidence.command("list")
def list_evidence(finding: int = typer.Option(..., "--finding")):
    """List attachments for a finding in the active target."""
    require_finding(finding)
    items = database.get_evidence(finding)
    if not items:
        typer.echo("No evidence found.")
    for evidence_id, _, name, sha256, _, _ in items:
        typer.echo(f"[{evidence_id}] {name} | {sha256}")


@evidence.command("show")
def show_evidence(evidence_id: int):
    """Display attachment metadata and verify the stored copy."""
    evidence_id, finding_id, name, sha256, relative, created = require_evidence(evidence_id)
    try:
        digest = storage.calculate_sha256(storage.resolve_evidence_path(relative))
        integrity = "verified" if digest == sha256 else "SHA-256 mismatch"
    except FileNotFoundError:
        integrity = "missing"
    except (OSError, ValueError) as exc:
        integrity = f"unavailable ({exc})"

    typer.echo(f"ID: {evidence_id}\nName: {name}\nFinding: {finding_id}\nSHA-256: {sha256}"
               f"\nCreated: {created}\nPath: {relative}\nIntegrity: {integrity}")
    if integrity != "verified":
        raise typer.Exit(1)


@evidence.command("delete")
def delete_evidence(evidence_id: int, yes: bool = typer.Option(False, "--yes", "-y")):
    """Remove the stored attachment and its metadata."""
    evidence_id, finding_id, name, _, _, _ = require_evidence(evidence_id)
    utils.confirm_delete(f"evidence '{name}'", yes)
    if not database.delete_evidence(finding_id, evidence_id):
        utils.fail("Evidence not found.")
    utils.finish_delete(f"Evidence {evidence_id} was deleted.")
