"""CI/CD compliance gate for AI model governance.

Designed for pipeline integration: silent by default, exit code 0 (pass) or 1 (fail).
Use --json for structured output or --verbose for human-readable details.
"""

import json
from typing import Optional

import typer
from rich.console import Console

from mltrack.core.storage import get_model, get_all_models
from mltrack.core.exceptions import ModelNotFoundError, DatabaseError
from mltrack.models import RiskTier
from mltrack.cli.validate_command import validate_model, ValidationSummary
from mltrack.cli.error_helpers import error_model_not_found, error_database

console = Console(stderr=True)

# Valid risk tiers for help text
RISK_TIERS = [t.value for t in RiskTier]


def _build_summary(models):
    """Run validation on a list of models and return a ValidationSummary."""
    summary = ValidationSummary()
    for model in models:
        result = validate_model(model)
        summary.add_result(result)
    return summary


def _format_json_output(summary: ValidationSummary) -> str:
    """Format validation summary as JSON for pipeline consumption."""
    output = {
        "passed": summary.failed_models == 0,
        "summary": {
            "total": summary.total_models,
            "passed": summary.passed_models,
            "failed": summary.failed_models,
            "compliance_rate": round(summary.compliance_rate, 1),
        },
        "failures": [
            {
                "model": r.model.model_name,
                "risk_tier": r.model.risk_tier.value,
                "violations": r.violations,
            }
            for r in summary.results
            if not r.passed
        ],
    }
    return json.dumps(output, indent=2)


def check_command(
    model_name: Optional[str] = typer.Argument(
        None,
        help="Model name to check (omit for --all)",
    ),
    all_models: bool = typer.Option(
        False,
        "--all", "-a",
        help="Check all models in the inventory",
    ),
    risk: Optional[str] = typer.Option(
        None,
        "--risk", "-r",
        help=f"Check only models with this risk tier: {', '.join(RISK_TIERS)}",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON to stdout",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show human-readable validation details on stderr",
    ),
) -> None:
    """
    CI/CD compliance gate — exit code 0 if compliant, 1 if not.

    Silent by default for pipeline integration. Add --json for structured
    output or --verbose for human-readable details.

    \b
    [bold cyan]Pipeline Usage:[/bold cyan]
      mltrack check "fraud-detector" && echo "OK" || echo "BLOCKED"
      mltrack check --all --json | jq '.passed'
      mltrack check --risk critical

    \b
    [bold cyan]GitHub Actions Example:[/bold cyan]
      - name: Compliance gate
        run: mltrack check --all

    \b
    [bold cyan]Exit Codes:[/bold cyan]
      0  All checked models are compliant
      1  One or more models failed compliance checks

    \b
    [bold cyan]Related Commands:[/bold cyan]
      mltrack validate --all    Interactive validation with Rich output
      mltrack report compliance  Detailed compliance report
    """
    try:
        if model_name:
            try:
                model = get_model(model_name)
            except ModelNotFoundError:
                if verbose:
                    try:
                        available = [m.model_name for m in get_all_models()]
                    except DatabaseError:
                        available = None
                    error_model_not_found(model_name, available)
                raise typer.Exit(1)
            models = [model]

        elif all_models:
            models = get_all_models()
            if not models:
                if verbose:
                    console.print("[yellow]No models in inventory.[/yellow]")
                raise typer.Exit(0)

        elif risk:
            risk_lower = risk.lower()
            if risk_lower not in RISK_TIERS:
                if verbose:
                    console.print(f"[red]Invalid risk tier:[/red] '{risk}'")
                    console.print(f"[dim]Valid: {', '.join(RISK_TIERS)}[/dim]")
                raise typer.Exit(1)

            risk_tier = RiskTier(risk_lower)
            models = get_all_models(risk_tier=risk_tier)
            if not models:
                if verbose:
                    console.print(f"[yellow]No models with risk tier '{risk.upper()}'.[/yellow]")
                raise typer.Exit(0)

        else:
            console.print("[yellow]Specify a model name or --all[/yellow]")
            console.print("[dim]Usage: mltrack check <model-name>[/dim]")
            console.print("[dim]       mltrack check --all[/dim]")
            raise typer.Exit(1)

    except DatabaseError as e:
        if verbose:
            error_database(e.operation, e.details)
        raise typer.Exit(1)

    summary = _build_summary(models)

    # Verbose: human-readable output to stderr
    if verbose:
        for r in summary.results:
            status = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
            console.print(f"  {status}  {r.model.model_name} ({r.model.risk_tier.value})")
            for v in r.violations:
                console.print(f"         [red]•[/red] {v}")

        rate_color = "green" if summary.compliance_rate == 100 else "red"
        console.print(
            f"\n[{rate_color}]{summary.passed_models}/{summary.total_models} compliant "
            f"({summary.compliance_rate:.0f}%)[/{rate_color}]"
        )

    # JSON: structured output to stdout
    if json_output:
        # Use print (stdout) not console (stderr) so pipelines can parse it
        print(_format_json_output(summary))

    raise typer.Exit(0 if summary.failed_models == 0 else 1)
