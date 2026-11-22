import hashlib
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path

import pytest
from typer.testing import CliRunner

import database
from main import app
from services import storage

runner = CliRunner()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    folder = tmp_path / "workspace"
    monkeypatch.setenv("PENTWORKS_HOME", str(folder))
    monkeypatch.delenv("PENTWORKS_DB", raising=False)
    monkeypatch.setattr(database, "WORKSPACE_DIR", folder)
    monkeypatch.setattr(storage, "WORKSPACE_DIR", folder)
    for name in ("NOTES", "EVIDENCE", "REPORTS"):
        monkeypatch.setattr(storage, f"{name}_DIR", folder / name.lower())
    return folder


def cli(*args, code=0, input=None):
    result = runner.invoke(app, args, input=input, terminal_width=110)
    assert result.exit_code == code, (result.output, result.exception)
    if code:
        assert "Traceback" not in result.output
    return result.output


def setup_project():
    cli("project", "create", "Demo")
    cli("project", "use", "1")


def setup_finding():
    setup_project()
    cli("target", "add", "demo.example")
    cli("target", "use", "1")
    cli("finding", "add", "Finding", "high", "--endpoint", "/example",
        "--description", "Line one\n<script>alert(1)</script>\n# Line three")


def create_source(tmp_path, name="review (1).png"):
    source = tmp_path / name
    source.write_bytes(b"attachment\x00")
    return source


def test_help_and_context_errors(workspace):
    assert "dashboard" in cli("--help")
    assert not workspace.exists()
    assert "No active project" in cli("dashboard", code=1)
    assert "No active project" in cli("report", "generate", code=1)
    assert "No active project" in cli("target", "add", "example", code=1)
    assert "not found" in cli("project", "show", "123", code=1).lower()
    assert "empty" in cli("project", "create", " ", code=1)
    setup_project()
    assert "No active target" in cli("finding", "list", code=1)


def test_project_target_finding_workflow(workspace):
    setup_finding()
    assert "Demo" in cli("project", "list")
    assert "Demo" in cli("project", "status")
    assert "demo.example" in cli("target", "status")
    assert "high" in cli("finding", "list")
    assert "confirmed" in cli("finding", "status", "1", "confirmed")
    assert "/example" in cli("finding", "show", "1")
    cli("finding", "add", "Bad", "severe", code=2)
    cli("finding", "status", "1", "unknown", code=2)

    cli("project", "create", "Other project")
    cli("project", "use", "2")
    assert database.get_active_target() is None
    assert "not found" in cli("target", "show", "1", code=1).lower()
    cli("target", "use", "1", code=1)

    cli("project", "use", "1")
    cli("target", "use", "1")
    assert "Cancelled" in cli("project", "delete", "1", input="n\n")
    assert database.get_project_by_id(1)
    cli("project", "delete", "1", input="y\n")
    assert database.get_project_by_id(1) is None
    assert database.get_active_project() is None
    assert database.get_active_target() is None
    assert database.get_project_by_id(2)


def test_notes_crud_and_editor_errors(workspace, monkeypatch):
    setup_finding()
    cli("note", "add", "Assessment", "--project")
    cli("note", "add", "Target note", "--target")
    cli("note", "add", "Заметка", "--finding", "1")
    cli("note", "add", "Bad scope", "--project", "--target", code=1)
    assert "Заметка" in cli("note", "list", "--finding", "1")
    assert "Assessment" not in cli("note", "list", "--target")
    assert "# Заметка" in cli("note", "show", "3")

    def edit(path):
        storage.resolve_note_path(path).write_text("Unique edited text", encoding="utf-8")

    monkeypatch.setattr(storage, "edit_note_file", edit)
    cli("note", "edit", "3")
    assert "Unique edited text" in cli("note", "show", "3")

    def editor_failure(path):
        raise subprocess.CalledProcessError(1, "editor")

    monkeypatch.setattr(storage, "edit_note_file", editor_failure)
    assert "Failed to edit note" in cli("note", "edit", "3", code=1)
    cli("note", "rename", "3", "Renamed note")
    assert "Renamed note" in cli("note", "search", "EDITED TEXT")
    path = storage.resolve_note_path(database.get_note_by_id(1, 3)[5])
    cli("note", "delete", "3", "--yes")
    assert not path.exists()
    cli("note", "show", "3", code=1)


def test_evidence_crud_and_integrity(workspace, tmp_path):
    setup_finding()
    source = create_source(tmp_path)
    cli("evidence", "add", str(source), "--finding", "1")
    evidence = database.get_evidence_by_id(1, 1)
    copy = storage.resolve_evidence_path(evidence[4])
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert copy.suffix == source.suffix
    assert copy.name != source.name
    assert evidence[3] == digest
    assert not Path(evidence[4]).is_absolute()
    assert source.read_bytes() == copy.read_bytes()
    assert source.name in cli("evidence", "list", "--finding", "1")
    details = cli("evidence", "show", "1")
    assert digest in details and "Integrity: verified" in details
    copy.write_bytes(b"changed")
    assert "SHA-256 mismatch" in cli("evidence", "show", "1", code=1)
    copy.unlink()
    assert "Integrity: missing" in cli("evidence", "show", "1", code=1)
    cli("evidence", "delete", "1", input="y\n")
    assert source.exists()
    assert "No evidence" in cli("evidence", "list", "--finding", "1")
    assert "Unable to copy" in cli("evidence", "add", str(tmp_path / "missing"), "--finding", "1", code=1)


def test_cross_project_and_target_access(workspace, tmp_path):
    setup_finding()
    source = create_source(tmp_path)
    cli("note", "add", "Private", "--finding", "1")
    cli("evidence", "add", str(source), "--finding", "1")
    cli("target", "add", "other.example")
    cli("target", "use", "2")
    cli("evidence", "show", "1", code=1)
    cli("evidence", "list", "--finding", "1", code=1)

    cli("project", "create", "Other")
    cli("project", "use", "2")
    cli("target", "add", "second.example")
    cli("target", "use", "3")
    cli("evidence", "add", str(source), "--finding", "1", code=1)
    cli("evidence", "delete", "1", "--yes", code=1)
    cli("finding", "show", "1", code=1)
    cli("note", "show", "1", code=1)
    with pytest.raises(sqlite3.IntegrityError, match="Invalid note scope"):
        database.insert_note(2, "Invalid", "notes/invalid.md", target_id=1, finding_id=1)

    assert database.get_evidence_by_id(1, 1)


def test_invalid_stored_paths_and_retry(workspace, tmp_path):
    setup_finding()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"keep")
    for path in (str(outside), "../outside.png", "evidence/../pentworks.db", "notes/test.md"):
        with pytest.raises(ValueError):
            storage.resolve_evidence_path(path)
    database.insert_evidence(1, "Invalid path", "hash", "../outside.png")
    assert "unavailable" in cli("evidence", "show", "1", code=1)
    assert "Cleanup pending" in cli("evidence", "delete", "1", "-y", code=1)
    assert outside.read_bytes() == b"keep"
    assert database.pending_file_deletions() == [("evidence", "../outside.png")]


def test_failed_insert_removes_copied_file(workspace, tmp_path, monkeypatch):
    setup_finding()
    source = create_source(tmp_path)

    def fail_insert(*args):
        raise sqlite3.IntegrityError("Induced failure")

    monkeypatch.setattr(database, "insert_evidence", fail_insert)
    cli("evidence", "add", str(source), "--finding", "1", code=1)
    assert list(storage.EVIDENCE_DIR.iterdir()) == []
    assert source.exists()
    monkeypatch.setattr(database, "insert_note", fail_insert)
    cli("note", "add", "Fail", "--project", code=1)
    assert list(storage.NOTES_DIR.iterdir()) == []


@pytest.mark.parametrize("parent", ["finding", "target", "project"])
def test_cascade_cleans_associated_files(workspace, tmp_path, parent):
    setup_finding()
    source = create_source(tmp_path)
    cli("note", "add", "Finding note", "--finding", "1")
    cli("evidence", "add", str(source), "--finding", "1")
    cli("note", "add", "Project note", "--project")
    cli(parent, "delete", "1", "--yes")
    assert database.get_finding_by_id(1, 1) is None
    assert database.get_evidence_by_id(1, 1) is None
    assert list(storage.EVIDENCE_DIR.iterdir()) == []
    assert len(list(storage.NOTES_DIR.iterdir())) == (0 if parent == "project" else 1)
    assert not database.pending_file_deletions()
    assert source.exists()


def test_cascade_retries_failed_cleanup(workspace, tmp_path, monkeypatch):
    setup_finding()
    source = create_source(tmp_path)
    cli("evidence", "add", str(source), "--finding", "1")
    path = database.get_evidence_by_id(1, 1)[4]

    def locked(_):
        raise PermissionError("File is locked")

    with monkeypatch.context() as patch:
        patch.setattr(storage, "delete_evidence_file", locked)
        assert "Cleanup pending" in cli("finding", "delete", "1", "--yes", code=1)
        assert database.pending_file_deletions() == [("evidence", path)]
        assert storage.resolve_evidence_path(path).exists()
    cli("project", "list")
    assert not database.pending_file_deletions()
    assert list(storage.EVIDENCE_DIR.iterdir()) == []


def test_dashboard_and_report(workspace, tmp_path):
    setup_project()
    empty = cli("dashboard")
    assert "Targets: 0" in empty and "No findings yet." in empty
    assert "Report:" in cli("report", "generate")
    empty_file, = storage.REPORTS_DIR.glob("*.md")
    assert "No findings recorded." in empty_file.read_text(encoding="utf-8")

    cli("target", "add", "demo.example")
    cli("target", "use", "1")
    cli("finding", "add", "Finding [tag]", "high", "--endpoint", "/example",
        "--description", "Line one\n<script>alert(1)</script>\n# Line three")
    cli("finding", "status", "1", "confirmed")
    cli("note", "add", "Review note", "--finding", "1")
    cli("evidence", "add", str(create_source(tmp_path)), "--finding", "1")

    output = cli("dashboard")
    assert "Notes: 1" in output and "Evidence: 1" in output
    assert "Recent findings" in output and "confirmed" in output
    assert "Finding [tag]" in output
    cli("report", "generate")
    report, = set(storage.REPORTS_DIR.glob("*.md")) - {empty_file}
    text = report.read_text(encoding="utf-8")
    assert "## Executive summary" in text and "| high | 1 |" in text
    assert "../evidence/" in text and "../notes/" in text
    assert "<script>" not in text and "> Line one" in text and r"> \# Line three" in text
    cli("report", "generate")
    reports = list(storage.REPORTS_DIR.glob("*.md"))
    assert len(reports) == 3
    assert report.read_text(encoding="utf-8") == text


def test_existing_database_path_and_data(workspace, tmp_path, monkeypatch):
    setup_finding()
    original = database.database_path()
    legacy = tmp_path / "pentworks.db"
    with closing(sqlite3.connect(original)) as source, closing(sqlite3.connect(legacy)) as dest:
        source.backup(dest)
        dest.executescript("""
            DROP TRIGGER validate_note_scope;
            DROP TRIGGER queue_note_deletion;
            DROP TRIGGER queue_evidence_deletion;
            DROP TABLE pending_file_deletions;
        """)
    monkeypatch.setenv("PENTWORKS_DB", str(legacy))
    monkeypatch.chdir(tmp_path)
    assert "Finding" in cli("finding", "show", "1")
    assert database.database_path() == legacy
    assert database.pending_file_deletions() == []


def test_source_checkout_legacy_database(workspace, tmp_path, monkeypatch):
    setup_finding()
    with closing(sqlite3.connect(database.database_path())) as source:
        checkout = tmp_path / "old checkout"
        checkout.mkdir()
        legacy = checkout / "pentworks.db"
        with closing(sqlite3.connect(legacy)) as destination:
            source.backup(destination)

    monkeypatch.delenv("PENTWORKS_HOME")
    monkeypatch.setattr(database, "__file__", str(checkout / "database.py"))
    monkeypatch.chdir(tmp_path)
    assert database.database_path() == legacy
    assert "Finding" in cli("finding", "show", "1")
    monkeypatch.setenv("PENTWORKS_DB", "relative.db")
    assert "must be an absolute path" in cli("project", "list", code=1)
