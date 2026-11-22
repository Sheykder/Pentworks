from pathlib import Path
from uuid import uuid4
import os
import subprocess
import shutil

WORKSPACE_DIR = Path.home() / ".pentworks"
NOTES_DIR = WORKSPACE_DIR / "notes"
EVIDENCE_DIR = WORKSPACE_DIR / "evidence"
REPORTS_DIR = WORKSPACE_DIR / "reports"

def resolve_note_path(file_path: str):
    file = WORKSPACE_DIR / file_path
    file = file.resolve()
    if(not file.is_relative_to(NOTES_DIR.resolve())):
        raise ValueError("Invalid note path")
    
    if(not file.is_file()):
        raise FileNotFoundError("Note file not found")

    return file

def resolve_evidence_path(file_path: str):
    file = WORKSPACE_DIR / file_path
    file = file.resolve()
    if(not file.is_relative_to(EVIDENCE_DIR.resolve())):
        raise ValueError("Invalid evidence path")
    
    if(not file.is_file()):
        raise FileNotFoundError("Evidence file not found")

    return file

def init_storage():
    directories = [WORKSPACE_DIR, NOTES_DIR, EVIDENCE_DIR, REPORTS_DIR]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def create_note_file(name: str, content: str = ""):
    filename = f"{uuid4()}.md"
    file = NOTES_DIR / filename
    file.write_text(f"# {name}\n\n{content}", encding="utf-8")
    return str(file.relative_to(WORKSPACE_DIR))

def read_note_file(file_path: str):
    file = resolve_note_path(file_path)
    return file.read_text(encoding="utf-8")

def delete_note_file(file_path: str):
    file = resolve_note_path(file_path)
    file.unlink()

def edit_note_file(file_path: str):
    file = resolve_note_path(file_path)
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(file)], check=True)
    
def save_evidence_file(source_path: str):
    source = Path(source_path).expanduser()
    if(not source.is_file()):
        raise FileNotFoundError("Source file not found")

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4()}{source.suffix}"
    destination = EVIDENCE_DIR / filename
    shutil.copy2(source, destination)

    return str(destination.relative_to(WORKSPACE_DIR))





