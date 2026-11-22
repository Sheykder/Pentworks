import typer
import database
import utils

project = typer.Typer()

#Project commands

#Create project
@project.command("create")
def create_project(name: str, description: str = ""):
    if(not name.strip()):
        utils.fail("Variable name is empty")
    else:
        database.insert_project(name, description)
        print(f"Project '{name}' was created.")

#List of projects
@project.command("list")
def list_projects():
    project_list = database.get_projects()
    if(not project_list):
        print("No projects found.")
    else:
        for item in project_list:
            project_id, project_name, project_description, project_date = item
            print(f"[{project_id}] {project_name} | {project_description or '-'} | {project_date}")

#Delete project with specific ID from sqlite dbs
@project.command("delete")
def delete_project(id: int, yes: bool = typer.Option(False, "--yes", "-y")):
    if not database.get_project_by_id(id):
        utils.fail("Project not found")
    utils.confirm_delete(f"project {id} and its associated records and files", yes)
    success = database.delete_project(id)
    if(success):
        utils.finish_delete(f"Project {id} was deleted.")
    else:
        utils.fail(f"Project {id} not found.")

#Set project to active
@project.command("use")
def use_project(id: int):
    project = database.get_project_by_id(id)
    if(not project):
        utils.fail("No project with given id")
    else:
        database.set_active_project(id)
        print(f"Active project: {project[1]}")

#Check what project are we currently using
@project.command("status")
def status_project():
    current_project_id = utils.require_active_project()
        
    current_project = database.get_project_by_id(current_project_id)
    print(f"Current project is '{current_project[1]}'")

@project.command("show")
def show_project(project_id: int):
    result = database.get_project_by_id(project_id)
    if(not result):
        utils.fail("Project not found")

    project_id, name, description, created_at = result
    targets = database.get_targets(project_id)

    print(f"ID: {project_id}")
    print(f"Name: {name}")
    print(f"Description: {description or '-'}")
    print(f"Created at: {created_at}")
    print(f"Targets: {len(targets)}")
