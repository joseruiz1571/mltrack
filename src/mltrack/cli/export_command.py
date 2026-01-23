"""CLI command for exporting AI models to CSV/JSON files."""

import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel

from mltrack.core.storage import get_all_models
from mltrack.core.exceptions import DatabaseError
from mltrack.models.ai_model import (
    AIModel,
    RiskTier,
    DeploymentEnvironment,
    ModelStatus,
)

console = Console()

# CSV/JSON field order for export
EXPORT_FIELDS = [
    "model_name",
    "vendor",
    "risk_tier",
    "use_case",
    "business_owner",
    "technical_owner",
    "deployment_date",
    "model_version",
    "deployment_environment",
    "api_endpoint",
    "data_classification",
    "status",
    "last_review_date",
    "next_review_date",
    "notes",
    "created_at",
    "updated_at",
]

# Human-readable headers for CSV
CSV_HEADERS = {
    "model_name": "Model Name",
    "vendor": "Vendor",
    "risk_tier": "Risk Tier",
    "use_case": "Use Case",
    "business_owner": "Business Owner",
    "technical_owner": "Technical Owner",
    "deployment_date": "Deployment Date",
    "model_version": "Version",
    "deployment_environment": "Environment",
    "api_endpoint": "API Endpoint",
    "data_classification": "Data Classification",
    "status": "Status",
    "last_review_date": "Last Review Date",
    "next_review_date": "Next Review Date",
    "notes": "Notes",
    "created_at": "Created At",
    "updated_at": "Updated At",
}


def _parse_risk_tier(value: str | None) -> RiskTier | None:
    """Parse and validate risk tier string."""
    if value is None:
        return None
    try:
        return RiskTier(value.lower())
    except ValueError:
        return None


def _parse_environment(value: str | None) -> DeploymentEnvironment | None:
    """Parse and validate environment string."""
    if value is None:
        return None
    aliases = {
        "production": "prod",
        "stage": "staging",
        "development": "dev",
    }
    normalized = aliases.get(value.lower(), value.lower())
    try:
        return DeploymentEnvironment(normalized)
    except ValueError:
        return None


def _parse_status(value: str | None) -> ModelStatus | None:
    """Parse and validate status string."""
    if value is None:
        return None
    try:
        return ModelStatus(value.lower())
    except ValueError:
        return None


def _filter_models(
    models: list[AIModel],
    risk_tier: RiskTier | None = None,
    vendor: str | None = None,
    environment: DeploymentEnvironment | None = None,
    status: ModelStatus | None = None,
) -> list[AIModel]:
    """Filter models based on criteria."""
    filtered = models

    if risk_tier is not None:
        filtered = [m for m in filtered if m.risk_tier == risk_tier]

    if vendor is not None:
        vendor_lower = vendor.lower()
        filtered = [m for m in filtered if m.vendor and m.vendor.lower() == vendor_lower]

    if environment is not None:
        filtered = [m for m in filtered if m.deployment_environment == environment]

    if status is not None:
        filtered = [m for m in filtered if m.status == status]

    return filtered


def _model_to_dict(model: AIModel) -> dict[str, Any]:
    """Convert AIModel to dictionary for export."""
    data = {}

    for field in EXPORT_FIELDS:
        value = getattr(model, field, None)

        # Convert enums to string values
        if isinstance(value, (RiskTier, DeploymentEnvironment, ModelStatus)):
            value = value.value

        # Convert dates to ISO format strings
        if isinstance(value, date):
            value = value.isoformat()

        # Convert datetime to ISO format strings
        if isinstance(value, datetime):
            value = value.isoformat()

        data[field] = value if value is not None else ""

    return data


def _write_csv(
    file_path: Path,
    models: list[AIModel],
    use_readable_headers: bool = True,
) -> None:
    """Write models to CSV file."""
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        if use_readable_headers:
            headers = [CSV_HEADERS.get(field, field) for field in EXPORT_FIELDS]
        else:
            headers = EXPORT_FIELDS

        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)

        # Write header row
        if use_readable_headers:
            writer.writerow(dict(zip(EXPORT_FIELDS, headers)))
        else:
            writer.writeheader()

        # Write data rows
        for model in models:
            writer.writerow(_model_to_dict(model))


def _write_json(file_path: Path, models: list[AIModel], pretty: bool = True) -> None:
    """Write models to JSON file."""
    data = {
        "exported_at": datetime.now().isoformat(),
        "count": len(models),
        "models": [_model_to_dict(model) for model in models],
    }

    with open(file_path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            json.dump(data, f, ensure_ascii=False)


def _write_template(file_path: Path) -> None:
    """Write CSV template with headers only."""
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Write machine-readable headers for import compatibility
        writer.writerow(EXPORT_FIELDS)


def export_models(
    file: Path = typer.Argument(
        ...,
        help="Output file path (.csv or .json)",
    ),
    risk: str | None = typer.Option(
        None,
        "--risk",
        "-r",
        help="Filter by risk tier (critical, high, medium, low)",
    ),
    vendor: str | None = typer.Option(
        None,
        "--vendor",
        "-V",
        help="Filter by vendor name (case-insensitive)",
    ),
    environment: str | None = typer.Option(
        None,
        "--environment",
        "-e",
        help="Filter by environment (prod, staging, dev)",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (active, deprecated, decommissioned)",
    ),
    template: bool = typer.Option(
        False,
        "--template",
        "-t",
        help="Export empty CSV template with headers only",
    ),
    machine_headers: bool = typer.Option(
        False,
        "--machine-headers",
        help="Use machine-readable field names as CSV headers (for re-import)",
    ),
    compact: bool = typer.Option(
        False,
        "--compact",
        help="Compact JSON output (no indentation)",
    ),
) -> None:
    """
    Export AI models to a CSV or JSON file.

    By default exports all models. Use filters to export a subset.

    \b
    Examples:
      mltrack export inventory.csv
      mltrack export inventory.json
      mltrack export high-risk.csv --risk high
      mltrack export prod-models.json --environment prod
      mltrack export anthropic.csv --vendor anthropic
      mltrack export template.csv --template
      mltrack export backup.csv --machine-headers
    """
    # Determine file type
    suffix = file.suffix.lower()
    if suffix not in [".csv", ".json"]:
        console.print(
            Panel(
                f"[red]Unsupported file type:[/red] '{suffix}'\n\n"
                "[dim]Supported formats: .csv, .json[/dim]",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    # Handle template mode
    if template:
        if suffix != ".csv":
            console.print(
                Panel(
                    "[red]Template mode only supports CSV files[/red]",
                    title="[red]Error[/red]",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

        _write_template(file)
        console.print(
            Panel(
                f"[green]Template exported to:[/green] {file}\n\n"
                f"[dim]Contains {len(EXPORT_FIELDS)} columns ready for import[/dim]",
                title="[green]✓ Template Created[/green]",
                border_style="green",
            )
        )
        raise typer.Exit(0)

    # Parse and validate filters
    risk_tier = None
    if risk:
        risk_tier = _parse_risk_tier(risk)
        if risk_tier is None:
            valid = [t.value for t in RiskTier]
            console.print(
                Panel(
                    f"[red]Invalid risk tier:[/red] '{risk}'\n"
                    f"[dim]Valid options: {', '.join(valid)}[/dim]",
                    title="[red]Error[/red]",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

    env = None
    if environment:
        env = _parse_environment(environment)
        if env is None:
            valid = [e.value for e in DeploymentEnvironment]
            console.print(
                Panel(
                    f"[red]Invalid environment:[/red] '{environment}'\n"
                    f"[dim]Valid options: {', '.join(valid)}[/dim]",
                    title="[red]Error[/red]",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

    model_status = None
    if status:
        model_status = _parse_status(status)
        if model_status is None:
            valid = [s.value for s in ModelStatus]
            console.print(
                Panel(
                    f"[red]Invalid status:[/red] '{status}'\n"
                    f"[dim]Valid options: {', '.join(valid)}[/dim]",
                    title="[red]Error[/red]",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

    # Fetch models
    try:
        models = get_all_models()
    except DatabaseError as e:
        console.print(
            Panel(
                f"[red]Database error:[/red] {e.details}",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    # Apply filters
    models = _filter_models(models, risk_tier, vendor, env, model_status)

    if not models:
        filter_desc = []
        if risk_tier:
            filter_desc.append(f"risk={risk_tier.value}")
        if vendor:
            filter_desc.append(f"vendor={vendor}")
        if env:
            filter_desc.append(f"environment={env.value}")
        if model_status:
            filter_desc.append(f"status={model_status.value}")

        msg = "[yellow]No models found"
        if filter_desc:
            msg += f" matching filters: {', '.join(filter_desc)}"
        msg += "[/yellow]"

        console.print(
            Panel(
                msg,
                title="[yellow]Warning[/yellow]",
                border_style="yellow",
            )
        )
        raise typer.Exit(0)

    # Write file
    try:
        if suffix == ".csv":
            _write_csv(file, models, use_readable_headers=not machine_headers)
        else:
            _write_json(file, models, pretty=not compact)
    except IOError as e:
        console.print(
            Panel(
                f"[red]Failed to write file:[/red] {e}",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    # Build filter description for output
    filter_parts = []
    if risk_tier:
        filter_parts.append(f"risk={risk_tier.value}")
    if vendor:
        filter_parts.append(f"vendor={vendor}")
    if env:
        filter_parts.append(f"env={env.value}")
    if model_status:
        filter_parts.append(f"status={model_status.value}")

    filter_msg = ""
    if filter_parts:
        filter_msg = f"\n[dim]Filters: {', '.join(filter_parts)}[/dim]"

    console.print(
        Panel(
            f"[green]Exported {len(models)} model(s) to:[/green] {file}{filter_msg}",
            title="[green]✓ Export Successful[/green]",
            border_style="green",
        )
    )
