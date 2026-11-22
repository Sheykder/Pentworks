import sqlite3

#Connection
def get_connection():
    connection = sqlite3.connect("pentworks.db")
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection

#Creation
def init_db():
    connection = get_connection()
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
    connection.commit()
    connection.close()

#Projects
def insert_project(name: str, description: str = ""):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO projects (name, description) VALUES (?, ?)", (name, description))
    connection.commit()
    connection.close()

def delete_project(id: int):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM settings WHERE setting_name='active_project' AND setting_value=?", (id,))
    if(cursor.rowcount):
        cursor.execute("DELETE FROM settings WHERE setting_name = 'active_target'")
    cursor.execute("DELETE FROM projects WHERE id = ?", (id,))
    success = cursor.rowcount
    connection.commit()
    connection.close()
    return success

def get_projects():
    connection = get_connection()
    cursor = connection.cursor()
    projects = cursor.execute("SELECT * FROM projects")
    result = projects.fetchall()
    connection.close()
    return result

def get_project_by_id(id: int):
    connection = get_connection()
    cursor = connection.cursor()
    project = cursor.execute("SELECT * FROM projects WHERE id = ?", (id,))
    result = project.fetchone()
    connection.close()
    return result

def set_active_project(id: int):
    connection = get_connection()
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
    connection.close()

def get_active_project():
    connection = get_connection()
    cursor = connection.cursor()
    active_project_id = cursor.execute("SELECT setting_value FROM settings WHERE setting_name = 'active_project'")
    result = active_project_id.fetchone()
    connection.close()
    if(not result):
        return None
    else:
        return int(result[0])

#Targets
def insert_target(project_id: int, address: str, description: str):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO targets (project_id, address, description) VALUES (?, ?, ?)", (project_id, address, description))
    connection.commit()
    connection.close()

def get_targets(project_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    targets = cursor.execute("SELECT * FROM targets WHERE project_id=?", (project_id,))
    result = targets.fetchall()
    connection.close()
    return result

def get_target_by_id(target_id: int, project_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    target = cursor.execute("SELECT * FROM targets WHERE id = ? AND project_id = ?", (target_id,project_id))
    result = target.fetchone()
    connection.close()
    return result

def delete_target(target_id: int, project_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    target = cursor.execute("DELETE FROM targets WHERE id = ? AND project_id = ?", (target_id, project_id))
    result = cursor.rowcount
    if(result):
        cursor.execute("DELETE FROM settings WHERE setting_name = 'active_target' AND setting_value = ?", (target_id,))

    connection.commit()
    connection.close()
    return result

def set_active_target(target_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
    """INSERT INTO settings (setting_name, setting_value) VALUES (?, ?) 
    ON CONFLICT(setting_name) DO UPDATE SET setting_value = excluded.setting_value""",
    ("active_target", target_id))
    connection.commit()
    connection.close()

def get_active_target():
    connection = get_connection()
    cursor = connection.cursor()
    active_target_id = cursor.execute("SELECT setting_value FROM settings WHERE setting_name = 'active_target'")
    result = active_target_id.fetchone()
    connection.close()
    if(not result):
        return None
    else:
        return int(result[0])

#Findings
def insert_finding(target_id: int, name: str, severity: str, description: str, endpoint: str):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO findings (target_id, name, severity, description, endpoint) VALUES (?, ?, ?, ?, ?)", (target_id, name, severity, description, endpoint))
    connection.commit()
    connection.close()

def get_findings(target_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    findings = cursor.execute("SELECT * FROM findings WHERE target_id=?", (target_id,))
    result = findings.fetchall()
    connection.close()
    return result

def get_finding_by_id(target_id: int, finding_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    finding = cursor.execute("SELECT * FROM findings WHERE id = ? AND target_id = ?", (finding_id, target_id))
    result = finding.fetchone()
    connection.close()
    return result

def delete_finding(target_id: int, finding_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    finding = cursor.execute("DELETE FROM findings WHERE id = ? AND target_id = ?", (finding_id, target_id))
    result = cursor.rowcount
    connection.commit()
    connection.close()
    return result

def update_finding_status(target_id: int, finding_id: int, status: str):
    connection = get_connection()
    cursor = connection.cursor()
    finding = cursor.execute("UPDATE findings SET status = ? WHERE id = ? AND target_id = ?", (status, finding_id, target_id))
    result = cursor.rowcount
    connection.commit()
    connection.close()
    return result

#Notes
def insert_note(project_id: int, name: str, file_path: str, target_id: int = None, finding_id: int = None):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO notes (project_id, target_id, finding_id, name, file_path) VALUES (?, ?, ?, ?, ?)", (project_id, target_id, finding_id, name, file_path))
    connection.commit()
    connection.close()

def get_notes(project_id: int, target_id: int = None, finding_id: int = None):
    connection = get_connection()
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
    connection.close()
    return result

def get_note_by_id(project_id: int, note_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    note = cursor.execute("SELECT * FROM notes WHERE project_id = ? AND id = ?", (project_id, note_id))
    result = note.fetchone()
    connection.close()
    return result

def delete_note(project_id: int, note_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    note = cursor.execute("DELETE FROM notes WHERE project_id = ? AND id = ?", (project_id, note_id))
    result = cursor.rowcount
    connection.commit()
    connection.close()
    return result

def update_note(project_id: int, note_id: int, name: str):
    connection = get_connection()
    cursor = connection.cursor()
    note = cursor.execute("UPDATE notes SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE project_id = ? AND id = ?", (name, project_id, note_id))
    result = note.rowcount
    connection.commit()
    connection.close()
    return result

def touch_note(project_id: int, note_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE notes SET updated_at = CURRENT_TIMESTAMP WHERE project_id = ? AND id = ?",
        (project_id, note_id)
    )
    connection.commit()
    connection.close()

#Evidence
def insert_evidence(finding_id: int, name: str, sha256: str, file_path: str):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO evidence (finding_id, name, sha256, file_path) VALUES (?, ?, ?, ?)", (finding_id, name, sha256, file_path))
    connection.commit()
    connection.close()

def get_evidence(finding_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    evidence = cursor.execute("SELECT * FROM evidence WHERE finding_id = ?", (finding_id,))
    result = evidence.fetchall()
    connection.close()
    return result

def get_evidence_by_id(finding_id: int, evidence_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    evidence = cursor.execute("SELECT * FROM evidence WHERE finding_id = ? AND id = ?", (finding_id, evidence_id))
    result = evidence.fetchone()
    connection.close()
    return result

def delete_evidence(finding_id: int, evidence_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM evidence WHERE finding_id = ? AND id = ?", (finding_id, evidence_id))
    result = cursor.rowcount
    connection.commit()
    connection.close()
    return result


    