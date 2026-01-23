"""CLI command for updating AI models in the inventory."""

from datetime import date
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm
from rich import box

from mltrack.core.storage import get_model, update_model, REVIEW_FREQUENCY
from mltrack.core.exceptions import (
    ModelNotFoundError,
    ModelAlreadyExistsError,
    ValidationError,
    DatabaseError,
)
from mltrack.models import RiskTier, DeploymentEnvironment, DataClassification, ModelStatus, AIModel

console = Console()

# Valid enum values for help text
RISK_TIERS = [t.value for t in RiskTier]
ENVIRONMENTS = [e.value for e in DeploymentEnvironment]
DATA_CLASSIFICATIONS = [c.value for c in DataClassification]
STATUSES = [s.value for s in ModelStatus]

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


def _validate_risk_tier(value: str) -> str:
    """Validate risk tier value."""
    normalized = value.lower()
    if normalized not in RISK_TIERS:
        raise typer.BadParameter(
            f"Invalid risk tier: '{value}'. Must be one of: {', '.join(RISK_TIERS)}"
        )
    return normalized


def _validate_status(value: str) -> str:
    """Validate status value."""
    normalized = value.lower()
    if normalized not in STATUSES:
        raise typer.BadParameter(
            f"Invalid status: '{value}'. Must be one of: {', '.join(STATUSES)}"
        )
    return normalized


def _validate_environment(value: str) -> str:
    """Validate deployment environment value."""
    normalized = value.lower()
    # Handle common aliases
    if normalized in ("production", "prd"):
        normalized = "prod"
    elif normalized in ("development",):
        normalized = "dev"
    elif normalized in ("stg",):
        normalized = "staging"

    if normalized not in ENVIRONMENTS:
        raise typer.BadParameter(
            f"Invalid environment: '{value}'. Must be one of: {', '.join(ENVIRONMENTS)}"
        )
    return normalized


def _validate_data_classification(value: str) -> str:
    """Validate data classification value."""
    normalized = value.lower()
    if normalized not in DATA_CLASSIFICATIONS:
        raise typer.BadParameter(
            f"Invalid classification: '{value}'. Must be one of: {', '.join(DATA_CLASSIFICATIONS)}"
        )
    return normalized


def _validate_date(value: str) -> date:
    """Validate and parse date string."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise typer.BadParameter(
            f"Invalid date format: '{value}'. Use YYYY-MM-DD (e.g., 2025-01-15)"
        )


def _format_value(value, field_type: str = "text") -> str:
    """Format a value for display."""
    if value is None:
        return "[dim]—[/dim]"

    if field_type == "risk_tier" and isinstance(value, RiskTier):
        color = RISK_COLORS.get(value, "white")
        return f"[{color}]{value.value.upper()}[/{color}]"

    if field_type == "status" and isinstance(value, ModelStatus):
        color = STATUS_COLORS.get(value, "white")
        return f"[{color}]{value.value.upper()}[/{color}]"

    if field_type == "environment" and isinstance(value, DeploymentEnvironment):
        return value.value.upper()

    if field_type == "classification" and isinstance(value, DataClassification):
        return value.value.upper()

    if isinstance(value, date):
        return str(value)

    return str(value)


def _build_comparison_table(model: AIModel, updates: dict) -> Table:
    """Build a comparison table showing before/after values."""
    table = Table(
        title="Proposed Changes",
        show_header=True,
        header_style="bold",
        box=box.ROUNDED,
    )
    table.add_column("Field", style="bold")
    table.add_column("Current Value")
    table.add_column("", style="dim", width=3)
    table.add_column("New Value")

    # Field mappings for display
    field_info = {
        "model_name": ("Model Name", "text"),
        "vendor": ("Vendor", "text"),
        "model_version": ("Version", "text"),
        "risk_tier": ("Risk Tier", "risk_tier"),
        "use_case": ("Use Case", "text"),
        "business_owner": ("Business Owner", "text"),
        "technical_owner": ("Technical Owner", "text"),
        "deployment_date": ("Deployment Date", "date"),
        "deployment_environment": ("Environment", "environment"),
        "api_endpoint": ("API Endpoint", "text"),
        "data_classification": ("Data Classification", "classification"),
        "status": ("Status", "status"),
        "last_review_date": ("Last Review Date", "date"),
        "notes": ("Notes", "text"),
    }

    for field, (display_name, field_type) in field_info.items():
        if field in updates:
            current_value = getattr(model, field)
            new_value = updates[field]

            current_formatted = _format_value(current_value, field_type)
            new_formatted = _format_value(new_value, field_type)

            table.add_row(
                display_name,
                current_formatted,
                "→",
                f"[green]{new_formatted}[/green]",
            )

    # Show if next_review_date will be recalculated
    if "risk_tier" in updates:
        new_risk = updates["risk_tier"]
        if isinstance(new_risk, str):
            new_risk = RiskTier(new_risk.lower())
        new_days = REVIEW_FREQUENCY[new_risk]
        table.add_row(
            "[dim]Review Cycle[/dim]",
            f"[dim]{REVIEW_FREQUENCY[model.risk_tier]} days[/dim]",
            "→",
            f"[dim green]{new_days} days (auto-updated)[/dim green]",
        )

    return table


def update_model_command(
    identifier: str = typer.Argument(
        ...,
        help="Model name or UUID to update (partial ID match supported)",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name", "-n",
        help="Rename the model (must be unique)",
    ),
    vendor: Optional[str] = typer.Option(
        None,
        "--vendor",
        help="Change the vendor/provider",
    ),
    version: Optional[str] = typer.Option(
        None,
        "--version",
        help="Update the model version identifier",
    ),
    risk_tier: Optional[str] = typer.Option(
        None,
        "--risk-tier", "-r",
        help=f"Change risk classification (auto-updates review cycle): {', '.join(RISK_TIERS)}",
    ),
    use_case: Optional[str] = typer.Option(
        None,
        "--use-case", "-u",
        help="Update the business use case description",
    ),
    business_owner: Optional[str] = typer.Option(
        None,
        "--business-owner", "-b",
        help="Change the accountable business stakeholder",
    ),
    technical_owner: Optional[str] = typer.Option(
        None,
        "--technical-owner", "-t",
        help="Change the technical owner/team",
    ),
    deployment_date: Optional[str] = typer.Option(
        None,
        "--deployment-date", "-d",
        help="Correct the deployment date (YYYY-MM-DD format)",
    ),
    environment: Optional[str] = typer.Option(
        None,
        "--environment", "-e",
        help=f"Change deployment environment: {', '.join(ENVIRONMENTS)}",
    ),
    api_endpoint: Optional[str] = typer.Option(
        None,
        "--api-endpoint",
        help="Update the API endpoint URL",
    ),
    data_classification: Optional[str] = typer.Option(
        None,
        "--data-classification",
        help=f"Set data sensitivity level: {', '.join(DATA_CLASSIFICATIONS)}",
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status", "-s",
        help=f"Change lifecycle status: {', '.join(STATUSES)}",
    ),
    last_review_date: Optional[str] = typer.Option(
        None,
        "--last-review-date",
        help="Manually set last review date (YYYY-MM-DD) - prefer 'mltrack reviewed' instead",
    ),
    notes: Optional[str] = typer.Option(
        None,
        "--notes",
        help="Replace notes with new content (for appending, edit directly)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt and apply changes immediately",
    ),
) -> None:
    """
    Modify attributes of an existing AI model.

    Specify the model by name or ID, then provide one or more fields to change.
    Shows a before/after comparison before applying changes.

    [bold]Note:[/bold] Only specified fields are modified; all others remain unchanged.

    \b
    [bold cyan]Common Updates:[/bold cyan]
      --risk-tier     Upgrade/downgrade risk (auto-updates review schedule)
      --status        Mark as deprecated or decommissioned
      --environment   Move between dev/staging/prod
      --business-owner / --technical-owner  Transfer ownership

    \b
    [bold cyan]Special Behavior:[/bold cyan]
      • Changing --risk-tier automatically recalculates the next review date
      • Use 'mltrack reviewed' instead of --last-review-date to properly record reviews
      • Use 'mltrack delete --soft' instead of --status decommissioned for audit trail

    \b
    [bold]Examples:[/bold]
      [dim]# Upgrade risk tier (recalculates review schedule)[/dim]
      mltrack update "claude-sonnet-4" --risk-tier critical

      [dim]# Mark model as deprecated with notes[/dim]
      mltrack update "old-model" --status deprecated --notes "Replaced by v2"

      [dim]# Transfer ownership[/dim]
      mltrack update "fraud-detector" -b "New Owner (Risk)" -t "New Team"

      [dim]# Promote to production[/dim]
      mltrack update "chatbot-v2" --environment prod --data-classification confidential

      [dim]# Skip confirmation for automation[/dim]
      mltrack update "model-name" --vendor "New Vendor" -y

    \b
    [bold cyan]Related Commands:[/bold cyan]
      mltrack show <name>       View current model details
      mltrack reviewed <name>   Record a model review
      mltrack delete <name>     Remove or decommission a model
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

    # Build updates dictionary with validation
    updates = {}

    try:
        if name is not None:
            updates["model_name"] = name.strip()

        if vendor is not None:
            updates["vendor"] = vendor.strip()

        if version is not None:
            updates["model_version"] = version.strip()

        if risk_tier is not None:
            validated = _validate_risk_tier(risk_tier)
            updates["risk_tier"] = validated

        if use_case is not None:
            updates["use_case"] = use_case.strip()

        if business_owner is not None:
            updates["business_owner"] = business_owner.strip()

        if technical_owner is not None:
            updates["technical_owner"] = technical_owner.strip()

        if deployment_date is not None:
            updates["deployment_date"] = _validate_date(deployment_date)

        if environment is not None:
            validated = _validate_environment(environment)
            updates["deployment_environment"] = validated

        if api_endpoint is not None:
            updates["api_endpoint"] = api_endpoint.strip()

        if data_classification is not None:
            validated = _validate_data_classification(data_classification)
            updates["data_classification"] = validated

        if status is not None:
            validated = _validate_status(status)
            updates["status"] = validated

        if last_review_date is not None:
            updates["last_review_date"] = _validate_date(last_review_date)

        if notes is not None:
            updates["notes"] = notes.strip()

    except typer.BadParameter as e:
        console.print(f"[red]Validation error:[/red] {e.message}")
        raise typer.Exit(1)

    # Check if any updates were provided
    if not updates:
        console.print(
            Panel(
                "[yellow]No changes specified.[/yellow]\n\n"
                "[dim]Provide at least one field to update. See available options with:[/dim]\n"
                "[cyan]mltrack update --help[/cyan]",
                title="No Changes",
                border_style="yellow",
            )
        )
        raise typer.Exit(0)

    # Show comparison table
    console.print()
    console.print(
        Panel(
            f"Updating model: [bold cyan]{model.model_name}[/bold cyan]",
            border_style="blue",
        )
    )

    comparison_table = _build_comparison_table(model, updates)
    console.print(comparison_table)
    console.print()

    # Confirm unless --yes flag is set
    if not yes:
        if not Confirm.ask("[bold]Apply these changes?[/bold]", default=True):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    # Apply the update
    try:
        updated_model = update_model(identifier, updates)
    except ModelAlreadyExistsError:
        console.print(
            Panel(
                f"[red]A model named '[bold]{updates.get('model_name', '')}[/bold]' already exists.[/red]\n\n"
                "[dim]Choose a different name.[/dim]",
                title="[red]Duplicate Name[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)
    except ValidationError as e:
        console.print(f"[red]Validation error:[/red] {e.message}")
        raise typer.Exit(1)
    except DatabaseError as e:
        console.print(f"[red]Database error:[/red] {e.details}")
        raise typer.Exit(1)

    # Success message
    console.print(
        Panel(
            f"[green]✓ Model updated successfully[/green]\n\n"
            f"[dim]View full details with:[/dim] [cyan]mltrack show {updated_model.model_name}[/cyan]",
            title="Success",
            border_style="green",
        )
    )
