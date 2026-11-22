import typer
import database

def require_active_project():
    project_id = database.get_active_project()
    if(not project_id):
        print("No active project")
        return
    if(not database.get_project_by_id(project_id)):
        print("Active project does not exist")
        return
    return project_id

def require_active_target():
    project_id = require_active_project()
    if(not project_id):
        return

    target_id = database.get_active_target()
    if(not target_id):
        print("No active target")
        return

    if(not database.get_target_by_id(target_id, project_id)):
        print("Active target does not exist")
        return

    return target_id
