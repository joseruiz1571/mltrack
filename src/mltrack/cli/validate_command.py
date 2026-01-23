"""CLI command for validating AI models against governance requirements."""

from datetime import date
from typing import Optional
from dataclasses import dataclass, field

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from mltrack.core.storage import get_model, get_all_models, REVIEW_FREQUENCY
from mltrack.core.exceptions import ModelNotFoundError, DatabaseError
from mltrack.models import RiskTier, ModelStatus, DeploymentEnvironment, AIModel

console = Console()

# Valid enum values for help text
RISK_TIERS = [t.value for t in RiskTier]

# Color mappings
RISK_COLORS = {
    RiskTier.CRITICAL: "bold red",
    RiskTier.HIGH: "red",
    RiskTier.MEDIUM: "yellow",
    RiskTier.LOW: "green",
}


@dataclass
class ValidationResult:
    """Result of validating a single model."""
    model: AIModel
    passed: bool = True
    violations: list[str] = field(default_factory=list)

    def add_violation(self, message: str) -> None:
        """Add a violation and mark as failed."""
        self.violations.append(message)
        self.passed = False


@dataclass
class ValidationSummary:
    """Summary of all validation results."""
    total_models: int = 0
    passed_models: int = 0
    failed_models: int = 0
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def compliance_rate(self) -> float:
        """Calculate compliance rate as percentage."""
        if self.total_models == 0:
            return 100.0
        return (self.passed_models / self.total_models) * 100

    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result to the summary."""
        self.results.append(result)
        self.total_models += 1
        if result.passed:
            self.passed_models += 1
        else:
            self.failed_models += 1


def _validate_required_fields(model: AIModel, result: ValidationResult) -> None:
    """Check that required fields are populated."""
    required_fields = [
        ("model_name", "Model name"),
        ("vendor", "Vendor"),
        ("risk_tier", "Risk tier"),
        ("use_case", "Use case"),
        ("business_owner", "Business owner"),
        ("technical_owner", "Technical owner"),
        ("deployment_date", "Deployment date"),
    ]

    for field_name, display_name in required_fields:
        value = getattr(model, field_name, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            result.add_violation(f"Missing required field: {display_name}")


def _validate_review_schedule(model: AIModel, result: ValidationResult) -> None:
    """Check that model has been reviewed within acceptable timeframe."""
    # Skip if model is not active
    if model.status != ModelStatus.ACTIVE:
        return

    # Check if next_review_date is set
    if model.next_review_date is None:
        result.add_violation("No review schedule defined (next_review_date is null)")
        return

    # Check if review is overdue
    days_overdue = (date.today() - model.next_review_date).days
    if days_overdue > 0:
        review_cycle = REVIEW_FREQUENCY[model.risk_tier]
        result.add_violation(
            f"Review overdue by {days_overdue} days "
            f"({model.risk_tier.value.upper()} risk requires review every {review_cycle} days)"
        )


def _validate_business_owner(model: AIModel, result: ValidationResult) -> None:
    """Check that business owner is defined."""
    if not model.business_owner or not model.business_owner.strip():
        result.add_violation("Business owner not defined")


def _validate_technical_owner(model: AIModel, result: ValidationResult) -> None:
    """Check that technical owner is defined."""
    if not model.technical_owner or not model.technical_owner.strip():
        result.add_violation("Technical owner not defined")


def _validate_deployment_date(model: AIModel, result: ValidationResult) -> None:
    """Check that active models have a deployment date."""
    if model.status == ModelStatus.ACTIVE and model.deployment_date is None:
        result.add_violation("Active model missing deployment date")


def _validate_production_data_classification(model: AIModel, result: ValidationResult) -> None:
    """Check that production models have data classification set."""
    if model.deployment_environment == DeploymentEnvironment.PROD:
        if model.data_classification is None:
            result.add_violation(
                "Production model missing data classification "
                "(required for data governance compliance)"
            )


def validate_model(model: AIModel) -> ValidationResult:
    """Run all validation rules against a model."""
    result = ValidationResult(model=model)

    # Run all validators
    _validate_required_fields(model, result)
    _validate_review_schedule(model, result)
    _validate_business_owner(model, result)
    _validate_technical_owner(model, result)
    _validate_deployment_date(model, result)
    _validate_production_data_classification(model, result)

    return result


def _format_risk_tier(tier: RiskTier) -> str:
    """Format risk tier with color."""
    color = RISK_COLORS.get(tier, "white")
    return f"[{color}]{tier.value.upper()}[/{color}]"


def _display_model_result(result: ValidationResult) -> None:
    """Display validation result for a single model."""
    model = result.model

    if result.passed:
        status_icon = "[green]✓ PASS[/green]"
    else:
        status_icon = "[red]✗ FAIL[/red]"

    # Build header
    header = f"{status_icon}  [cyan]{model.model_name}[/cyan]"
    header += f"  {_format_risk_tier(model.risk_tier)}"

    console.print(header)

    if result.violations:
        for violation in result.violations:
            console.print(f"    [red]•[/red] {violation}")


def _display_summary(summary: ValidationSummary) -> None:
    """Display validation summary."""
    # Determine overall status color
    if summary.compliance_rate == 100:
        rate_color = "green"
        status = "ALL COMPLIANT"
    elif summary.compliance_rate >= 80:
        rate_color = "yellow"
        status = "NEEDS ATTENTION"
    else:
        rate_color = "red"
        status = "NON-COMPLIANT"

    # Summary table
    summary_table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value", justify="right")

    summary_table.add_row("Total Models", str(summary.total_models))
    summary_table.add_row("Passed", f"[green]{summary.passed_models}[/green]")
    summary_table.add_row("Failed", f"[red]{summary.failed_models}[/red]" if summary.failed_models > 0 else "0")
    summary_table.add_row(
        "Compliance Rate",
        f"[{rate_color}]{summary.compliance_rate:.1f}%[/{rate_color}]"
    )

    console.print()
    console.print(
        Panel(
            summary_table,
            title=f"[{rate_color}]{status}[/{rate_color}]",
            border_style=rate_color,
        )
    )


def _display_violation_summary(summary: ValidationSummary) -> None:
    """Display summary of violations by type."""
    violation_counts: dict[str, int] = {}

    for result in summary.results:
        for violation in result.violations:
            # Extract violation type (before the colon or parenthesis)
            if ":" in violation:
                violation_type = violation.split(":")[0]
            elif "(" in violation:
                violation_type = violation.split("(")[0].strip()
            else:
                violation_type = violation

            violation_counts[violation_type] = violation_counts.get(violation_type, 0) + 1

    if violation_counts:
        console.print()
        console.print("[bold]Violation Summary:[/bold]")

        # Sort by count descending
        sorted_violations = sorted(violation_counts.items(), key=lambda x: x[1], reverse=True)

        for violation_type, count in sorted_violations:
            console.print(f"  [red]•[/red] {violation_type}: [bold]{count}[/bold] model{'s' if count > 1 else ''}")


def validate_command(
    all_models: bool = typer.Option(
        False,
        "--all", "-a",
        help="Check all models in the inventory for compliance issues",
    ),
    model_id: Optional[str] = typer.Option(
        None,
        "--model-id", "-m",
        help="Check a specific model by name or UUID",
    ),
    risk: Optional[str] = typer.Option(
        None,
        "--risk", "-r",
        help=f"Check only models with this risk tier: {', '.join(RISK_TIERS)}",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show all models including those passing validation",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON (for CI/CD pipelines, scripting)",
    ),
) -> None:
    """
    Check AI models against governance and compliance requirements.

    Validates each model against these rules:
    • [bold]Required fields[/bold] - All mandatory fields are populated
    • [bold]Review schedule[/bold] - Model is not overdue for review (based on risk tier)
    • [bold]Ownership[/bold] - Business and technical owners are defined
    • [bold]Deployment date[/bold] - Active models have deployment dates
    • [bold]Data classification[/bold] - Production models have classification set

    Returns exit code 1 if any model fails validation (useful for CI/CD).

    \b
    [bold cyan]Selection Options (choose one):[/bold cyan]
      --all        Check all models in inventory
      --model-id   Check a specific model
      --risk       Check models of a specific risk tier

    \b
    [bold cyan]Review Cycles (SR 11-7 Aligned):[/bold cyan]
      CRITICAL → 30 days     HIGH → 90 days
      MEDIUM   → 180 days    LOW  → 365 days

    \b
    [bold]Examples:[/bold]
      [dim]# Validate all models[/dim]
      mltrack validate --all

      [dim]# Check a specific model[/dim]
      mltrack validate -m "claude-sonnet-4"
      mltrack validate --model-id "fraud-detector"

      [dim]# Check only critical risk models[/dim]
      mltrack validate --risk critical

      [dim]# Show all results including passing models[/dim]
      mltrack validate --all --verbose
      mltrack validate --all -v

      [dim]# JSON output for CI/CD pipelines[/dim]
      mltrack validate --all --json
      mltrack validate --all --json | jq '.summary.compliance_rate'

      [dim]# Use in CI/CD (fails pipeline if non-compliant)[/dim]
      mltrack validate --all --json || echo "Compliance check failed"

    \b
    [bold cyan]Related Commands:[/bold cyan]
      mltrack reviewed <name>     Record a review to clear overdue violations
      mltrack update <name>       Fix missing fields or update classification
      mltrack report compliance   Generate detailed compliance report
    """
    # Determine which models to validate
    models_to_validate: list[AIModel] = []

    try:
        if model_id:
            # Validate specific model
            try:
                model = get_model(model_id)
                models_to_validate = [model]
            except ModelNotFoundError:
                console.print(
                    Panel(
                        f"[red]Model not found:[/red] '{model_id}'\n\n"
                        "[dim]Use [cyan]mltrack list[/cyan] to see all models.[/dim]",
                        title="Not Found",
                        border_style="red",
                    )
                )
                raise typer.Exit(1)

        elif risk:
            # Validate by risk tier
            risk_lower = risk.lower()
            if risk_lower not in RISK_TIERS:
                console.print(
                    f"[red]Invalid risk tier:[/red] '{risk}'. "
                    f"Must be one of: {', '.join(RISK_TIERS)}"
                )
                raise typer.Exit(1)

            risk_tier = RiskTier(risk_lower)
            models_to_validate = get_all_models(risk_tier=risk_tier)

            if not models_to_validate:
                console.print(
                    Panel(
                        f"[yellow]No models found with risk tier:[/yellow] {risk.upper()}",
                        title="No Models",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(0)

        elif all_models:
            # Validate all models
            models_to_validate = get_all_models()

            if not models_to_validate:
                console.print(
                    Panel(
                        "[yellow]No models in inventory.[/yellow]\n\n"
                        "[dim]Add models with:[/dim] [cyan]mltrack add --interactive[/cyan]",
                        title="Empty Inventory",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(0)

        else:
            # No filter specified - show help
            console.print(
                Panel(
                    "[yellow]Please specify which models to validate:[/yellow]\n\n"
                    "[cyan]--all[/cyan]              Validate all models\n"
                    "[cyan]--model-id NAME[/cyan]   Validate specific model\n"
                    "[cyan]--risk TIER[/cyan]       Validate by risk tier\n\n"
                    "[dim]Example: mltrack validate --all[/dim]",
                    title="Usage",
                    border_style="yellow",
                )
            )
            raise typer.Exit(0)

    except DatabaseError as e:
        console.print(f"[red]Database error:[/red] {e.details}")
        raise typer.Exit(1)

    # Run validation
    summary = ValidationSummary()

    for model in models_to_validate:
        result = validate_model(model)
        summary.add_result(result)

    # Handle JSON output
    if json_output:
        import json

        output_data = {
            "summary": {
                "total_models": summary.total_models,
                "passed_models": summary.passed_models,
                "failed_models": summary.failed_models,
                "compliance_rate": round(summary.compliance_rate, 1),
            },
            "results": [
                {
                    "model_id": r.model.id,
                    "model_name": r.model.model_name,
                    "risk_tier": r.model.risk_tier.value,
                    "passed": r.passed,
                    "violations": r.violations,
                }
                for r in summary.results
            ],
        }
        print(json.dumps(output_data, indent=2))
        raise typer.Exit(0 if summary.failed_models == 0 else 1)

    # Display results
    console.print()
    console.print(
        Panel(
            f"[bold]Validating {summary.total_models} model{'s' if summary.total_models != 1 else ''}[/bold]",
            border_style="blue",
        )
    )
    console.print()

    # Show individual results
    failed_results = [r for r in summary.results if not r.passed]
    passed_results = [r for r in summary.results if r.passed]

    # Always show failed models
    if failed_results:
        console.print("[bold red]Failed Validation:[/bold red]")
        console.print()
        for result in failed_results:
            _display_model_result(result)
            console.print()

    # Show passed models if verbose
    if verbose and passed_results:
        console.print("[bold green]Passed Validation:[/bold green]")
        console.print()
        for result in passed_results:
            _display_model_result(result)
        console.print()

    # Show violation summary
    if failed_results:
        _display_violation_summary(summary)

    # Show overall summary
    _display_summary(summary)

    # Exit with error code if any failures
    if summary.failed_models > 0:
        raise typer.Exit(1)
