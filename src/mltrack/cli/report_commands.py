"""Compliance reporting CLI commands."""

import typer
from rich.console import Console

console = Console()

report_app = typer.Typer(
    help="Generate compliance reports.",
    no_args_is_help=True,
)


@report_app.command("overdue")
def overdue_reviews() -> None:
    """Show models with overdue reviews."""
    console.print("[yellow]TODO:[/yellow] List models with overdue reviews")


@report_app.command("gaps")
def documentation_gaps() -> None:
    """Show models missing required documentation."""
    console.print("[yellow]TODO:[/yellow] List models with documentation gaps")


@report_app.command("summary")
def risk_summary() -> None:
    """Show risk tier distribution summary."""
    console.print("[yellow]TODO:[/yellow] Display risk summary")
