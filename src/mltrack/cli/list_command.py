"""CLI command for listing AI models in the inventory."""

import csv
import json
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from mltrack.core.storage import get_all_models
from mltrack.core.exceptions import DatabaseError
from mltrack.models import RiskTier, DeploymentEnvironment, ModelStatus, AIModel
from mltrack.cli.error_helpers import (
    error_invalid_risk_tier,
    error_invalid_status,
    error_invalid_environment,
    error_database,
    warning_no_models,
)

console = Console()

# Valid enum values for help text
RISK_TIERS = [t.value for t in RiskTier]
ENVIRONMENTS = [e.value for e in DeploymentEnvironment]
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


def _format_risk_tier(tier: RiskTier) -> str:
    """Format risk tier with color."""
    color = RISK_COLORS.get(tier, "white")
    return f"[{color}]{tier.value.upper()}[/{color}]"


def _format_status(status: ModelStatus) -> str:
    """Format status with color."""
    color = STATUS_COLORS.get(status, "white")
    return f"[{color}]{status.value.upper()}[/{color}]"


def _truncate(text: str, max_length: int = 40) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def _parse_risk_tier(value: str) -> Optional[RiskTier]:
    """Parse risk tier from string."""
    try:
        return RiskTier(value.lower())
    except ValueError:
        return None


def _parse_status(value: str) -> Optional[ModelStatus]:
    """Parse status from string."""
    try:
        return ModelStatus(value.lower())
    except ValueError:
        return None


def _model_to_dict(model: AIModel) -> dict:
    """Convert model to dictionary for JSON/CSV export."""
    return {
        "id": model.id,
        "model_name": model.model_name,
        "vendor": model.vendor,
        "model_version": model.model_version,
        "risk_tier": model.risk_tier.value,
        "use_case": model.use_case,
        "business_owner": model.business_owner,
        "technical_owner": model.technical_owner,
        "deployment_date": model.deployment_date.isoformat(),
        "deployment_environment": model.deployment_environment.value if model.deployment_environment else None,
        "api_endpoint": model.api_endpoint,
        "last_review_date": model.last_review_date.isoformat() if model.last_review_date else None,
        "next_review_date": model.next_review_date.isoformat() if model.next_review_date else None,
        "data_classification": model.data_classification.value if model.data_classification else None,
        "status": model.status.value,
        "notes": model.notes,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }


def _create_table(models: list[AIModel], verbose: bool = False) -> Table:
    """Create a Rich table for displaying models."""
    if verbose:
        table = Table(
            title=f"AI Model Inventory ({len(models)} models)",
            show_header=True,
            header_style="bold cyan",
            box=box.ROUNDED,
            show_lines=True,
        )

        table.add_column("ID", style="dim", max_width=12)
        table.add_column("Model Name", style="cyan", no_wrap=True)
        table.add_column("Vendor")
        table.add_column("Version")
        table.add_column("Risk", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Business Owner")
        table.add_column("Technical Owner")
        table.add_column("Use Case", max_width=30)
        table.add_column("Deployed")
        table.add_column("Environment")
        table.add_column("Next Review")
        table.add_column("Data Class")

        for model in models:
            env = model.deployment_environment.value.upper() if model.deployment_environment else "-"
            data_class = model.data_classification.value.upper() if model.data_classification else "-"
            next_review = str(model.next_review_date) if model.next_review_date else "-"

            # Highlight overdue reviews
            if model.next_review_date and model.next_review_date < date.today():
                next_review = f"[red]{next_review}[/red]"

            table.add_row(
                model.id[:8] + "...",
                model.model_name,
                model.vendor,
                model.model_version or "-",
                _format_risk_tier(model.risk_tier),
                _format_status(model.status),
                model.business_owner,
                model.technical_owner,
                _truncate(model.use_case, 30),
                str(model.deployment_date),
                env,
                next_review,
                data_class,
            )
    else:
        # Compact view
        table = Table(
            title=f"AI Model Inventory ({len(models)} models)",
            show_header=True,
            header_style="bold cyan",
            box=box.ROUNDED,
        )

        table.add_column("Model Name", style="cyan", no_wrap=True)
        table.add_column("Vendor")
        table.add_column("Risk", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Use Case", max_width=40)
        table.add_column("Deployed")

        for model in models:
            table.add_row(
                model.model_name,
                model.vendor,
                _format_risk_tier(model.risk_tier),
                _format_status(model.status),
                _truncate(model.use_case, 40),
                str(model.deployment_date),
            )

    return table


def _export_csv(models: list[AIModel], output_path: Path) -> None:
    """Export models to CSV file."""
    if not models:
        console.print("[yellow]No models to export.[/yellow]")
        return

    fieldnames = [
        "id", "model_name", "vendor", "model_version", "risk_tier",
        "use_case", "business_owner", "technical_owner", "deployment_date",
        "deployment_environment", "api_endpoint", "last_review_date",
        "next_review_date", "data_classification", "status", "notes",
        "created_at", "updated_at"
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for model in models:
            writer.writerow(_model_to_dict(model))

    console.print(f"[green]✓ Exported {len(models)} models to {output_path}[/green]")


def _output_json(models: list[AIModel]) -> None:
    """Output models as JSON."""
    data = [_model_to_dict(model) for model in models]
    # Use print directly for clean JSON output (no Rich formatting)
    print(json.dumps(data, indent=2))


def list_models(
    risk: Optional[str] = typer.Option(
        None,
        "--risk", "-r",
        help=f"Show only models with this risk tier: {', '.join(RISK_TIERS)}",
    ),
    vendor: Optional[str] = typer.Option(
        None,
        "--vendor",
        help="Show only models from this vendor (case-insensitive match)",
    ),
    environment: Optional[str] = typer.Option(
        None,
        "--environment", "-e",
        help=f"Show only models in this environment: {', '.join(ENVIRONMENTS)} (aliases: production, development)",
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status", "-s",
        help=f"Show only models with this status: {', '.join(STATUSES)}",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show all fields including IDs, owners, versions, and review dates",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON array (for scripting, piping to jq, etc.)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Export results to CSV file instead of displaying",
    ),
) -> None:
    """
    Display AI models in the inventory with optional filtering.

    By default shows a compact table with key fields. Use filters to narrow
    results or combine multiple filters for precise queries.

    \b
    [bold cyan]Filters (can be combined):[/bold cyan]
      --risk        Filter by risk tier (critical/high/medium/low)
      --vendor      Filter by vendor name (case-insensitive)
      --environment Filter by deployment environment (prod/staging/dev)
      --status      Filter by lifecycle status (active/deprecated/decommissioned)

    \b
    [bold cyan]Output Formats:[/bold cyan]
      [default]     Rich table in terminal
      --verbose     Extended table with all fields
      --json        JSON array for scripting
      --output      Export to CSV file

    \b
    [bold]Examples:[/bold]
      [dim]# List all models[/dim]
      mltrack list

      [dim]# Filter by risk tier[/dim]
      mltrack list --risk critical
      mltrack list -r high

      [dim]# Filter by vendor (case-insensitive)[/dim]
      mltrack list --vendor anthropic
      mltrack list --vendor "In-house"

      [dim]# Combine filters[/dim]
      mltrack list --risk high --environment prod
      mltrack list --vendor openai --status active

      [dim]# Verbose output with all fields[/dim]
      mltrack list -v

      [dim]# Export to CSV[/dim]
      mltrack list -o inventory.csv
      mltrack list --risk critical -o critical-models.csv

      [dim]# JSON for scripting[/dim]
      mltrack list --json
      mltrack list --json | jq '.[].model_name'
    """
    # Parse and validate filters
    risk_filter = None
    if risk:
        risk_filter = _parse_risk_tier(risk)
        if risk_filter is None:
            error_invalid_risk_tier(risk)
            raise typer.Exit(1)

    status_filter = None
    if status:
        status_filter = _parse_status(status)
        if status_filter is None:
            error_invalid_status(status)
            raise typer.Exit(1)

    # Fetch models
    try:
        models = get_all_models(
            risk_tier=risk_filter,
            status=status_filter,
            vendor=vendor,
        )
    except DatabaseError as e:
        error_database(e.operation, e.details)
        raise typer.Exit(1)

    # Apply environment filter (not supported by get_all_models directly)
    if environment:
        env_lower = environment.lower()
        # Handle aliases
        if env_lower in ("production", "prd"):
            env_lower = "prod"
        elif env_lower == "development":
            env_lower = "dev"
        elif env_lower == "stg":
            env_lower = "staging"

        try:
            env_enum = DeploymentEnvironment(env_lower)
            models = [m for m in models if m.deployment_environment == env_enum]
        except ValueError:
            error_invalid_environment(environment)
            raise typer.Exit(1)

    # Handle output formats
    if json_output:
        _output_json(models)
        return

    if output:
        _export_csv(models, output)
        return

    # Display table
    if not models:
        # Show helpful message based on filters
        filter_parts = []
        if risk:
            filter_parts.append(f"risk={risk}")
        if vendor:
            filter_parts.append(f"vendor={vendor}")
        if environment:
            filter_parts.append(f"environment={environment}")
        if status:
            filter_parts.append(f"status={status}")

        filter_description = ", ".join(filter_parts) if filter_parts else None
        warning_no_models(filter_description)
        return

    table = _create_table(models, verbose=verbose)
    console.print()
    console.print(table)
    console.print()

    # Show summary
    risk_counts = {}
    for model in models:
        tier = model.risk_tier.value
        risk_counts[tier] = risk_counts.get(tier, 0) + 1

    summary_parts = []
    for tier in ["critical", "high", "medium", "low"]:
        if tier in risk_counts:
            color = RISK_COLORS.get(RiskTier(tier), "white")
            summary_parts.append(f"[{color}]{risk_counts[tier]} {tier.upper()}[/{color}]")

    if summary_parts:
        console.print(f"[dim]Risk distribution:[/dim] {' | '.join(summary_parts)}")
