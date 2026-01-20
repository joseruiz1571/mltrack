"""Dashboard CLI commands."""

import typer
from rich.console import Console

console = Console()

dashboard_app = typer.Typer(
    help="View compliance dashboard.",
    invoke_without_command=True,
)


@dashboard_app.callback(invoke_without_command=True)
def show_dashboard(ctx: typer.Context) -> None:
    """Display the compliance dashboard with key metrics."""
    if ctx.invoked_subcommand is None:
        console.print("[yellow]TODO:[/yellow] Display compliance dashboard")
