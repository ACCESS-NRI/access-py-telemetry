"""Console script for intake_telemetry."""
import intake_telemetry

import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command()
def main():
    """Console script for intake_telemetry."""
    console.print("Replace this message by putting your code into "
               "intake_telemetry.cli.main")
    console.print("See Typer documentation at https://typer.tiangolo.com/")
    


if __name__ == "__main__":
    app()
