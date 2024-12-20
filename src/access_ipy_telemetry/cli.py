"""Console script for intake_telemetry."""

import access_ipy_telemetry

access_ipy_telemetry.__file__

import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command()  # type: ignore
def main() -> None:
    """Console script for intake_telemetry."""
    console.print(
        "Replace this message by putting your code into "
        "access_ipy_telemetry.cli.main"
    )
    console.print("See Typer documentation at https://typer.tiangolo.com/")


if __name__ == "__main__":
    app()
