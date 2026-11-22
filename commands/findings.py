import typer
import database
import utils
from enums import Severity, FindingStatus

finding = typer.Typer()

#Finding commands
@finding.command("add")
def add_finding(name: str, severity: Severity, description: str = "", endpoint: str = ""):
    target_id = utils.require_active_target()
    if(not target_id):
        return

    if(not name.strip()):
        print("Variable name is empty")
        return

    database.insert_finding(target_id, name, severity.value, description, endpoint)
    print(f"Finding '{name}' was successfully added")

@finding.command("list")
def list_findings():
    target_id = utils.require_active_target()
    if(not target_id):
        return

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
    if (not target_id):
        return

    result = database.get_finding_by_id(target_id, finding_id)

    if (not result):
        print("Finding not found")
        return

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
def delete_finding(finding_id: int):
    target_id = utils.require_active_target()
    if not target_id:
        return

    result = database.delete_finding(target_id, finding_id)

    if result:
        print(f"Finding {finding_id} was deleted")
    else:
        print("Finding not found")


@finding.command("status")
def update_status(finding_id: int, status: FindingStatus):
    target_id = utils.require_active_target()
    if not target_id:
        return

    result = database.update_finding_status(target_id, finding_id, status.value)

    if result:
        print(f"Finding {finding_id} status updated to {status.value}")
    else:
        print("Finding not found")
