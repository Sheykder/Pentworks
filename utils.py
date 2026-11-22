import typer

import database
from services import storage


def fail(message: str):
    typer.echo(message, err=True)
    raise typer.Exit(1)


def require_active_project():
    project_id = database.get_active_project()
    if project_id is None:
        fail("No active project. Use 'project use ID'.")
    if not database.get_project_by_id(project_id):
        fail("Active project does not exist.")
    return project_id


def require_active_target(project_id: int | None = None):
    if project_id is None:
        project_id = require_active_project()
    target_id = database.get_active_target()
    if target_id is None:
        fail("No active target. Use 'target use ID'.")
    if not database.get_target_by_id(target_id, project_id):
        fail("Active target does not exist in the active project.")
    return target_id


def confirm_delete(label: str, yes: bool):
    if not yes and not typer.confirm(f"Delete {label}?"):
        typer.echo("Cancelled")
        raise typer.Exit()


def clean_pending_files():
    failed = False
    for kind, path in database.pending_file_deletions():
        delete_file = {"note": storage.delete_note_file, "evidence": storage.delete_evidence_file}[kind]
        try:
            delete_file(path)
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            typer.echo(f"Cleanup pending for {kind} file {path!r}: {exc}", err=True)
            failed = True
            continue
        database.finish_file_deletion(kind, path)
    return not failed


def finish_delete(message: str):
    typer.echo(message)
    if not clean_pending_files():
        fail("Some files could not be removed. Pentworks will retry on the next command.")
