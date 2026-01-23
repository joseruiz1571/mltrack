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

# Epilog shown at the bottom of --help
EPILOG = """
[bold cyan]Quick Start:[/bold cyan]
  mltrack sample-data           Generate demo data to explore features
  mltrack dashboard             View compliance dashboard
  mltrack validate --all        Check all models for compliance issues

[bold cyan]Common Workflows:[/bold cyan]
  [dim]Add a model:[/dim]       mltrack add --interactive
  [dim]Record review:[/dim]     mltrack reviewed "model-name" --date today
  [dim]Export data:[/dim]       mltrack export backup.json
  [dim]Get report:[/dim]        mltrack report compliance

[bold cyan]Review Cycles (SR 11-7):[/bold cyan]
  CRITICAL: 30 days  │  HIGH: 90 days  │  MEDIUM: 180 days  │  LOW: 365 days

[dim]Documentation: https://github.com/joseruiz1571/mltrack[/dim]
"""

app = typer.Typer(
    name="mltrack",
    help="Model Lineage Tracker - AI governance tool for financial services compliance.",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=True,
    epilog=EPILOG,
)

# Register top-level commands with enhanced help summaries
app.command(
    name="add",
    help="Register a new AI model [dim](use -i for interactive mode)[/dim]",
)(add_model)

app.command(
    name="list",
    help="List models with filtering [dim](--risk, --vendor, --status)[/dim]",
)(list_models)

app.command(
    name="show",
    help="Display full details for a model [dim](by name or ID)[/dim]",
)(show_model)

app.command(
    name="update",
    help="Modify model attributes [dim](--risk-tier, --status, etc.)[/dim]",
)(update_model_command)

app.command(
    name="delete",
    help="Remove or decommission a model [dim](--soft preserves audit trail)[/dim]",
)(delete_model_command)

app.command(
    name="validate",
    help="Check compliance status [dim](--all, --risk, --json)[/dim]",
)(validate_command)

app.command(
    name="reviewed",
    help="Record model review completion [dim](auto-calculates next review)[/dim]",
)(reviewed_command)

app.command(
    name="import",
    help="Bulk import from CSV/JSON [dim](--validate, --update)[/dim]",
)(import_models)

app.command(
    name="export",
    help="Export to CSV/JSON [dim](with filtering, --template)[/dim]",
)(export_models)

app.command(
    name="sample-data",
    help="Generate realistic demo data [dim](--count, --clear)[/dim]",
)(sample_data)

# Register subcommand groups
app.add_typer(
    model_app,
    name="model",
    help="[dim](alias)[/dim] Model inventory management",
)
app.add_typer(
    report_app,
    name="report",
    help="Generate compliance/inventory/risk reports",
)
app.add_typer(
    dashboard_app,
    name="dashboard",
    help="Interactive dashboard [dim](--watch for auto-refresh)[/dim]",
)


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
        help="Display MLTrack version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """
    [bold blue]MLTrack[/bold blue] — AI Model Governance for Financial Services

    Track deployed AI/ML models with automated review scheduling aligned to:

    • [cyan]SR 11-7[/cyan]     Federal Reserve Model Risk Management
    • [cyan]NIST AI RMF[/cyan] AI Risk Management Framework
    • [cyan]ISO 42001[/cyan]   AI Management System Standard

    [bold]Key Features:[/bold]
    • Model inventory with ownership and risk classification
    • Risk-based review cycles (Critical=30d, High=90d, Medium=180d, Low=365d)
    • Compliance validation with violation reports
    • Interactive terminal dashboard with real-time metrics
    • CSV/JSON import/export with field mapping

    [dim]Run any command with --help for detailed usage information.[/dim]
    """
    pass


if __name__ == "__main__":
    app()
