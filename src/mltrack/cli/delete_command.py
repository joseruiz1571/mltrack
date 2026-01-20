"""CLI command for deleting AI models from the inventory."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm
from rich import box

from mltrack.core.storage import get_model, delete_model, update_model, REVIEW_FREQUENCY
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
    """Format risk tier with color."""
    color = RISK_COLORS.get(tier, "white")
    return f"[{color}]{tier.value.upper()}[/{color}]"


def _format_status(status: ModelStatus) -> str:
    """Format status with color."""
    color = STATUS_COLORS.get(status, "white")
    return f"[{color}]{status.value.upper()}[/{color}]"


def _build_model_summary(model: AIModel) -> Table:
    """Build a summary table of the model to be deleted."""
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("ID", f"[dim]{model.id}[/dim]")
    table.add_row("Name", f"[cyan]{model.model_name}[/cyan]")
    table.add_row("Vendor", model.vendor)
    table.add_row("Risk Tier", _format_risk_tier(model.risk_tier))
    table.add_row("Status", _format_status(model.status))
    table.add_row("Use Case", model.use_case[:60] + "..." if len(model.use_case) > 60 else model.use_case)
    table.add_row("Business Owner", model.business_owner)
    table.add_row("Technical Owner", model.technical_owner)
    table.add_row("Deployed", str(model.deployment_date))

    if model.deployment_environment:
        table.add_row("Environment", model.deployment_environment.value.upper())

    return table


def delete_model_command(
    identifier: str = typer.Argument(
        ...,
        help="Model name or ID to delete",
    ),
    soft: bool = typer.Option(
        False,
        "--soft",
        help="Soft delete: set status to 'decommissioned' instead of removing",
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt (for automation)",
    ),
) -> None:
    """
    Delete an AI model from the inventory.

    By default, this permanently removes the model from the database.
    Use --soft to mark the model as 'decommissioned' instead (recommended
    for audit trail preservation).

    \b
    Examples:
      mltrack delete "old-model"              # Hard delete with confirmation
      mltrack delete "old-model" --soft       # Soft delete (decommission)
      mltrack delete "old-model" -y           # Skip confirmation
      mltrack delete abc123 --soft -y         # Soft delete by ID, no prompt
    """
    # First, fetch the existing model
    try:
        model = get_model(identifier)
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

    # Check if already decommissioned (for soft delete)
    if soft and model.status == ModelStatus.DECOMMISSIONED:
        console.print(
            Panel(
                f"[yellow]Model '[bold]{model.model_name}[/bold]' is already decommissioned.[/yellow]",
                title="Already Decommissioned",
                border_style="yellow",
            )
        )
        raise typer.Exit(0)

    # Show model details
    console.print()
    summary_table = _build_model_summary(model)

    if soft:
        # Soft delete warning
        console.print(
            Panel(
                summary_table,
                title="[yellow]Model to Decommission[/yellow]",
                border_style="yellow",
                subtitle="[dim]Status will be set to DECOMMISSIONED[/dim]",
            )
        )
        console.print()
        console.print(
            "[yellow]This will mark the model as decommissioned.[/yellow]\n"
            "[dim]The model will remain in the database for audit purposes but will be hidden from active listings.[/dim]"
        )
    else:
        # Hard delete warning
        console.print(
            Panel(
                summary_table,
                title="[bold red]Model to Delete[/bold red]",
                border_style="red",
                subtitle="[dim]This action cannot be undone[/dim]",
            )
        )
        console.print()
        console.print(
            "[bold red]WARNING:[/bold red] This will [bold]permanently delete[/bold] the model from the database.\n"
            "[dim]Consider using [cyan]--soft[/cyan] to decommission instead (preserves audit trail).[/dim]"
        )

    console.print()

    # Confirm unless --yes flag is set
    if not yes:
        if soft:
            prompt = f"[bold]Decommission '{model.model_name}'?[/bold]"
        else:
            prompt = f"[bold red]Permanently delete '{model.model_name}'?[/bold red]"

        if not Confirm.ask(prompt, default=False):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    # Perform the deletion
    try:
        if soft:
            # Soft delete - update status
            update_model(identifier, {"status": "decommissioned"})
            console.print(
                Panel(
                    f"[green]✓ Model '[bold]{model.model_name}[/bold]' has been decommissioned.[/green]\n\n"
                    "[dim]The model is now hidden from active listings but preserved for audit purposes.\n"
                    f"View with: [cyan]mltrack show {model.model_name}[/cyan][/dim]",
                    title="Decommissioned",
                    border_style="green",
                )
            )
        else:
            # Hard delete
            delete_model(identifier)
            console.print(
                Panel(
                    f"[green]✓ Model '[bold]{model.model_name}[/bold]' has been permanently deleted.[/green]",
                    title="Deleted",
                    border_style="green",
                )
            )
    except DatabaseError as e:
        console.print(f"[red]Database error:[/red] {e.details}")
        raise typer.Exit(1)
