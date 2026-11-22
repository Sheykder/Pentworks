import typer
import database
import utils

target = typer.Typer()

#Target commands

#Add target
@target.command("add")
def add_target(address: str, description: str = ""):
    project_id = utils.require_active_project()
    if(not project_id):
        return

    if(not address.strip()):
        print("Variable address is empty")
        return

    database.insert_target(project_id, address, description)
    print(f"Target {address} was successfully added")

#List of targets
@target.command("list")
def list_targets():
    project_id = utils.require_active_project()
    if(not project_id):
        return

    targets_list = database.get_targets(project_id)
    if(not targets_list):
        print("No targets found.")
        return

    for item in targets_list:
            target_id, target_project_id,target_address, target_description, target_date = item
            print(f"[{target_id}] | {target_address} | {target_description or '-'} | {target_date}")

#Show target
@target.command("show")
def show_target(target_id: int):
    project_id = utils.require_active_project()
    if(not project_id):
        return

    target = database.get_target_by_id(target_id, project_id)
    if(not target):
        print("Target not found")
        return

    target_id, target_project_id, target_address, target_description, target_date = target

    print(f"ID: {target_id}")
    print(f"Project ID: {target_project_id}")
    print(f"Address: {target_address}")
    print(f"Description: {target_description or '-'}")
    print(f"Created at: {target_date}")
    
#Delete target
@target.command("delete")
def delete_target(target_id: int):
    project_id = utils.require_active_project()
    if(not project_id):
        return

    result = database.delete_target(target_id, project_id)
    if(not result):
        print("No target with this id")
    else:
        print("Target was successfully deleted")

#Set target to active
@target.command("use")
def use_target(target_id: int):
    project_id = utils.require_active_project()
    if(not project_id):
        return

    target = database.get_target_by_id(target_id, project_id)
    if(not target):
        print("No target with given id")
    else:
        database.set_active_target(target_id)
        print(f"Active target: {target[2]}")

#Check what target are we currently using
@target.command("status")
def status_target():
    target_id = utils.require_active_target()
    if(not target_id):
        return

    project_id = utils.require_active_project()
    target = database.get_target_by_id(target_id, project_id)
    print(f"Active target is '{target[2]}'")



    

