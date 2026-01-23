"""Helper functions for consistent, user-friendly error messages."""

from difflib import SequenceMatcher, get_close_matches
from typing import Any

from rich.console import Console
from rich.panel import Panel

from mltrack.models import RiskTier, DeploymentEnvironment, DataClassification, ModelStatus

console = Console()

# Valid enum values
RISK_TIERS = [t.value for t in RiskTier]
ENVIRONMENTS = [e.value for e in DeploymentEnvironment]
DATA_CLASSIFICATIONS = [c.value for c in DataClassification]
STATUSES = [s.value for s in ModelStatus]

# Environment aliases for suggestions
ENVIRONMENT_ALIASES = {
    "production": "prod",
    "prd": "prod",
    "development": "dev",
    "stg": "staging",
}


def find_similar_strings(
    value: str,
    valid_options: list[str],
    cutoff: float = 0.6,
    max_suggestions: int = 2,
) -> list[str]:
    """Find strings similar to the given value.

    Args:
        value: The invalid value entered by the user
        valid_options: List of valid options to compare against
        cutoff: Similarity threshold (0-1)
        max_suggestions: Maximum number of suggestions to return

    Returns:
        List of similar valid options
    """
    return get_close_matches(value.lower(), valid_options, n=max_suggestions, cutoff=cutoff)


def format_suggestion(suggestions: list[str]) -> str:
    """Format suggestions as a readable string.

    Args:
        suggestions: List of suggested values

    Returns:
        Formatted suggestion string
    """
    if not suggestions:
        return ""

    if len(suggestions) == 1:
        return f"Did you mean '[cyan]{suggestions[0]}[/cyan]'?"

    quoted = [f"'[cyan]{s}[/cyan]'" for s in suggestions]
    return f"Did you mean {' or '.join(quoted)}?"


def error_invalid_enum(
    field_name: str,
    invalid_value: str,
    valid_options: list[str],
    field_display_name: str | None = None,
) -> None:
    """Display error for invalid enum value with suggestions.

    Args:
        field_name: Internal field name (e.g., 'risk_tier')
        invalid_value: The invalid value entered
        valid_options: List of valid options
        field_display_name: Human-readable field name (defaults to field_name)
    """
    display_name = field_display_name or field_name.replace("_", " ").title()

    # Find similar valid options
    suggestions = find_similar_strings(invalid_value, valid_options)

    # Build error message
    error_lines = [
        f"[red]Invalid {display_name.lower()}:[/red] '{invalid_value}'",
        "",
        f"[dim]Valid options: {', '.join(valid_options)}[/dim]",
    ]

    if suggestions:
        error_lines.insert(1, f"[yellow]{format_suggestion(suggestions)}[/yellow]")

    console.print(
        Panel(
            "\n".join(error_lines),
            title=f"[red]Invalid {display_name}[/red]",
            border_style="red",
        )
    )


def error_invalid_risk_tier(invalid_value: str) -> None:
    """Display error for invalid risk tier with suggestions."""
    error_invalid_enum("risk_tier", invalid_value, RISK_TIERS, "Risk Tier")


def error_invalid_environment(invalid_value: str) -> None:
    """Display error for invalid environment with suggestions."""
    # Check if it's a known alias
    normalized = invalid_value.lower()
    if normalized in ENVIRONMENT_ALIASES:
        alias_target = ENVIRONMENT_ALIASES[normalized]
        console.print(
            Panel(
                f"[yellow]Note:[/yellow] '{invalid_value}' is an alias for '{alias_target}'.\n\n"
                f"[dim]Use '{alias_target}' directly, or the alias should work automatically.[/dim]",
                title="[yellow]Environment Alias[/yellow]",
                border_style="yellow",
            )
        )
        return

    error_invalid_enum("environment", invalid_value, ENVIRONMENTS, "Environment")


def error_invalid_status(invalid_value: str) -> None:
    """Display error for invalid status with suggestions."""
    error_invalid_enum("status", invalid_value, STATUSES, "Status")


def error_invalid_data_classification(invalid_value: str) -> None:
    """Display error for invalid data classification with suggestions."""
    error_invalid_enum(
        "data_classification",
        invalid_value,
        DATA_CLASSIFICATIONS,
        "Data Classification",
    )


def error_invalid_date(invalid_value: str, field_name: str = "date") -> None:
    """Display error for invalid date format.

    Args:
        invalid_value: The invalid date string
        field_name: Name of the date field
    """
    console.print(
        Panel(
            f"[red]Invalid date format:[/red] '{invalid_value}'\n\n"
            "[dim]Expected format: YYYY-MM-DD (e.g., 2025-01-15)[/dim]\n"
            "[dim]You can also use 'today' for the current date.[/dim]",
            title=f"[red]Invalid {field_name.replace('_', ' ').title()}[/red]",
            border_style="red",
        )
    )


def error_model_not_found(
    identifier: str,
    available_models: list[str] | None = None,
    suggestion_prefix: str = "mltrack list",
) -> None:
    """Display error for model not found with suggestions.

    Args:
        identifier: The model identifier that wasn't found
        available_models: Optional list of available model names for fuzzy matching
        suggestion_prefix: Command to suggest for listing models
    """
    error_lines = [f"[red]Model not found:[/red] '{identifier}'"]

    # Try to find similar model names
    if available_models:
        suggestions = find_similar_strings(identifier, available_models)
        if suggestions:
            error_lines.append("")
            error_lines.append(f"[yellow]{format_suggestion(suggestions)}[/yellow]")

    error_lines.append("")
    error_lines.append(f"[dim]Use [cyan]{suggestion_prefix}[/cyan] to see all models in the inventory.[/dim]")

    console.print(
        Panel(
            "\n".join(error_lines),
            title="[red]Model Not Found[/red]",
            border_style="red",
        )
    )


def error_model_already_exists(model_name: str) -> None:
    """Display error for duplicate model name.

    Args:
        model_name: The duplicate model name
    """
    console.print(
        Panel(
            f"[red]A model named '[bold]{model_name}[/bold]' already exists.[/red]\n\n"
            "[dim]Choose a different name, or update the existing model with:[/dim]\n"
            f"[cyan]mltrack update \"{model_name}\"[/cyan]",
            title="[red]Duplicate Model[/red]",
            border_style="red",
        )
    )


def error_missing_fields(missing_fields: list[str], suggestion: str | None = None) -> None:
    """Display error for missing required fields.

    Args:
        missing_fields: List of missing field names
        suggestion: Optional suggestion message
    """
    formatted_fields = ", ".join(f"[cyan]--{f}[/cyan]" for f in missing_fields)

    error_lines = [f"[red]Missing required fields:[/red] {formatted_fields}"]

    if suggestion:
        error_lines.append("")
        error_lines.append(f"[dim]{suggestion}[/dim]")
    else:
        error_lines.append("")
        error_lines.append("[dim]Provide all required flags, or use interactive mode:[/dim]")
        error_lines.append("[cyan]mltrack add --interactive[/cyan]")

    console.print(
        Panel(
            "\n".join(error_lines),
            title="[red]Missing Fields[/red]",
            border_style="red",
        )
    )


def error_validation(field: str, message: str) -> None:
    """Display validation error with context.

    Args:
        field: The field that failed validation
        message: The validation error message
    """
    field_display = field.replace("_", " ").title()

    console.print(
        Panel(
            f"[red]Validation error for '{field_display}':[/red]\n{message}",
            title="[red]Validation Error[/red]",
            border_style="red",
        )
    )


def error_database(operation: str, details: str) -> None:
    """Display database error with context.

    Args:
        operation: The operation that failed (e.g., 'create', 'update')
        details: Error details
    """
    console.print(
        Panel(
            f"[red]Database operation failed:[/red] {operation}\n\n"
            f"[dim]Details: {details}[/dim]\n\n"
            "[dim]If this persists, check that the database file is accessible and not corrupted.[/dim]",
            title="[red]Database Error[/red]",
            border_style="red",
        )
    )


def error_file_not_found(file_path: str, expected_format: str | None = None) -> None:
    """Display error for file not found.

    Args:
        file_path: Path to the file that wasn't found
        expected_format: Optional expected file format hint
    """
    error_lines = [f"[red]File not found:[/red] '{file_path}'"]

    if expected_format:
        error_lines.append("")
        error_lines.append(f"[dim]Expected format: {expected_format}[/dim]")

    error_lines.append("")
    error_lines.append("[dim]Check that the file exists and the path is correct.[/dim]")

    console.print(
        Panel(
            "\n".join(error_lines),
            title="[red]File Not Found[/red]",
            border_style="red",
        )
    )


def error_file_format(file_path: str, expected_formats: list[str], actual_format: str | None = None) -> None:
    """Display error for unsupported file format.

    Args:
        file_path: Path to the file
        expected_formats: List of supported formats
        actual_format: The actual format found (if known)
    """
    format_str = ", ".join(expected_formats)

    error_lines = []
    if actual_format:
        error_lines.append(f"[red]Unsupported file type:[/red] '{actual_format}'")
    else:
        error_lines.append(f"[red]Unable to determine file type for:[/red] '{file_path}'")

    error_lines.append("")
    error_lines.append(f"[dim]Supported formats: {format_str}[/dim]")

    console.print(
        Panel(
            "\n".join(error_lines),
            title="[red]Unsupported File Type[/red]",
            border_style="red",
        )
    )


def error_file_read(file_path: str, error_message: str) -> None:
    """Display error when reading a file fails.

    Args:
        file_path: Path to the file
        error_message: The error message
    """
    console.print(
        Panel(
            f"[red]Failed to read file:[/red] '{file_path}'\n\n"
            f"[dim]Error: {error_message}[/dim]\n\n"
            "[dim]Check that the file exists, is readable, and is not corrupted.[/dim]",
            title="[red]File Read Error[/red]",
            border_style="red",
        )
    )


def error_file_write(file_path: str, error_message: str) -> None:
    """Display error when writing a file fails.

    Args:
        file_path: Path to the file
        error_message: The error message
    """
    console.print(
        Panel(
            f"[red]Failed to write file:[/red] '{file_path}'\n\n"
            f"[dim]Error: {error_message}[/dim]\n\n"
            "[dim]Check that the directory exists and you have write permissions.[/dim]",
            title="[red]File Write Error[/red]",
            border_style="red",
        )
    )


def warning_no_models(filter_description: str | None = None) -> None:
    """Display warning when no models match criteria.

    Args:
        filter_description: Description of the filters applied
    """
    if filter_description:
        message = f"[yellow]No models found matching:[/yellow] {filter_description}"
    else:
        message = "[yellow]No models in inventory.[/yellow]"

    console.print(
        Panel(
            f"{message}\n\n"
            "[dim]Add models with:[/dim] [cyan]mltrack add --interactive[/cyan]",
            title="[yellow]No Models[/yellow]",
            border_style="yellow",
        )
    )


def warning_no_changes() -> None:
    """Display warning when no changes were specified for update."""
    console.print(
        Panel(
            "[yellow]No changes specified.[/yellow]\n\n"
            "[dim]Provide at least one field to update. See available options with:[/dim]\n"
            "[cyan]mltrack update --help[/cyan]",
            title="[yellow]No Changes[/yellow]",
            border_style="yellow",
        )
    )


def warning_already_decommissioned(model_name: str) -> None:
    """Display warning when trying to decommission an already decommissioned model.

    Args:
        model_name: Name of the model
    """
    console.print(
        Panel(
            f"[yellow]Model '[bold]{model_name}[/bold]' is already decommissioned.[/yellow]",
            title="[yellow]Already Decommissioned[/yellow]",
            border_style="yellow",
        )
    )


def info_usage(title: str, options: list[tuple[str, str]], example: str | None = None) -> None:
    """Display usage information panel.

    Args:
        title: Panel title
        options: List of (option, description) tuples
        example: Optional example command
    """
    lines = ["[yellow]Please specify an option:[/yellow]", ""]

    for option, description in options:
        lines.append(f"[cyan]{option}[/cyan]  {description}")

    if example:
        lines.append("")
        lines.append(f"[dim]Example: {example}[/dim]")

    console.print(
        Panel(
            "\n".join(lines),
            title=f"[blue]{title}[/blue]",
            border_style="blue",
        )
    )
