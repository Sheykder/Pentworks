import sqlite3
import subprocess

import typer

import database
import utils
from services import storage

note = typer.Typer()

def get_note(note_id: int):
    project_id = utils.require_active_project()

    result = database.get_note_by_id(project_id, note_id)
    if(not result):
        utils.fail("Note doesn't exist")

    return result

@note.command("add")
def note_add(
    name: str,
    project: bool = typer.Option(False, "--project"),
    target: bool = typer.Option(False, "--target"),
    finding: int | None = typer.Option(None, "--finding")
):
    if(project + target + (finding is not None) != 1):
        utils.fail("Choose exactly one note level")

    if(not name.strip()):
        utils.fail("Note name cannot be empty")

    project_id = utils.require_active_project()

    target_id = None
    if(target or finding is not None):
        target_id = utils.require_active_target(project_id)

    if(finding is not None):
        if(not database.get_finding_by_id(target_id, finding)):
            utils.fail("Finding doesn't exist")

    try:
        path = storage.create_note_file(name)
    except OSError as exc:
        utils.fail(f"Failed to create note file: {exc}")

    try:
        database.insert_note(project_id, name, path, target_id, finding)
    except sqlite3.Error as e:
        try:
            storage.delete_note_file(path)
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as cleanup_error:
            typer.echo(f"Failed to clean up note file: {cleanup_error}", err=True)
            database.queue_file_deletion("note", path)
        if isinstance(e):
            raise
        utils.fail(f"Failed to create note: {e}")

    print("Note was successfully added")

@note.command("list")
def note_list(
    target: bool = typer.Option(False, "--target"),
    finding: int | None = typer.Option(None, "--finding")
):
    if(target and finding is not None):
        utils.fail("Choose only one filter")

    project_id = utils.require_active_project()

    target_id = None
    if(target or finding is not None):
        target_id = utils.require_active_target(project_id)

    if(finding is not None):
        if(not database.get_finding_by_id(target_id, finding)):
            utils.fail("Finding doesn't exist")

    notes = database.get_notes(project_id, target_id, finding)
    if(not notes):
        print("No notes found")
        return

    for item in notes:
        note_id, project_id, target_id, finding_id, name, file_path, created_at, updated_at = item
        level = "finding" if finding_id is not None else "target" if target_id is not None else "project"
        print(f"[{note_id}] {name} | {level} | {updated_at}")

@note.command("show")
def note_show(note_id: int):
    item = get_note(note_id)

    note_id, project_id, target_id, finding_id, name, file_path, created_at, updated_at = item

    try:
        content = storage.read_note_file(file_path)
    except (OSError, ValueError) as e:
        utils.fail(f"Failed to read note: {e}")

    print(f"ID: {note_id}")
    print(f"Name: {name}")
    print(f"Project ID: {project_id}")
    print(f"Target ID: {target_id}")
    print(f"Finding ID: {finding_id}")
    print(f"Created: {created_at}")
    print(f"Updated: {updated_at}")
    print()
    print(content)

@note.command("edit")
def note_edit(note_id: int):
    item = get_note(note_id)

    file_path = item[5]

    try:
        storage.edit_note_file(file_path)
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        utils.fail(f"Failed to edit note: {e}")

    project_id = item[1]
    database.touch_note(project_id, note_id)
    print("Note was successfully edited")

@note.command("rename")
def note_rename(note_id: int, name: str):
    if(not name.strip()):
        utils.fail("Note name cannot be empty")

    item = get_note(note_id)

    project_id = item[1]
    if not database.update_note(project_id, note_id, name):
        utils.fail("Note doesn't exist")
    print("Note was successfully renamed")

@note.command("delete")
def note_delete(
    note_id: int,
    yes: bool = typer.Option(False, "--yes", "-y")
):
    item = get_note(note_id)

    utils.confirm_delete(f"note '{item[4]}'", yes)
    if not database.delete_note(item[1], note_id):
        utils.fail("Note doesn't exist")
    utils.finish_delete("Note was successfully deleted")


@note.command("search")
def note_search(query: str):
    project_id = utils.require_active_project()

    if(not query.strip()):
        utils.fail("Search query cannot be empty")

    notes = database.get_notes(project_id)
    matches = []

    for item in notes:
        note_id, _, target_id, finding_id, name, file_path, _, _ = item

        try:
            content = storage.read_note_file(file_path)
        except (OSError, ValueError) as e:
            typer.echo(f"Skipping note [{note_id}]: {e}", err=True)
            continue

        if(query.casefold() in name.casefold() or query.casefold() in content.casefold()):
            matches.append((note_id, name, target_id, finding_id))

    if(not matches):
        print("No matching notes")
        return

    for note_id, name, target_id, finding_id in matches:
        level = "finding" if finding_id is not None else "target" if target_id is not None else "project"
        print(f"[{note_id}] {name} | {level}")
