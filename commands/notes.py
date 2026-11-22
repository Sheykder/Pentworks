
import typer
import database
import utils
from pathlib import Path
from services import storage

note = typer.Typer()

def get_note(note_id: int):
    project_id = utils.require_active_project()
    if(not project_id):
        return None

    result = database.get_note_by_id(project_id, note_id)
    if(not result):
        print("Note doesn't exist")
        return None

    return result

@note.command("add")
def note_add(
    name: str,
    project: bool = typer.Option(False, "--project"),
    target: bool = typer.Option(False, "--target"),
    finding: int | None = typer.Option(None, "--finding")
):
    if(project + target + (finding is not None) != 1):
        print("Choose exactly one note level")
        return

    if(not name.strip()):
        print("Note name cannot be empty")
        return

    project_id = utils.require_active_project()
    if(not project_id):
        return

    target_id = None
    if(target or finding is not None):
        target_id = utils.require_active_target()
        if(not target_id):
            return

    if(finding is not None):
        if(not database.get_finding_by_id(target_id, finding)):
            print("Finding doesn't exist")
            return

    path = storage.create_note_file(name)

    try:
        database.insert_note(project_id, name, path, target_id, finding)
    except Exception as e:
        try:
            storage.delete_note_file(path)
        except OSError as cleanup_error:
            print(f"Failed to clean up note file: {cleanup_error}")
        print(f"Failed to create note: {e}")
        return

    print("Note was successfully added")

@note.command("list")
def note_list(
    target: bool = typer.Option(False, "--target"),
    finding: int | None = typer.Option(None, "--finding")
):
    if(target and finding is not None):
        print("Choose only one filter")
        return

    project_id = utils.require_active_project()
    if(not project_id):
        return

    target_id = None
    if(target or finding is not None):
        target_id = utils.require_active_target()
        if(not target_id):
            return

    if(finding is not None):
        if(not database.get_finding_by_id(target_id, finding)):
            print("Finding doesn't exist")
            return

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
    if(not item):
        return

    note_id, project_id, target_id, finding_id, name, file_path, created_at, updated_at = item

    try:
        content = storage.read_note_file(file_path)
    except (OSError, ValueError) as e:
        print(f"Failed to read note: {e}")
        return

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
    if(not item):
        return

    file_path = item[5]

    try:
        storage.edit_note_file(file_path)
    except (OSError, ValueError) as e:
        print(f"Failed to edit note: {e}")
        return

    project_id = item[1]
    database.touch_note(project_id, note_id)
    print("Note was successfully edited")

@note.command("rename")
def note_rename(note_id: int, name: str):
    if(not name.strip()):
        print("Note name cannot be empty")
        return

    item = get_note(note_id)
    if(not item):
        return

    project_id = item[1]
    database.update_note(project_id, note_id, name)
    print("Note was successfully renamed")

@note.command("delete")
def note_delete(
    note_id: int,
    yes: bool = typer.Option(False, "--yes", "-y")
):
    item = get_note(note_id)
    if(not item):
        return

    if(not yes):
        confirmed = typer.confirm(f"Delete note '{item[4]}'?")
        if(not confirmed):
            print("Cancelled")
            return

    project_id = item[1]
    file_path = item[5]

    database.delete_note(project_id, note_id)

    try:
        storage.delete_note_file(file_path)
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        print(f"Note deleted from database, but file cleanup failed: {e}")
        return

    print("Note was successfully deleted")

@note.command("search")
def note_search(query: str):
    project_id = utils.require_active_project()
    if(not project_id):
        return

    if(not query.strip()):
        print("Search query cannot be empty")
        return

    notes = database.get_notes(project_id)
    matches = []

    for item in notes:
        note_id, _, target_id, finding_id, name, file_path, _, _ = item

        try:
            content = storage.read_note_file(file_path)
        except (OSError, ValueError) as e:
            print(f"Skipping note [{note_id}]: {e}")
            continue

        if(query.casefold() in name.casefold() or query.casefold() in content.casefold()):
            matches.append((note_id, name, target_id, finding_id))

    if(not matches):
        print("No matching notes")
        return

    for note_id, name, target_id, finding_id in matches:
        level = "finding" if finding_id is not None else "target" if target_id is not None else "project"
        print(f"[{note_id}] {name} | {level}")
