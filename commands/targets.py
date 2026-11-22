import typer
import database
import utils

target = typer.Typer()

#Target commands

#Add target
@target.command("add")
def add_target(address: str, description: str = ""):
    project_id = utils.require_active_project()

    if(not address.strip()):
        utils.fail("Variable address is empty")

    database.insert_target(project_id, address, description)
    print(f"Target {address} was successfully added")

#List of targets
@target.command("list")
def list_targets():
    project_id = utils.require_active_project()

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

    target = database.get_target_by_id(target_id, project_id)
    if(not target):
        utils.fail("Target not found")

    target_id, target_project_id, target_address, target_description, target_date = target

    print(f"ID: {target_id}")
    print(f"Project ID: {target_project_id}")
    print(f"Address: {target_address}")
    print(f"Description: {target_description or '-'}")
    print(f"Created at: {target_date}")
    
#Delete target
@target.command("delete")
def delete_target(target_id: int, yes: bool = typer.Option(False, "--yes", "-y")):
    project_id = utils.require_active_project()

    if not database.get_target_by_id(target_id, project_id):
        utils.fail("Target not found")
    utils.confirm_delete(f"target {target_id} and its associated records and files", yes)
    result = database.delete_target(target_id, project_id)
    if(not result):
        utils.fail("No target with this id")
    else:
        utils.finish_delete("Target was successfully deleted")

#Set target to active
@target.command("use")
def use_target(target_id: int):
    project_id = utils.require_active_project()

    target = database.get_target_by_id(target_id, project_id)
    if(not target):
        utils.fail("No target with given id")
    else:
        database.set_active_target(target_id)
        print(f"Active target: {target[2]}")

#Check what target are we currently using
@target.command("status")
def status_target():
    target_id = utils.require_active_target()

    project_id = utils.require_active_project()
    target = database.get_target_by_id(target_id, project_id)
    print(f"Active target is '{target[2]}'")



    

