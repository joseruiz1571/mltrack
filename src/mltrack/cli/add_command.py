"""CLI command for adding new AI models to the inventory."""

from datetime import date
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import box

from mltrack.core.storage import create_model, REVIEW_FREQUENCY
from mltrack.core.exceptions import (
    ModelAlreadyExistsError,
    ValidationError,
    DatabaseError,
)
from mltrack.models import RiskTier, DeploymentEnvironment, DataClassification

console = Console()

# Valid enum values for help text
RISK_TIERS = [t.value for t in RiskTier]
ENVIRONMENTS = [e.value for e in DeploymentEnvironment]
DATA_CLASSIFICATIONS = [c.value for c in DataClassification]


def validate_date(value: str) -> date:
    """Validate and parse date string."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise typer.BadParameter(
            f"Invalid date format: '{value}'. Use YYYY-MM-DD (e.g., 2025-01-15)"
        )


def validate_risk_tier(value: str) -> str:
    """Validate risk tier value."""
    normalized = value.lower()
    if normalized not in RISK_TIERS:
        raise typer.BadParameter(
            f"Invalid risk tier: '{value}'. Must be one of: {', '.join(RISK_TIERS)}"
        )
    return normalized


def validate_environment(value: Optional[str]) -> Optional[str]:
    """Validate deployment environment value."""
    if value is None or value == "":
        return None
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


def validate_data_classification(value: Optional[str]) -> Optional[str]:
    """Validate data classification value."""
    if value is None or value == "":
        return None
    normalized = value.lower()
    if normalized not in DATA_CLASSIFICATIONS:
        raise typer.BadParameter(
            f"Invalid classification: '{value}'. Must be one of: {', '.join(DATA_CLASSIFICATIONS)}"
        )
    return normalized


def _format_risk_tier(tier: RiskTier) -> str:
    """Format risk tier with appropriate color."""
    colors = {
        RiskTier.CRITICAL: "bold red",
        RiskTier.HIGH: "red",
        RiskTier.MEDIUM: "yellow",
        RiskTier.LOW: "green",
    }
    color = colors.get(tier, "white")
    return f"[{color}]{tier.value.upper()}[/{color}]"


def _prompt_with_validation(
    prompt_text: str,
    example: str,
    validator=None,
    required: bool = True,
    default: str = "",
    choices: list[str] | None = None,
) -> str:
    """Prompt for input with validation and retry."""
    while True:
        # Build the prompt with example
        if choices:
            choice_str = "/".join(choices)
            full_prompt = f"{prompt_text} [cyan]({choice_str})[/cyan]"
        else:
            full_prompt = f"{prompt_text} [dim](e.g., {example})[/dim]"

        value = Prompt.ask(full_prompt, default=default if default else None)

        # Handle empty input
        if not value or not value.strip():
            if required:
                console.print("[red]This field is required.[/red]")
                continue
            return ""

        value = value.strip()

        # Validate if validator provided
        if validator:
            try:
                validator(value)
                return value
            except typer.BadParameter as e:
                console.print(f"[red]{e.message}[/red]")
                continue

        return value


def _interactive_prompt() -> dict:
    """Run interactive prompts for model creation."""
    console.print()
    console.print(
        Panel(
            "[bold]Add New AI Model[/bold]\n\n"
            "Enter model details below. Required fields are marked with [red]*[/red].\n"
            "Press [cyan]Enter[/cyan] to skip optional fields.",
            border_style="blue",
        )
    )
    console.print()

    data = {}

    # Required fields
    console.print("[bold cyan]─── Required Fields ───[/bold cyan]\n")

    data["name"] = _prompt_with_validation(
        "[red]*[/red] Model name",
        "fraud-detection-v2",
        required=True,
    )

    data["vendor"] = _prompt_with_validation(
        "[red]*[/red] Vendor",
        "anthropic, openai, aws, in-house",
        required=True,
    )

    # Risk tier with choices
    console.print()
    console.print("[dim]Risk tiers determine review frequency (SR 11-7):[/dim]")
    console.print("[dim]  • critical = 30 days  • high = 90 days[/dim]")
    console.print("[dim]  • medium = 180 days   • low = 365 days[/dim]")
    data["risk_tier"] = _prompt_with_validation(
        "[red]*[/red] Risk tier",
        "",
        validator=lambda v: validate_risk_tier(v),
        required=True,
        choices=RISK_TIERS,
    )

    data["use_case"] = _prompt_with_validation(
        "[red]*[/red] Use case",
        "Customer service chatbot for financial advice",
        required=True,
    )

    data["business_owner"] = _prompt_with_validation(
        "[red]*[/red] Business owner",
        "Jane Smith (Product Team)",
        required=True,
    )

    data["technical_owner"] = _prompt_with_validation(
        "[red]*[/red] Technical owner",
        "Bob Chen (ML Platform)",
        required=True,
    )

    # Date with today as default
    today_str = date.today().isoformat()
    data["deployment_date"] = _prompt_with_validation(
        "[red]*[/red] Deployment date",
        today_str,
        validator=lambda v: validate_date(v),
        required=True,
        default=today_str,
    )

    # Optional fields
    console.print()
    console.print("[bold cyan]─── Optional Fields ───[/bold cyan]")
    console.print("[dim]Press Enter to skip[/dim]\n")

    data["version"] = _prompt_with_validation(
        "    Model version",
        "1.0.0, 20250514",
        required=False,
    )

    data["environment"] = _prompt_with_validation(
        "    Environment",
        "",
        validator=lambda v: validate_environment(v),
        required=False,
        choices=ENVIRONMENTS,
    )

    data["api_endpoint"] = _prompt_with_validation(
        "    API endpoint",
        "https://api.example.com/v1",
        required=False,
    )

    data["data_classification"] = _prompt_with_validation(
        "    Data classification",
        "",
        validator=lambda v: validate_data_classification(v),
        required=False,
        choices=DATA_CLASSIFICATIONS,
    )

    data["notes"] = _prompt_with_validation(
        "    Notes",
        "Production model for customer support",
        required=False,
    )

    return data


def _show_confirmation(data: dict) -> bool:
    """Show summary and ask for confirmation."""
    console.print()

    # Build summary table
    table = Table(
        title="Model Summary",
        show_header=True,
        header_style="bold",
        box=box.ROUNDED,
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Name", f"[cyan]{data['name']}[/cyan]")
    table.add_row("Vendor", data["vendor"])

    risk_tier = RiskTier(data["risk_tier"].lower())
    table.add_row("Risk Tier", _format_risk_tier(risk_tier))
    table.add_row("Use Case", data["use_case"])
    table.add_row("Business Owner", data["business_owner"])
    table.add_row("Technical Owner", data["technical_owner"])
    table.add_row("Deployment Date", data["deployment_date"])

    # Calculate next review
    review_days = REVIEW_FREQUENCY[risk_tier]
    parsed_date = date.fromisoformat(data["deployment_date"])
    next_review = parsed_date + __import__("datetime").timedelta(days=review_days)
    table.add_row("Next Review", f"[yellow]{next_review}[/yellow] ({review_days} days)")

    # Optional fields
    if data.get("version"):
        table.add_row("Version", data["version"])
    if data.get("environment"):
        table.add_row("Environment", data["environment"].upper())
    if data.get("api_endpoint"):
        table.add_row("API Endpoint", f"[dim]{data['api_endpoint']}[/dim]")
    if data.get("data_classification"):
        table.add_row("Data Classification", data["data_classification"].upper())
    if data.get("notes"):
        table.add_row("Notes", data["notes"])

    console.print(table)
    console.print()

    return Confirm.ask("[bold]Save this model?[/bold]", default=True)


def _save_model(data: dict) -> None:
    """Validate, transform, and save the model."""
    # Validate inputs
    try:
        parsed_date = validate_date(data["deployment_date"])
        validated_risk_tier = validate_risk_tier(data["risk_tier"])
        validated_env = validate_environment(data.get("environment"))
        validated_classification = validate_data_classification(data.get("data_classification"))
    except typer.BadParameter as e:
        console.print(f"[red]Error:[/red] {e.message}")
        raise typer.Exit(1)

    # Build model data
    model_data = {
        "model_name": data["name"].strip(),
        "vendor": data["vendor"].strip(),
        "risk_tier": validated_risk_tier,
        "use_case": data["use_case"].strip(),
        "business_owner": data["business_owner"].strip(),
        "technical_owner": data["technical_owner"].strip(),
        "deployment_date": parsed_date,
    }

    # Add optional fields if provided
    if data.get("version"):
        model_data["model_version"] = data["version"].strip()
    if validated_env:
        model_data["deployment_environment"] = validated_env
    if data.get("api_endpoint"):
        model_data["api_endpoint"] = data["api_endpoint"].strip()
    if validated_classification:
        model_data["data_classification"] = validated_classification
    if data.get("notes"):
        model_data["notes"] = data["notes"].strip()

    # Create the model
    try:
        model = create_model(model_data)
    except ModelAlreadyExistsError:
        console.print(
            Panel(
                f"[red]A model named '[bold]{data['name']}[/bold]' already exists.[/red]\n\n"
                "[dim]Use a different name or update the existing model with:[/dim]\n"
                f"[cyan]mltrack model edit {data['name']}[/cyan]",
                title="[red]Duplicate Model[/red]",
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

    # Success output
    risk_tier_enum = RiskTier(validated_risk_tier)
    review_days = REVIEW_FREQUENCY[risk_tier_enum]

    # Create summary table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("ID", f"[dim]{model.id}[/dim]")
    table.add_row("Name", f"[cyan]{model.model_name}[/cyan]")
    table.add_row("Vendor", model.vendor)
    table.add_row("Risk Tier", _format_risk_tier(risk_tier_enum))
    table.add_row("Business Owner", model.business_owner)
    table.add_row("Technical Owner", model.technical_owner)
    table.add_row("Deployed", str(model.deployment_date))
    table.add_row("Next Review", f"[yellow]{model.next_review_date}[/yellow] ({review_days} days)")

    if model.model_version:
        table.add_row("Version", model.model_version)
    if model.deployment_environment:
        table.add_row("Environment", model.deployment_environment.value.upper())
    if model.api_endpoint:
        table.add_row("API Endpoint", f"[dim]{model.api_endpoint}[/dim]")

    console.print()
    console.print(
        Panel(
            table,
            title="[green]✓ Model Added Successfully[/green]",
            border_style="green",
            subtitle=f"[dim]Use 'mltrack show {model.model_name}' for full details[/dim]",
        )
    )


def add_model(
    interactive: bool = typer.Option(
        False,
        "--interactive", "-i",
        help="Launch guided prompts to enter model details step-by-step",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name", "-n",
        help="Unique identifier for the model (e.g., 'fraud-detection-v2', 'claude-sonnet-4')",
    ),
    vendor: Optional[str] = typer.Option(
        None,
        "--vendor",
        help="Model provider or source (e.g., 'Anthropic', 'OpenAI', 'AWS', 'In-house')",
    ),
    risk_tier: Optional[str] = typer.Option(
        None,
        "--risk-tier", "-r",
        help=f"Risk classification that determines review frequency: {', '.join(RISK_TIERS)}",
    ),
    use_case: Optional[str] = typer.Option(
        None,
        "--use-case", "-u",
        help="Business purpose description (e.g., 'Customer service chatbot for financial advice')",
    ),
    business_owner: Optional[str] = typer.Option(
        None,
        "--business-owner", "-b",
        help="Accountable stakeholder with name and team (e.g., 'Jane Smith (Product)')",
    ),
    technical_owner: Optional[str] = typer.Option(
        None,
        "--technical-owner", "-t",
        help="Technical team or person maintaining the model (e.g., 'ML Platform Team')",
    ),
    deployment_date: Optional[str] = typer.Option(
        None,
        "--deployment-date", "-d",
        help="Date model was deployed in ISO format (YYYY-MM-DD, e.g., '2025-01-15')",
    ),
    version: Optional[str] = typer.Option(
        None,
        "--version",
        help="Model version identifier (e.g., '1.0.0', '20250514', 'gpt-4-0125-preview')",
    ),
    environment: Optional[str] = typer.Option(
        None,
        "--environment", "-e",
        help=f"Deployment target: {', '.join(ENVIRONMENTS)} (aliases: production, development also work)",
    ),
    api_endpoint: Optional[str] = typer.Option(
        None,
        "--api-endpoint",
        help="API endpoint URL where the model is accessible",
    ),
    data_classification: Optional[str] = typer.Option(
        None,
        "--data-classification",
        help=f"Data sensitivity level: {', '.join(DATA_CLASSIFICATIONS)} (required for prod if auditing)",
    ),
    notes: Optional[str] = typer.Option(
        None,
        "--notes",
        help="Additional context, deployment notes, or compliance remarks",
    ),
) -> None:
    """
    Register a new AI model in the governance inventory.

    Two modes are available:

    [bold]Interactive Mode (Recommended for first-time users):[/bold]
      mltrack add --interactive
      Walks you through each field with prompts and validation.

    [bold]Flag Mode (For scripting/automation):[/bold]
      Provide all required fields via command-line flags.

    \b
    [bold cyan]Required Fields:[/bold cyan]
      --name              Unique model identifier
      --vendor            Model provider
      --risk-tier         Risk classification (critical/high/medium/low)
      --use-case          Business purpose description
      --business-owner    Accountable stakeholder
      --technical-owner   Technical team/person
      --deployment-date   Deployment date (YYYY-MM-DD)

    \b
    [bold cyan]Review Cycles (SR 11-7 Aligned):[/bold cyan]
      CRITICAL → 30 days     HIGH → 90 days
      MEDIUM   → 180 days    LOW  → 365 days

    \b
    [bold]Examples:[/bold]
      [dim]# Interactive mode with guided prompts[/dim]
      mltrack add --interactive

      [dim]# Full command for scripting[/dim]
      mltrack add -n "claude-sonnet-4" --vendor Anthropic -r high \\
        -u "Customer service chatbot" -b "Jane Smith (Product)" \\
        -t "ML Platform Team" -d 2025-01-15 -e prod

      [dim]# Minimal required fields[/dim]
      mltrack add -n "gpt-4-turbo" --vendor OpenAI -r critical \\
        -u "Trading signals" -b "Trading Desk" -t "Quant Team" -d 2024-06-01
    """
    if interactive:
        # Interactive mode
        data = _interactive_prompt()

        # Show confirmation
        if not _show_confirmation(data):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

        _save_model(data)
    else:
        # Flag-based mode - check required fields
        required_fields = {
            "name": name,
            "vendor": vendor,
            "risk_tier": risk_tier,
            "use_case": use_case,
            "business_owner": business_owner,
            "technical_owner": technical_owner,
            "deployment_date": deployment_date,
        }

        missing = [k.replace("_", "-") for k, v in required_fields.items() if v is None]

        if missing:
            console.print(
                Panel(
                    f"[red]Missing required fields:[/red] {', '.join(f'--{f}' for f in missing)}\n\n"
                    "[dim]Provide all required flags, or use interactive mode:[/dim]\n"
                    "[cyan]mltrack add --interactive[/cyan]",
                    title="[red]Missing Fields[/red]",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

        # Build data dict and save
        data = {
            "name": name,
            "vendor": vendor,
            "risk_tier": risk_tier,
            "use_case": use_case,
            "business_owner": business_owner,
            "technical_owner": technical_owner,
            "deployment_date": deployment_date,
            "version": version,
            "environment": environment,
            "api_endpoint": api_endpoint,
            "data_classification": data_classification,
            "notes": notes,
        }

        _save_model(data)
