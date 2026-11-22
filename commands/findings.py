import typer
import database
import utils
from enums import Severity, FindingStatus

finding = typer.Typer()

#Finding commands
@finding.command("add")
def add_finding(name: str, severity: Severity, description: str = "", endpoint: str = ""):
    target_id = utils.require_active_target()

    if(not name.strip()):
        utils.fail("Variable name is empty")

    database.insert_finding(target_id, name, severity.value, description, endpoint)
    print(f"Finding '{name}' was successfully added")

@finding.command("list")
def list_findings():
    target_id = utils.require_active_target()

    findings = database.get_findings(target_id)

    if (not findings):
        print("No findings found")
        return

    print("Findings:")

    for item in findings:
        finding_id, target_id, name, severity, description, endpoint, status, created_at = item
        print(f"{finding_id} | {name} | {severity} | {status} | {endpoint or '-'}")


@finding.command("show")
def show_finding(finding_id: int):
    target_id = utils.require_active_target()

    result = database.get_finding_by_id(target_id, finding_id)

    if (not result):
        utils.fail("Finding not found")

    finding_id, target_id, name, severity, description, endpoint, status, created_at = result

    print(f"ID: {finding_id}")
    print(f"Target ID: {target_id}")
    print(f"Name: {name}")
    print(f"Severity: {severity}")
    print(f"Status: {status}")
    print(f"Endpoint: {endpoint or '-'}")
    print(f"Description: {description or '-'}")
    print(f"Created at: {created_at}")


@finding.command("delete")
def delete_finding(finding_id: int, yes: bool = typer.Option(False, "--yes", "-y")):
    target_id = utils.require_active_target()

    if not database.get_finding_by_id(target_id, finding_id):
        utils.fail("Finding not found")
    utils.confirm_delete(f"finding {finding_id} and its associated records and files", yes)
    result = database.delete_finding(target_id, finding_id)

    if result:
        utils.finish_delete(f"Finding {finding_id} was deleted")
    else:
        utils.fail("Finding not found")


@finding.command("status")
def update_status(finding_id: int, status: FindingStatus):
    target_id = utils.require_active_target()

    result = database.update_finding_status(target_id, finding_id, status.value)

    if result:
        print(f"Finding {finding_id} status updated to {status.value}")
    else:
        utils.fail("Finding not found")
