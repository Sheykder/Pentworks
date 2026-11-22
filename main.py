import typer
import database
import services.storage as storage

from commands.findings import finding
from commands.projects import project
from commands.targets import target
from commands.notes import note


app = typer.Typer()
app.add_typer(project, name="project")
app.add_typer(target, name="target")
app.add_typer(finding, name="finding")
app.add_typer(note, name="note")

#App commands
@app.command()
def version():
    print("Pentworks v0.1.0")

if __name__ == "__main__":
    database.init_db()
    storage.init_storage()
    app()