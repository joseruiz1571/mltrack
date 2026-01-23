"""CLI command for exporting AI models to CSV/JSON files."""

import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel

from mltrack.core.storage import get_all_models, iter_all_models, get_model_count
from mltrack.core.exceptions import DatabaseError

# Threshold for using streaming export (number of models)
STREAMING_THRESHOLD = 500
from mltrack.models.ai_model import (
    AIModel,
    RiskTier,
    DeploymentEnvironment,
    ModelStatus,
    DataClassification,
)
from mltrack.cli.error_helpers import (
    error_file_format,
    error_file_write,
    error_invalid_risk_tier,
    error_invalid_environment,
    error_invalid_status,
    error_database,
    warning_no_models,
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
        if isinstance(value, (RiskTier, DeploymentEnvironment, ModelStatus, DataClassification)):
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


def _write_csv_streaming(
    file_path: Path,
    model_iterator,
    use_readable_headers: bool = True,
) -> int:
    """Write models to CSV file using streaming for memory efficiency.

    Returns the number of models written.
    """
    count = 0
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

        # Write data rows from iterator
        for model in model_iterator:
            writer.writerow(_model_to_dict(model))
            count += 1

    return count


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


def _write_json_streaming(
    file_path: Path,
    model_iterator,
    pretty: bool = True,
) -> int:
    """Write models to JSON file using streaming for memory efficiency.

    Note: For JSON, we still need to build the full structure, but we
    process models one at a time to reduce peak memory usage.

    Returns the number of models written.
    """
    models_data = []
    for model in model_iterator:
        models_data.append(_model_to_dict(model))

    data = {
        "exported_at": datetime.now().isoformat(),
        "count": len(models_data),
        "models": models_data,
    }

    with open(file_path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            json.dump(data, f, ensure_ascii=False)

    return len(models_data)


def _write_template(file_path: Path) -> None:
    """Write CSV template with headers only."""
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Write machine-readable headers for import compatibility
        writer.writerow(EXPORT_FIELDS)


def export_models(
    file: Path = typer.Argument(
        ...,
        help="Output file path with .csv or .json extension",
    ),
    risk: str | None = typer.Option(
        None,
        "--risk",
        "-r",
        help="Export only models with this risk tier (critical/high/medium/low)",
    ),
    vendor: str | None = typer.Option(
        None,
        "--vendor",
        "-V",
        help="Export only models from this vendor (case-insensitive match)",
    ),
    environment: str | None = typer.Option(
        None,
        "--environment",
        "-e",
        help="Export only models in this environment (prod/staging/dev)",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Export only models with this status (active/deprecated/decommissioned)",
    ),
    template: bool = typer.Option(
        False,
        "--template",
        "-t",
        help="Create empty CSV with headers only (for manual data entry)",
    ),
    machine_headers: bool = typer.Option(
        False,
        "--machine-headers",
        help="Use database field names as CSV headers (for re-import compatibility)",
    ),
    compact: bool = typer.Option(
        False,
        "--compact",
        help="Minified JSON output without indentation (smaller file size)",
    ),
) -> None:
    """
    Export AI models to CSV or JSON file.

    Exports all models by default. Use filters to export specific subsets.
    File format is determined by the file extension (.csv or .json).

    \b
    [bold cyan]Output Formats:[/bold cyan]
      CSV     Human-readable headers by default, 17 columns
      JSON    Pretty-printed with metadata, includes export timestamp

    \b
    [bold cyan]Filters (can be combined):[/bold cyan]
      --risk        Export specific risk tier
      --vendor      Export specific vendor
      --environment Export specific environment
      --status      Export specific lifecycle status

    \b
    [bold cyan]CSV Options:[/bold cyan]
      [default]          Human-readable headers ("Model Name", "Risk Tier", etc.)
      --machine-headers  Database field names (model_name, risk_tier, etc.)
      --template         Empty file with headers only for manual entry

    \b
    [bold]Examples:[/bold]
      [dim]# Export all models[/dim]
      mltrack export inventory.csv
      mltrack export backup.json

      [dim]# Export with filters[/dim]
      mltrack export critical-models.csv --risk critical
      mltrack export production.json --environment prod
      mltrack export anthropic-models.csv --vendor anthropic
      mltrack export active.csv --status active

      [dim]# Combine multiple filters[/dim]
      mltrack export high-risk-prod.csv --risk high --environment prod

      [dim]# Create template for manual data entry[/dim]
      mltrack export template.csv --template

      [dim]# Export for re-import (machine-readable headers)[/dim]
      mltrack export backup.csv --machine-headers

      [dim]# Compact JSON (smaller file)[/dim]
      mltrack export backup.json --compact

    \b
    [bold cyan]Workflow Tips:[/bold cyan]
      • Use --template to get a blank spreadsheet for adding new models
      • Use --machine-headers when exporting for later re-import
      • JSON exports include an 'exported_at' timestamp for tracking

    \b
    [bold cyan]Related Commands:[/bold cyan]
      mltrack import <file>    Import from CSV/JSON
      mltrack list --json      Quick JSON output to stdout
      mltrack report inventory Generate formatted inventory report
    """
    # Determine file type
    suffix = file.suffix.lower()
    if suffix not in [".csv", ".json"]:
        error_file_format(str(file), [".csv", ".json"], suffix)
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
            error_invalid_risk_tier(risk)
            raise typer.Exit(1)

    env = None
    if environment:
        env = _parse_environment(environment)
        if env is None:
            error_invalid_environment(environment)
            raise typer.Exit(1)

    model_status = None
    if status:
        model_status = _parse_status(status)
        if model_status is None:
            error_invalid_status(status)
            raise typer.Exit(1)

    # Check total count to decide if we should use streaming
    try:
        total_count = get_model_count(
            risk_tier=risk_tier,
            status=model_status,
            vendor=vendor,
        )
    except DatabaseError as e:
        error_database(e.operation, e.details)
        raise typer.Exit(1)

    # Use streaming for large exports (note: environment filter requires post-processing)
    use_streaming = total_count > STREAMING_THRESHOLD and env is None

    if use_streaming:
        console.print(f"[dim]Large export ({total_count} models), using streaming mode...[/dim]")

    # Fetch models
    try:
        if use_streaming:
            # Use iterator for memory efficiency
            model_iterator = iter_all_models(
                risk_tier=risk_tier,
                status=model_status,
                vendor=vendor,
            )
            # For streaming, we write directly and skip the filter step
            models = None
        else:
            models = get_all_models(
                risk_tier=risk_tier,
                status=model_status,
                vendor=vendor,
            )
    except DatabaseError as e:
        error_database(e.operation, e.details)
        raise typer.Exit(1)

    # Apply environment filter (only for non-streaming mode)
    if models is not None:
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

            filter_description = ", ".join(filter_desc) if filter_desc else None
            warning_no_models(filter_description)
            raise typer.Exit(0)

    # Write file
    try:
        if use_streaming:
            # Use streaming functions for large exports
            if suffix == ".csv":
                export_count = _write_csv_streaming(
                    file, model_iterator, use_readable_headers=not machine_headers
                )
            else:
                export_count = _write_json_streaming(file, model_iterator, pretty=not compact)
        else:
            # Standard export for smaller datasets
            if suffix == ".csv":
                _write_csv(file, models, use_readable_headers=not machine_headers)
            else:
                _write_json(file, models, pretty=not compact)
            export_count = len(models)
    except IOError as e:
        error_file_write(str(file), str(e))
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
            f"[green]Exported {export_count} model(s) to:[/green] {file}{filter_msg}",
            title="[green]✓ Export Successful[/green]",
            border_style="green",
        )
    )
