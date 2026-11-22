from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
import hashlib
import os
import shlex
import subprocess
import shutil
import stat

WORKSPACE_DIR = Path(os.environ.get("PENTWORKS_HOME") or Path.home() / ".pentworks").expanduser().resolve()
NOTES_DIR = WORKSPACE_DIR / "notes"
EVIDENCE_DIR = WORKSPACE_DIR / "evidence"
REPORTS_DIR = WORKSPACE_DIR / "reports"

def resolve_stored_path(file_path: str, directory: Path):
    relative = Path(file_path)
    file = WORKSPACE_DIR / relative
    if relative.anchor or file.parent != directory or file.name in (".", ".."):
        raise ValueError("Invalid stored path")
    if os.name == "nt" and os.path.isreserved(file.name):
        raise ValueError("Invalid stored path")
    if file.resolve().parent != directory or file.is_symlink():
        raise ValueError("Invalid stored path")
    if not stat.S_ISREG(file.stat().st_mode):
        raise ValueError("Stored path is not a regular file")
    return file


def resolve_note_path(file_path: str):
    return resolve_stored_path(file_path, NOTES_DIR)


def resolve_evidence_path(file_path: str):
    return resolve_stored_path(file_path, EVIDENCE_DIR)


def init_storage():
    directories = [WORKSPACE_DIR, NOTES_DIR, EVIDENCE_DIR, REPORTS_DIR]
    for directory in directories:
        if directory.resolve() != directory:
            raise OSError(f"Workspace directory is redirected: {directory}")
        directory.mkdir(parents=True, exist_ok=True)

@contextmanager
def new_file(path: Path, mode: str, **options):
    stream = path.open(mode, **options)
    try:
        with stream:
            yield stream
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def create_note_file(name: str, content: str = ""):
    file = NOTES_DIR / f"{uuid4()}.md"
    with new_file(file, "x", encoding="utf-8") as output:
        output.write(f"# {name}\n\n{content}")
    return file.relative_to(WORKSPACE_DIR).as_posix()


def read_note_file(file_path: str):
    file = resolve_note_path(file_path)
    return file.read_text(encoding="utf-8")

def delete_note_file(file_path: str):
    file = resolve_note_path(file_path)
    file.unlink()

def edit_note_file(file_path: str):
    file = resolve_note_path(file_path)
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        editor = "notepad.exe" if os.name == "nt" else "vi"
    if Path(editor).is_file():
        command = [editor]
    elif os.name == "nt":
        command = [arg[1:-1] if arg.startswith('"') and arg.endswith('"') else arg
                   for arg in shlex.split(editor, posix=False)]
    else:
        command = shlex.split(editor)
    if not command:
        raise ValueError("Editor command is empty")
    subprocess.run([*command, str(file)], check=True)
    
def save_evidence_file(source_path: str):
    source = Path(source_path).expanduser()
    if(not source.is_file()):
        raise FileNotFoundError("Source file not found")

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4()}{source.suffix}"
    if os.name == "nt" and os.path.isreserved(filename):
        raise ValueError("Unsupported evidence filename")
    destination = EVIDENCE_DIR / filename
    with source.open("rb") as source_file, new_file(destination, "xb") as output:
        shutil.copyfileobj(source_file, output)
    return destination.relative_to(WORKSPACE_DIR).as_posix()


def calculate_sha256(file: Path):
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def delete_evidence_file(file_path: str):
    resolve_evidence_path(file_path).unlink()
