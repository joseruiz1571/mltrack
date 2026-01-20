"""CLI command for showing detailed model information."""

from datetime import date

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from mltrack.core.storage import get_model, REVIEW_FREQUENCY
from mltrack.core.exceptions import ModelNotFoundError, DatabaseError
from mltrack.models import RiskTier, ModelStatus, AIModel

console = Console()

# Color mappings
RISK_COLORS = {
    RiskTier.CRITICAL: "bold red",
    RiskTier.HIGH: "red",
    RiskTier.MEDIUM: "yellow",
    RiskTier.LOW: "green",
}

STATUS_COLORS = {
    ModelStatus.ACTIVE: "green",
    ModelStatus.DEPRECATED: "yellow",
    ModelStatus.DECOMMISSIONED: "dim",
}


def _format_risk_tier(tier: RiskTier) -> str:
    """Format risk tier with color and review frequency."""
    color = RISK_COLORS.get(tier, "white")
    days = REVIEW_FREQUENCY[tier]
    return f"[{color}]{tier.value.upper()}[/{color}] [dim]({days}-day review cycle)[/dim]"


def _format_status(status: ModelStatus) -> str:
    """Format status with color."""
    color = STATUS_COLORS.get(status, "white")
    return f"[{color}]{status.value.upper()}[/{color}]"


def _calculate_days_deployed(deployment_date: date) -> tuple[int, str]:
    """Calculate days since deployment with formatted string."""
    days = (date.today() - deployment_date).days
    if days == 0:
        return days, "[cyan]Deployed today[/cyan]"
    elif days == 1:
        return days, "[cyan]1 day ago[/cyan]"
    elif days < 30:
        return days, f"[cyan]{days} days ago[/cyan]"
    elif days < 365:
        months = days // 30
        return days, f"[cyan]{months} month{'s' if months > 1 else ''} ago[/cyan] ({days} days)"
    else:
        years = days // 365
        return days, f"[cyan]{years} year{'s' if years > 1 else ''} ago[/cyan] ({days} days)"


def _calculate_days_until_review(next_review_date: date | None) -> tuple[int | None, str]:
    """Calculate days until next review with formatted string."""
    if next_review_date is None:
        return None, "[dim]Not scheduled[/dim]"

    days = (next_review_date - date.today()).days

    if days < 0:
        return days, f"[bold red]OVERDUE by {abs(days)} days[/bold red]"
    elif days == 0:
        return days, "[bold yellow]Due today[/bold yellow]"
    elif days == 1:
        return days, "[yellow]Due tomorrow[/yellow]"
    elif days <= 7:
        return days, f"[yellow]Due in {days} days[/yellow]"
    elif days <= 30:
        return days, f"[green]Due in {days} days[/green]"
    else:
        return days, f"[dim]Due in {days} days[/dim]"


def _format_date(d: date | None, label: str = "") -> str:
    """Format a date for display."""
    if d is None:
        return "[dim]—[/dim]"
    return str(d)


def _format_optional(value: str | None) -> str:
    """Format an optional string value."""
    if value is None or value == "":
        return "[dim]—[/dim]"
    return value


def _build_model_display(model: AIModel) -> None:
    """Build and display the model information."""
    # Calculate derived values
    days_deployed, deployed_str = _calculate_days_deployed(model.deployment_date)
    days_until_review, review_str = _calculate_days_until_review(model.next_review_date)

    # Header with model name and status
    header = f"[bold cyan]{model.model_name}[/bold cyan]"
    if model.model_version:
        header += f" [dim]v{model.model_version}[/dim]"

    # Risk badge
    risk_color = RISK_COLORS.get(model.risk_tier, "white")
    risk_badge = f"[{risk_color}]● {model.risk_tier.value.upper()} RISK[/{risk_color}]"

    # Build the main info table
    info_table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        expand=True,
    )
    info_table.add_column("Label", style="bold", width=20)
    info_table.add_column("Value")

    # Core Information Section
    console.print()
    console.print(Panel(
        f"{header}\n{risk_badge}",
        title="Model Details",
        title_align="left",
        border_style="cyan",
        padding=(1, 2),
    ))

    # Identity & Classification
    identity_table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    identity_table.add_column("Label", style="bold cyan", width=20)
    identity_table.add_column("Value")

    identity_table.add_row("ID", f"[dim]{model.id}[/dim]")
    identity_table.add_row("Vendor", model.vendor)
    identity_table.add_row("Risk Tier", _format_risk_tier(model.risk_tier))
    identity_table.add_row("Status", _format_status(model.status))
    if model.data_classification:
        identity_table.add_row("Data Classification", model.data_classification.value.upper())

    console.print(Panel(
        identity_table,
        title="[bold]Identity & Classification[/bold]",
        title_align="left",
        border_style="blue",
    ))

    # Use Case
    console.print(Panel(
        model.use_case,
        title="[bold]Use Case[/bold]",
        title_align="left",
        border_style="blue",
    ))

    # Ownership
    ownership_table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    ownership_table.add_column("Label", style="bold cyan", width=20)
    ownership_table.add_column("Value")

    ownership_table.add_row("Business Owner", model.business_owner)
    ownership_table.add_row("Technical Owner", model.technical_owner)

    console.print(Panel(
        ownership_table,
        title="[bold]Ownership[/bold]",
        title_align="left",
        border_style="blue",
    ))

    # Deployment
    deployment_table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    deployment_table.add_column("Label", style="bold cyan", width=20)
    deployment_table.add_column("Value")

    deployment_table.add_row("Deployment Date", f"{model.deployment_date}  {deployed_str}")
    if model.deployment_environment:
        deployment_table.add_row("Environment", model.deployment_environment.value.upper())
    if model.api_endpoint:
        deployment_table.add_row("API Endpoint", f"[link={model.api_endpoint}]{model.api_endpoint}[/link]")

    console.print(Panel(
        deployment_table,
        title="[bold]Deployment[/bold]",
        title_align="left",
        border_style="blue",
    ))

    # Review Schedule
    review_table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    review_table.add_column("Label", style="bold cyan", width=20)
    review_table.add_column("Value")

    review_table.add_row("Last Review", _format_date(model.last_review_date))
    review_table.add_row("Next Review", f"{_format_date(model.next_review_date)}  {review_str}")
    review_table.add_row("Review Cycle", f"{REVIEW_FREQUENCY[model.risk_tier]} days [dim](based on {model.risk_tier.value} risk)[/dim]")

    console.print(Panel(
        review_table,
        title="[bold]Review Schedule[/bold]",
        title_align="left",
        border_style="blue",
    ))

    # Notes (if present)
    if model.notes:
        console.print(Panel(
            model.notes,
            title="[bold]Notes[/bold]",
            title_align="left",
            border_style="blue",
        ))

    # Metadata
    metadata_table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    metadata_table.add_column("Label", style="bold dim", width=20)
    metadata_table.add_column("Value", style="dim")

    created = model.created_at.strftime("%Y-%m-%d %H:%M:%S") if model.created_at else "—"
    updated = model.updated_at.strftime("%Y-%m-%d %H:%M:%S") if model.updated_at else "—"

    metadata_table.add_row("Created", created)
    metadata_table.add_row("Last Updated", updated)

    console.print(Panel(
        metadata_table,
        title="[bold dim]Metadata[/bold dim]",
        title_align="left",
        border_style="dim",
    ))
    console.print()


def show_model(
    identifier: str = typer.Argument(
        ...,
        help="Model name or ID to display",
    ),
) -> None:
    """
    Show detailed information about a specific AI model.

    \b
    Examples:
      mltrack show claude-sonnet-4       # Show by name
      mltrack show 34be9c1a-491c-4dff    # Show by ID (partial match)
    """
    try:
        model = get_model(identifier)
        _build_model_display(model)
    except ModelNotFoundError:
        console.print(
            Panel(
                f"[red]Model not found:[/red] '{identifier}'\n\n"
                "[dim]Use [cyan]mltrack list[/cyan] to see all models in the inventory.[/dim]",
                title="Not Found",
                border_style="red",
            )
        )
        raise typer.Exit(1)
    except DatabaseError as e:
        console.print(f"[red]Database error:[/red] {e.details}")
        raise typer.Exit(1)
