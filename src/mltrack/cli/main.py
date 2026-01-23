"""Main CLI entry point for MLTrack."""

import typer
from rich.console import Console
from rich.panel import Panel

from mltrack import __version__
from mltrack.cli.model_commands import model_app
from mltrack.cli.report_commands import report_app
from mltrack.cli.dashboard_commands import dashboard_app
from mltrack.cli.add_command import add_model
from mltrack.cli.list_command import list_models
from mltrack.cli.show_command import show_model
from mltrack.cli.update_command import update_model_command
from mltrack.cli.delete_command import delete_model_command
from mltrack.cli.validate_command import validate_command
from mltrack.cli.reviewed_command import reviewed_command
from mltrack.cli.import_command import import_models
from mltrack.cli.export_command import export_models
from mltrack.cli.sample_data_command import sample_data

console = Console()

app = typer.Typer(
    name="mltrack",
    help="Model Lineage Tracker - AI governance tool for financial services compliance.",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Register top-level commands
app.command(name="add", help="Add a new AI model to the inventory")(add_model)
app.command(name="list", help="List all AI models in the inventory")(list_models)
app.command(name="show", help="Show detailed information about a model")(show_model)
app.command(name="update", help="Update an existing model")(update_model_command)
app.command(name="delete", help="Delete a model from the inventory")(delete_model_command)
app.command(name="validate", help="Validate models against governance requirements")(validate_command)
app.command(name="reviewed", help="Record that a model has been reviewed")(reviewed_command)
app.command(name="import", help="Import models from CSV or JSON file")(import_models)
app.command(name="export", help="Export models to CSV or JSON file")(export_models)
app.command(name="sample-data", help="Generate sample data for demos")(sample_data)

# Register subcommand groups
app.add_typer(model_app, name="model", help="Manage AI model inventory")
app.add_typer(report_app, name="report", help="Generate compliance reports")
app.add_typer(dashboard_app, name="dashboard", help="View compliance dashboard")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(
            Panel(
                f"[bold blue]MLTrack[/bold blue] v{__version__}\n"
                "[dim]Model Lineage Tracker for AI Governance[/dim]",
                border_style="blue",
            )
        )
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """
    [bold]MLTrack[/bold] - Model Lineage Tracker

    Track deployed AI models for compliance with:
    • [cyan]NIST AI RMF[/cyan] - AI Risk Management Framework
    • [cyan]ISO 42001[/cyan] - AI Management System Standard
    • [cyan]SR 11-7[/cyan] - Federal Reserve Model Risk Management

    [dim]Built for AI Risk Managers at financial services firms.[/dim]
    """
    pass


if __name__ == "__main__":
    app()
