import os
import sqlite3
from contextlib import closing
from pathlib import Path

from services.storage import WORKSPACE_DIR


def database_path():
    override = os.environ.get("PENTWORKS_DB")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise OSError("PENTWORKS_DB must be an absolute path")
        return path.resolve()
    legacy = Path(__file__).resolve().with_name("pentworks.db")
    if not os.environ.get("PENTWORKS_HOME") and legacy.is_file():
        return legacy
    return WORKSPACE_DIR / "pentworks.db"


#Connection
def get_connection():
    connection = sqlite3.connect(database_path())
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection

#Creation
def init_db():
    with closing(get_connection()) as connection, connection:
        connection.execute("BEGIN")
        cursor = connection.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS projects(
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)
        """)
        cursor.execute("""CREATE TABLE IF NOT EXISTS settings(
        setting_name TEXT PRIMARY KEY, setting_value TEXT NOT NULL
        )
        """)
        cursor.execute("""CREATE TABLE IF NOT EXISTS targets(
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL,
        address TEXT NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("""CREATE TABLE IF NOT EXISTS findings(
        id INTEGER PRIMARY KEY,
        target_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        severity TEXT NOT NULL CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
        description TEXT,
        endpoint TEXT,
        status TEXT NOT NULL CHECK (status IN ('open', 'confirmed', 'fixed', 'false_positive')) DEFAULT 'open',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (target_id) REFERENCES targets(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("""CREATE TABLE IF NOT EXISTS notes(
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL,
        target_id INTEGER,
        finding_id INTEGER,
        name TEXT NOT NULL,
        file_path TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY (target_id) REFERENCES targets(id) ON DELETE CASCADE,
        FOREIGN KEY (finding_id) REFERENCES findings(id) ON DELETE CASCADE,
        CHECK (finding_id IS NULL OR target_id IS NOT NULL)
        )
        """)
        cursor.execute("""CREATE TABLE IF NOT EXISTS evidence(
        id INTEGER PRIMARY KEY,
        finding_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        file_path TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (finding_id) REFERENCES findings(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("""CREATE TABLE IF NOT EXISTS pending_file_deletions(
            kind TEXT NOT NULL CHECK (kind IN ('note', 'evidence')), file_path TEXT NOT NULL,
            PRIMARY KEY (kind, file_path)
        )""")
        cursor.execute("""CREATE TRIGGER IF NOT EXISTS queue_note_deletion
            AFTER DELETE ON notes BEGIN
                INSERT OR IGNORE INTO pending_file_deletions VALUES ('note', OLD.file_path);
            END
        """)
        cursor.execute("""CREATE TRIGGER IF NOT EXISTS queue_evidence_deletion
            AFTER DELETE ON evidence BEGIN
                INSERT OR IGNORE INTO pending_file_deletions VALUES ('evidence', OLD.file_path);
            END
        """)
        cursor.execute("""CREATE TRIGGER IF NOT EXISTS validate_note_scope
            BEFORE INSERT ON notes WHEN
                (NEW.target_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM targets WHERE id = NEW.target_id AND project_id = NEW.project_id
                )) OR (NEW.finding_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM findings WHERE id = NEW.finding_id AND target_id = NEW.target_id
                ))
            BEGIN
                SELECT RAISE(ABORT, 'Invalid note scope');
            END
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS targets_project ON targets(project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS findings_target ON findings(target_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS notes_project ON notes(project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS notes_target ON notes(target_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS notes_finding ON notes(finding_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS evidence_finding ON evidence(finding_id)")


#Projects
def insert_project(name: str, description: str = ""):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO projects (name, description) VALUES (?, ?)", (name, description))
        connection.commit()


def delete_project(id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM settings WHERE setting_name='active_project' AND setting_value=?", (id,))
        if(cursor.rowcount):
            cursor.execute("DELETE FROM settings WHERE setting_name = 'active_target'")
        cursor.execute("DELETE FROM projects WHERE id = ?", (id,))
        success = cursor.rowcount
        connection.commit()
        return success


def get_projects():
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        projects = cursor.execute("SELECT * FROM projects")
        result = projects.fetchall()
        return result


def get_project_by_id(id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        project = cursor.execute("SELECT * FROM projects WHERE id = ?", (id,))
        result = project.fetchone()
        return result


def set_active_project(id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        last_active_project_id = cursor.execute(
        """SELECT setting_value FROM settings WHERE setting_name = 'active_project'
        """).fetchone()
        last_active_project_id = int(last_active_project_id[0]) if last_active_project_id else None
        if(last_active_project_id != id):
            cursor.execute("DELETE FROM settings WHERE setting_name = 'active_target'")
        cursor.execute(
        """INSERT INTO settings (setting_name, setting_value) VALUES (?, ?)
        ON CONFLICT(setting_name) DO UPDATE SET setting_value = excluded.setting_value""",
        ("active_project",id,))
        connection.commit()


def get_active_project():
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        active_project_id = cursor.execute("SELECT setting_value FROM settings WHERE setting_name = 'active_project'")
        result = active_project_id.fetchone()
        if(not result):
            return None
        else:
            return int(result[0])


#Targets
def insert_target(project_id: int, address: str, description: str):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO targets (project_id, address, description) VALUES (?, ?, ?)", (project_id, address, description))
        connection.commit()


def get_targets(project_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        targets = cursor.execute("SELECT * FROM targets WHERE project_id=?", (project_id,))
        result = targets.fetchall()
        return result


def get_target_by_id(target_id: int, project_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        target = cursor.execute("SELECT * FROM targets WHERE id = ? AND project_id = ?", (target_id,project_id))
        result = target.fetchone()
        return result


def delete_target(target_id: int, project_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        target = cursor.execute("DELETE FROM targets WHERE id = ? AND project_id = ?", (target_id, project_id))
        result = cursor.rowcount
        if(result):
            cursor.execute("DELETE FROM settings WHERE setting_name = 'active_target' AND setting_value = ?", (target_id,))

        connection.commit()
        return result


def set_active_target(target_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
        """INSERT INTO settings (setting_name, setting_value) VALUES (?, ?)
        ON CONFLICT(setting_name) DO UPDATE SET setting_value = excluded.setting_value""",
        ("active_target", target_id))
        connection.commit()


def get_active_target():
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        active_target_id = cursor.execute("SELECT setting_value FROM settings WHERE setting_name = 'active_target'")
        result = active_target_id.fetchone()
        if(not result):
            return None
        else:
            return int(result[0])


#Findings
def insert_finding(target_id: int, name: str, severity: str, description: str, endpoint: str):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO findings (target_id, name, severity, description, endpoint) VALUES (?, ?, ?, ?, ?)", (target_id, name, severity, description, endpoint))
        connection.commit()


def get_findings(target_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        findings = cursor.execute("SELECT * FROM findings WHERE target_id=?", (target_id,))
        result = findings.fetchall()
        return result


def get_finding_by_id(target_id: int, finding_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        finding = cursor.execute("SELECT * FROM findings WHERE id = ? AND target_id = ?", (finding_id, target_id))
        result = finding.fetchone()
        return result


def delete_finding(target_id: int, finding_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        finding = cursor.execute("DELETE FROM findings WHERE id = ? AND target_id = ?", (finding_id, target_id))
        result = cursor.rowcount
        connection.commit()
        return result


def update_finding_status(target_id: int, finding_id: int, status: str):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        finding = cursor.execute("UPDATE findings SET status = ? WHERE id = ? AND target_id = ?", (status, finding_id, target_id))
        result = cursor.rowcount
        connection.commit()
        return result


#Notes
def insert_note(project_id: int, name: str, file_path: str, target_id: int = None, finding_id: int = None):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO notes (project_id, target_id, finding_id, name, file_path) VALUES (?, ?, ?, ?, ?)", (project_id, target_id, finding_id, name, file_path))
        connection.commit()


def get_notes(project_id: int, target_id: int = None, finding_id: int = None):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        query = "SELECT * FROM notes WHERE project_id = ?"
        params = [project_id]
        if(target_id is not None):
            query += " AND target_id = ?"
            params.append(target_id)

        if(finding_id is not None):
            query += " AND finding_id = ?"
            params.append(finding_id)

        notes = cursor.execute(query, params)
        result = notes.fetchall()
        return result


def get_note_by_id(project_id: int, note_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        note = cursor.execute("SELECT * FROM notes WHERE project_id = ? AND id = ?", (project_id, note_id))
        result = note.fetchone()
        return result


def delete_note(project_id: int, note_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        note = cursor.execute("DELETE FROM notes WHERE project_id = ? AND id = ?", (project_id, note_id))
        result = cursor.rowcount
        connection.commit()
        return result


def update_note(project_id: int, note_id: int, name: str):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        note = cursor.execute("UPDATE notes SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE project_id = ? AND id = ?", (name, project_id, note_id))
        result = note.rowcount
        connection.commit()
        return result


def touch_note(project_id: int, note_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE notes SET updated_at = CURRENT_TIMESTAMP WHERE project_id = ? AND id = ?",
            (project_id, note_id)
        )
        connection.commit()


#Evidence
def insert_evidence(finding_id: int, name: str, sha256: str, file_path: str):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO evidence (finding_id, name, sha256, file_path) VALUES (?, ?, ?, ?)", (finding_id, name, sha256, file_path))
        connection.commit()


def get_evidence(finding_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        evidence = cursor.execute("SELECT * FROM evidence WHERE finding_id = ?", (finding_id,))
        result = evidence.fetchall()
        return result


def get_evidence_by_id(finding_id: int, evidence_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        evidence = cursor.execute("SELECT * FROM evidence WHERE finding_id = ? AND id = ?", (finding_id, evidence_id))
        result = evidence.fetchone()
        return result


def delete_evidence(finding_id: int, evidence_id: int):
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM evidence WHERE finding_id = ? AND id = ?", (finding_id, evidence_id))
        result = cursor.rowcount
        connection.commit()
        return result



def get_evidence_in_context(project_id: int, target_id: int, evidence_id: int):
    with closing(get_connection()) as connection:
        return connection.execute("""
            SELECT e.* FROM evidence e
            JOIN findings f ON f.id = e.finding_id
            JOIN targets t ON t.id = f.target_id
            WHERE e.id = ? AND t.id = ? AND t.project_id = ?
        """, (evidence_id, target_id, project_id)).fetchone()


def pending_file_deletions():
    with closing(get_connection()) as connection:
        return connection.execute("SELECT kind, file_path FROM pending_file_deletions").fetchall()


def finish_file_deletion(kind: str, file_path: str):
    with closing(get_connection()) as connection, connection:
        connection.execute("DELETE FROM pending_file_deletions WHERE kind = ? AND file_path = ?",
                           (kind, file_path))


def project_snapshot(project_id: int, include_references: bool = False):
    with closing(get_connection()) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        project = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        targets = connection.execute("""
            SELECT * FROM targets WHERE project_id = ? ORDER BY id
        """, (project_id,)).fetchall()
        findings = connection.execute("""
            SELECT f.*, t.address FROM findings f JOIN targets t ON t.id = f.target_id
            WHERE t.project_id = ? ORDER BY f.created_at DESC, f.id DESC
        """, (project_id,)).fetchall()
        notes_query = " FROM notes WHERE project_id = ?"
        evidence_query = """
            FROM evidence e JOIN findings f ON f.id = e.finding_id
            JOIN targets t ON t.id = f.target_id WHERE t.project_id = ?
        """
        if include_references:
            notes = connection.execute("SELECT *" + notes_query + " ORDER BY id", (project_id,)).fetchall()
            evidence = connection.execute("SELECT e.*" + evidence_query + " ORDER BY e.id",
                                          (project_id,)).fetchall()
        else:
            notes = connection.execute("SELECT COUNT(*)" + notes_query, (project_id,)).fetchone()[0]
            evidence = connection.execute("SELECT COUNT(*)" + evidence_query, (project_id,)).fetchone()[0]
        return project, targets, findings, notes, evidence


def queue_file_deletion(kind: str, file_path: str):
    with closing(get_connection()) as connection, connection:
        connection.execute("INSERT OR IGNORE INTO pending_file_deletions VALUES (?, ?)",
                           (kind, file_path))
