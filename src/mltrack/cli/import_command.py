"""CLI command for importing AI models from CSV/JSON files."""

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box

from mltrack.core.storage import create_model, get_model, update_model
from mltrack.core.database import session_scope
from mltrack.core.exceptions import (
    ModelAlreadyExistsError,
    ModelNotFoundError,
    ValidationError,
    DatabaseError,
)
from mltrack.models import RiskTier, DeploymentEnvironment, DataClassification

console = Console()

# Field mapping from common CSV/JSON field names to database schema
FIELD_MAPPINGS = {
    # Model name variations
    "model_name": "model_name",
    "name": "model_name",
    "model": "model_name",
    # Vendor
    "vendor": "vendor",
    "provider": "vendor",
    # Risk tier
    "risk_tier": "risk_tier",
    "risk": "risk_tier",
    "tier": "risk_tier",
    "risk_level": "risk_tier",
    # Use case
    "use_case": "use_case",
    "usecase": "use_case",
    "description": "use_case",
    # Business owner
    "business_owner": "business_owner",
    "businessowner": "business_owner",
    "owner": "business_owner",
    # Technical owner
    "technical_owner": "technical_owner",
    "technicalowner": "technical_owner",
    "tech_owner": "technical_owner",
    # Deployment date
    "deployment_date": "deployment_date",
    "deploymentdate": "deployment_date",
    "deploy_date": "deployment_date",
    "deployed": "deployment_date",
    "deployed_at": "deployment_date",
    # Version
    "model_version": "model_version",
    "version": "model_version",
    # Environment
    "deployment_environment": "deployment_environment",
    "environment": "deployment_environment",
    "env": "deployment_environment",
    # API endpoint
    "api_endpoint": "api_endpoint",
    "endpoint": "api_endpoint",
    "url": "api_endpoint",
    # Data classification
    "data_classification": "data_classification",
    "classification": "data_classification",
    "data_class": "data_classification",
    # Notes
    "notes": "notes",
    "note": "notes",
    "comments": "notes",
}

REQUIRED_FIELDS = [
    "model_name",
    "vendor",
    "risk_tier",
    "use_case",
    "business_owner",
    "technical_owner",
    "deployment_date",
]


def _normalize_field_name(field: str) -> str | None:
    """Normalize field name to database schema field."""
    normalized = field.lower().strip().replace("-", "_").replace(" ", "_")
    return FIELD_MAPPINGS.get(normalized)


def _parse_date(value: str | date) -> date | None:
    """Parse date from string or date object."""
    if isinstance(value, date):
        return value
    if not value or not value.strip():
        return None
    value = value.strip()
    # Try ISO format first
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    # Try common formats
    for fmt in ["%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"]:
        try:
            from datetime import datetime
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_risk_tier(value: str) -> str | None:
    """Parse and validate risk tier."""
    if not value:
        return None
    normalized = value.lower().strip()
    valid_tiers = [t.value for t in RiskTier]
    if normalized in valid_tiers:
        return normalized
    return None


def _parse_environment(value: str) -> str | None:
    """Parse and validate deployment environment."""
    if not value:
        return None
    normalized = value.lower().strip()
    # Handle aliases
    aliases = {
        "production": "prod",
        "prd": "prod",
        "development": "dev",
        "stg": "staging",
        "stage": "staging",
    }
    normalized = aliases.get(normalized, normalized)
    valid_envs = [e.value for e in DeploymentEnvironment]
    if normalized in valid_envs:
        return normalized
    return None


def _parse_data_classification(value: str) -> str | None:
    """Parse and validate data classification."""
    if not value:
        return None
    normalized = value.lower().strip()
    valid_classes = [c.value for c in DataClassification]
    if normalized in valid_classes:
        return normalized
    return None


def _map_record(raw_record: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Map raw record fields to database schema. Returns (mapped_data, errors)."""
    mapped = {}
    errors = []

    for raw_field, value in raw_record.items():
        db_field = _normalize_field_name(raw_field)
        if db_field:
            # Convert value to string if not already
            if value is not None and not isinstance(value, (str, date)):
                value = str(value)
            mapped[db_field] = value

    # Validate and transform specific fields
    if "deployment_date" in mapped:
        parsed_date = _parse_date(mapped["deployment_date"])
        if parsed_date:
            mapped["deployment_date"] = parsed_date
        else:
            errors.append(f"Invalid date format: '{mapped['deployment_date']}'")

    if "risk_tier" in mapped:
        parsed_tier = _parse_risk_tier(mapped["risk_tier"])
        if parsed_tier:
            mapped["risk_tier"] = parsed_tier
        else:
            errors.append(f"Invalid risk tier: '{mapped['risk_tier']}' (must be critical/high/medium/low)")

    if "deployment_environment" in mapped and mapped["deployment_environment"]:
        parsed_env = _parse_environment(mapped["deployment_environment"])
        if parsed_env:
            mapped["deployment_environment"] = parsed_env
        else:
            errors.append(f"Invalid environment: '{mapped['deployment_environment']}' (must be prod/staging/dev)")

    if "data_classification" in mapped and mapped["data_classification"]:
        parsed_class = _parse_data_classification(mapped["data_classification"])
        if parsed_class:
            mapped["data_classification"] = parsed_class
        else:
            errors.append(f"Invalid classification: '{mapped['data_classification']}'")

    # Strip string values
    for key, value in mapped.items():
        if isinstance(value, str):
            mapped[key] = value.strip()

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in mapped or not mapped[field]:
            errors.append(f"Missing required field: '{field}'")

    return mapped, errors


def _read_csv(file_path: Path) -> list[dict[str, Any]]:
    """Read records from CSV file."""
    records = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        # Try to detect delimiter
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(f, dialect=dialect)
        for row in reader:
            # Filter out empty keys and None values from empty cells
            clean_row = {k: v for k, v in row.items() if k and k.strip()}
            records.append(clean_row)
    return records


def _read_json(file_path: Path) -> list[dict[str, Any]]:
    """Read records from JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both array and object with 'models' key
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        if "models" in data:
            return data["models"]
        elif "data" in data:
            return data["data"]
        else:
            # Single record
            return [data]
    else:
        raise ValueError("JSON must be an array or object with 'models' key")


def _validate_record(record: dict[str, Any], row_num: int) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate a single record. Returns (valid_data, errors)."""
    mapped, errors = _map_record(record)
    if errors:
        return None, errors
    return mapped, []


def _import_record(
    record: dict[str, Any],
    update_existing: bool,
) -> tuple[str, str | None, str | None]:
    """
    Import a single record.
    Returns: (status, model_name, error_message)
    Status: 'created', 'updated', 'skipped', 'error'
    """
    model_name = record.get("model_name", "unknown")

    try:
        # Check if model exists
        existing = None
        try:
            existing = get_model(model_name)
        except ModelNotFoundError:
            pass

        if existing:
            if update_existing:
                # Update existing model
                update_data = {k: v for k, v in record.items() if k != "model_name" and v is not None}
                update_model(model_name, update_data)
                return "updated", model_name, None
            else:
                return "skipped", model_name, "Already exists"
        else:
            # Create new model
            create_model(record)
            return "created", model_name, None

    except ValidationError as e:
        return "error", model_name, f"Validation error: {e.message}"
    except DatabaseError as e:
        return "error", model_name, f"Database error: {e.details}"
    except Exception as e:
        return "error", model_name, str(e)


def import_models(
    file: Path = typer.Argument(
        ...,
        help="Path to CSV or JSON file to import",
        exists=True,
        readable=True,
    ),
    validate_only: bool = typer.Option(
        False,
        "--validate",
        "-v",
        help="Validate records without importing",
    ),
    update_existing: bool = typer.Option(
        False,
        "--update",
        "-u",
        help="Update existing models instead of skipping",
    ),
    continue_on_error: bool = typer.Option(
        False,
        "--continue-on-error",
        "-c",
        help="Continue importing even if some records fail",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be imported without making changes",
    ),
) -> None:
    """
    Import AI models from a CSV or JSON file.

    Supports field name variations and auto-maps to database schema.
    Use --validate to check the file before importing.

    \b
    Required CSV/JSON fields:
      model_name (or: name, model)
      vendor (or: provider)
      risk_tier (or: risk, tier)
      use_case (or: usecase, description)
      business_owner (or: owner)
      technical_owner (or: tech_owner)
      deployment_date (or: deployed, deploy_date)

    \b
    Optional fields:
      model_version, deployment_environment, api_endpoint,
      data_classification, notes

    \b
    Examples:
      mltrack import models.csv
      mltrack import models.json --validate
      mltrack import models.csv --update --continue-on-error
      mltrack import models.json --dry-run
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

    # Read file
    console.print(f"\n[dim]Reading {file.name}...[/dim]")
    try:
        if suffix == ".csv":
            records = _read_csv(file)
        else:
            records = _read_json(file)
    except Exception as e:
        console.print(
            Panel(
                f"[red]Failed to read file:[/red] {e}",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    if not records:
        console.print(
            Panel(
                "[yellow]No records found in file[/yellow]",
                title="[yellow]Warning[/yellow]",
                border_style="yellow",
            )
        )
        raise typer.Exit(0)

    console.print(f"[dim]Found {len(records)} record(s)[/dim]\n")

    # Validate all records first
    validation_results: list[tuple[int, dict | None, list[str]]] = []
    valid_count = 0
    invalid_count = 0

    for i, record in enumerate(records, 1):
        valid_data, errors = _validate_record(record, i)
        validation_results.append((i, valid_data, errors))
        if errors:
            invalid_count += 1
        else:
            valid_count += 1

    # Show validation summary
    if validate_only or dry_run or invalid_count > 0:
        _show_validation_results(validation_results, validate_only or dry_run)

    if validate_only:
        # Just show validation results
        if invalid_count > 0:
            console.print(
                Panel(
                    f"[red]{invalid_count} record(s) have validation errors[/red]\n"
                    f"[green]{valid_count} record(s) are valid[/green]",
                    title="[yellow]Validation Complete[/yellow]",
                    border_style="yellow",
                )
            )
            raise typer.Exit(1)
        else:
            console.print(
                Panel(
                    f"[green]All {valid_count} record(s) are valid and ready to import[/green]",
                    title="[green]Validation Passed[/green]",
                    border_style="green",
                )
            )
        raise typer.Exit(0)

    if invalid_count > 0 and not continue_on_error:
        console.print(
            Panel(
                f"[red]{invalid_count} record(s) have validation errors[/red]\n\n"
                "[dim]Fix the errors above or use --continue-on-error to skip invalid records[/dim]",
                title="[red]Import Aborted[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    if dry_run:
        console.print(
            Panel(
                f"[cyan]Dry run complete[/cyan]\n\n"
                f"Would import: [green]{valid_count}[/green] valid record(s)\n"
                f"Would skip: [red]{invalid_count}[/red] invalid record(s)",
                title="[cyan]Dry Run[/cyan]",
                border_style="cyan",
            )
        )
        raise typer.Exit(0)

    # Import valid records
    results = {
        "created": [],
        "updated": [],
        "skipped": [],
        "error": [],
    }

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Importing models...", total=len(validation_results))

        for row_num, valid_data, errors in validation_results:
            if errors:
                # Skip invalid records
                results["error"].append((row_num, "unknown", "; ".join(errors)))
                progress.update(task, advance=1)
                continue

            status, model_name, error_msg = _import_record(valid_data, update_existing)
            results[status].append((row_num, model_name, error_msg))
            progress.update(task, advance=1)

    # Show results summary
    _show_import_results(results)

    # Exit with error code if there were errors
    if results["error"] and not continue_on_error:
        raise typer.Exit(1)


def _show_validation_results(
    results: list[tuple[int, dict | None, list[str]]],
    show_all: bool = False,
) -> None:
    """Display validation results."""
    has_errors = any(errors for _, _, errors in results)

    if not has_errors and not show_all:
        return

    table = Table(
        title="Validation Results",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
    )
    table.add_column("Row", style="dim", width=5)
    table.add_column("Model Name", style="cyan", max_width=25)
    table.add_column("Status", width=10)
    table.add_column("Details", max_width=50)

    for row_num, valid_data, errors in results:
        model_name = "unknown"
        if valid_data:
            model_name = valid_data.get("model_name", "unknown")
        elif isinstance(results[row_num - 1], tuple) and len(results[row_num - 1]) > 1:
            # Try to get name from raw data
            pass

        if errors:
            table.add_row(
                str(row_num),
                model_name[:25],
                "[red]Invalid[/red]",
                "[red]" + "; ".join(errors[:2]) + "[/red]",
            )
        elif show_all:
            table.add_row(
                str(row_num),
                model_name[:25] if model_name else "unknown",
                "[green]Valid[/green]",
                "[dim]Ready to import[/dim]",
            )

    console.print(table)
    console.print()


def _show_import_results(results: dict[str, list]) -> None:
    """Display import results summary."""
    created = results["created"]
    updated = results["updated"]
    skipped = results["skipped"]
    errors = results["error"]

    # Summary panel
    summary_lines = []
    if created:
        summary_lines.append(f"[green]Created:[/green] {len(created)} model(s)")
    if updated:
        summary_lines.append(f"[cyan]Updated:[/cyan] {len(updated)} model(s)")
    if skipped:
        summary_lines.append(f"[yellow]Skipped:[/yellow] {len(skipped)} model(s) (already exist)")
    if errors:
        summary_lines.append(f"[red]Failed:[/red] {len(errors)} model(s)")

    total_processed = len(created) + len(updated) + len(skipped) + len(errors)
    summary_lines.insert(0, f"[bold]Total processed:[/bold] {total_processed}")

    # Determine border color based on results
    if errors and not (created or updated):
        border_style = "red"
        title = "[red]Import Failed[/red]"
    elif errors:
        border_style = "yellow"
        title = "[yellow]Import Completed with Errors[/yellow]"
    else:
        border_style = "green"
        title = "[green]Import Successful[/green]"

    console.print()
    console.print(
        Panel(
            "\n".join(summary_lines),
            title=title,
            border_style=border_style,
        )
    )

    # Show details table if there were issues
    if skipped or errors:
        console.print()
        table = Table(
            title="Details",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold dim",
        )
        table.add_column("Row", style="dim", width=5)
        table.add_column("Model", style="cyan", max_width=25)
        table.add_column("Status", width=10)
        table.add_column("Reason")

        for row_num, model_name, _ in skipped[:10]:
            table.add_row(str(row_num), model_name[:25], "[yellow]Skipped[/yellow]", "Already exists")

        for row_num, model_name, error in errors[:10]:
            table.add_row(str(row_num), model_name[:25], "[red]Error[/red]", error[:50] if error else "")

        remaining = len(skipped) + len(errors) - 20
        if remaining > 0:
            table.add_row("...", f"[dim]+{remaining} more[/dim]", "", "")

        console.print(table)
