import sqlite3

import typer
from typer.core import TyperGroup

import database
import utils
from commands.dashboard import dashboard
from commands.evidence import evidence
from commands.findings import finding
from commands.notes import note
from commands.projects import project
from commands.reports import report
from commands.targets import target
from services import storage

__version__ = "0.1.0"


class WorkspaceGroup(TyperGroup):
    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except (OSError, sqlite3.Error) as exc:
            utils.fail(f"Workspace operation failed: {exc}")


app = typer.Typer(cls=WorkspaceGroup, no_args_is_help=True, help="Manage an offline security assessment workspace.")
app.add_typer(project, name="project", help="Manage projects and select the active project.")
app.add_typer(target, name="target", help="Manage targets in the active project.")
app.add_typer(finding, name="finding", help="Manage findings in the active target.")
app.add_typer(note, name="note", help="Manage Markdown notes.")
app.add_typer(evidence, name="evidence", help="Manage finding attachments.")
app.add_typer(report, name="report", help="Generate Markdown reports.")
app.command()(dashboard)


@app.callback()
def initialize(ctx: typer.Context):
    if ctx.invoked_subcommand == "version":
        return
    storage.init_storage()
    database.init_db()
    utils.clean_pending_files()


@app.command()
def version():
    """Print the current version."""
    typer.echo(f"Pentworks v{__version__}")


def main():
    app()


if __name__ == "__main__":
    main()
