"""CLI command for recording model reviews."""

from datetime import date
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from mltrack.core.storage import get_model, update_model, REVIEW_FREQUENCY
from mltrack.core.exceptions import ModelNotFoundError, DatabaseError
from mltrack.models import RiskTier

console = Console()

# Color mappings
RISK_COLORS = {
    RiskTier.CRITICAL: "bold red",
    RiskTier.HIGH: "red",
    RiskTier.MEDIUM: "yellow",
    RiskTier.LOW: "green",
}


def _format_risk_tier(tier: RiskTier) -> str:
    """Format risk tier with color."""
    color = RISK_COLORS.get(tier, "white")
    return f"[{color}]{tier.value.upper()}[/{color}]"


def _parse_date(value: str) -> date:
    """Parse date string, supporting 'today' keyword."""
    if value.lower() == "today":
        return date.today()

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise typer.BadParameter(
            f"Invalid date format: '{value}'. Use YYYY-MM-DD or 'today'"
        )


def reviewed_command(
    identifier: str = typer.Argument(
        ...,
        help="Model name or UUID that was reviewed",
    ),
    review_date: str = typer.Option(
        "today",
        "--date", "-d",
        help="Date the review was completed: YYYY-MM-DD or 'today' (default: today)",
    ),
    notes: Optional[str] = typer.Option(
        None,
        "--notes", "-n",
        help="Review notes (appended to existing notes with timestamp)",
    ),
) -> None:
    """
    Record completion of a model review.

    Updates the model's last_review_date and automatically calculates
    the next_review_date based on the model's risk tier. Notes are
    timestamped and appended to existing notes.

    This is the primary way to clear "overdue for review" compliance
    violations shown by 'mltrack validate'.

    \b
    [bold cyan]Review Cycles (SR 11-7 Aligned):[/bold cyan]
      CRITICAL → 30 days     HIGH → 90 days
      MEDIUM   → 180 days    LOW  → 365 days

    \b
    [bold cyan]What Happens:[/bold cyan]
      1. Sets last_review_date to the specified date
      2. Calculates next_review_date based on risk tier
      3. Appends notes with [date] prefix to model notes
      4. Clears any "review overdue" compliance violations

    \b
    [bold]Examples:[/bold]
      [dim]# Record review completed today[/dim]
      mltrack reviewed "claude-sonnet-4"
      mltrack reviewed "fraud-detector"

      [dim]# Record review with specific date[/dim]
      mltrack reviewed "claude-sonnet-4" --date 2025-01-15
      mltrack reviewed "gpt-4-turbo" -d 2025-01-20

      [dim]# Record review with notes[/dim]
      mltrack reviewed "claude-sonnet-4" -n "Quarterly security review completed"
      mltrack reviewed "credit-model" -d 2025-01-15 -n "Annual audit - no issues found"

      [dim]# Use 'today' explicitly[/dim]
      mltrack reviewed "model-name" --date today --notes "Passed all checks"

    \b
    [bold cyan]Related Commands:[/bold cyan]
      mltrack validate --all       Check which models need review
      mltrack show <name>          View model's current review schedule
      mltrack report compliance    See review status for all models
    """
    # Parse the review date
    try:
        parsed_date = _parse_date(review_date)
    except typer.BadParameter as e:
        console.print(f"[red]Error:[/red] {e.message}")
        raise typer.Exit(1)

    # Get the current model
    try:
        model = get_model(identifier)
    except ModelNotFoundError:
        console.print(
            Panel(
                f"[red]Model not found:[/red] '{identifier}'\n\n"
                "[dim]Use [cyan]mltrack list[/cyan] to see all models.[/dim]",
                title="Not Found",
                border_style="red",
            )
        )
        raise typer.Exit(1)
    except DatabaseError as e:
        console.print(f"[red]Database error:[/red] {e.details}")
        raise typer.Exit(1)

    # Store previous values for comparison
    old_last_review = model.last_review_date
    old_next_review = model.next_review_date

    # Build updates
    updates = {"last_review_date": parsed_date}
    if notes is not None:
        # Append to existing notes or set new
        if model.notes:
            updates["notes"] = f"{model.notes}\n\n[{parsed_date}] {notes}"
        else:
            updates["notes"] = f"[{parsed_date}] {notes}"

    # Apply the update (this will recalculate next_review_date)
    try:
        updated_model = update_model(identifier, updates)
    except DatabaseError as e:
        console.print(f"[red]Database error:[/red] {e.details}")
        raise typer.Exit(1)

    # Calculate review cycle days
    review_days = REVIEW_FREQUENCY[updated_model.risk_tier]

    # Build comparison table
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    table.add_column("Field", style="bold cyan", width=20)
    table.add_column("Value")

    table.add_row("Model", f"[cyan]{updated_model.model_name}[/cyan]")
    table.add_row("Risk Tier", _format_risk_tier(updated_model.risk_tier))
    table.add_row("Review Cycle", f"{review_days} days")
    table.add_row("", "")  # Spacer

    # Show last review change
    if old_last_review:
        table.add_row(
            "Last Review (was)",
            f"[dim]{old_last_review}[/dim]",
        )
    table.add_row(
        "Last Review (now)",
        f"[green]{updated_model.last_review_date}[/green]",
    )

    table.add_row("", "")  # Spacer

    # Show next review change
    if old_next_review:
        days_was_overdue = (date.today() - old_next_review).days
        if days_was_overdue > 0:
            table.add_row(
                "Next Review (was)",
                f"[red]{old_next_review} (was {days_was_overdue} days overdue)[/red]",
            )
        else:
            table.add_row(
                "Next Review (was)",
                f"[dim]{old_next_review}[/dim]",
            )

    days_until_next = (updated_model.next_review_date - date.today()).days
    table.add_row(
        "Next Review (now)",
        f"[green]{updated_model.next_review_date}[/green] [dim](in {days_until_next} days)[/dim]",
    )

    # Success message
    console.print()
    console.print(
        Panel(
            table,
            title="[green]✓ Review Recorded[/green]",
            border_style="green",
        )
    )

    if notes:
        console.print(f"\n[dim]Note added:[/dim] {notes}")
