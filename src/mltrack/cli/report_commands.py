"""Compliance reporting CLI commands."""

import csv
import json
from datetime import date
from pathlib import Path
from typing import Optional
from collections import defaultdict

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from mltrack.core.storage import get_all_models, REVIEW_FREQUENCY
from mltrack.core.exceptions import DatabaseError
from mltrack.models import RiskTier, ModelStatus, DeploymentEnvironment, AIModel
from mltrack.cli.validate_command import validate_model, ValidationSummary

console = Console()

REPORT_EPILOG = """
[bold cyan]Available Reports:[/bold cyan]
  compliance    Compliance status, violations, and review status
  inventory     Full model inventory grouped by vendor and risk
  risk          Risk distribution and concentration analysis

[bold cyan]Output Formats:[/bold cyan]
  terminal      Rich formatted display (default)
  csv           Export to CSV file (requires -o)
  json          Export to JSON file (requires -o)

[bold]Quick Examples:[/bold]
  mltrack report compliance                      Terminal display
  mltrack report compliance -f json -o out.json  Export to JSON
  mltrack report inventory -f csv -o inv.csv     Export to CSV
"""

report_app = typer.Typer(
    help="Generate compliance, inventory, and risk reports.",
    no_args_is_help=True,
    epilog=REPORT_EPILOG,
)

# Valid output formats
OUTPUT_FORMATS = ["terminal", "csv", "json"]

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


def _get_review_status(model: AIModel) -> tuple[str, str]:
    """Get review status and color for a model."""
    if model.next_review_date is None:
        return "No schedule", "dim"

    days_until = (model.next_review_date - date.today()).days

    if days_until < 0:
        return f"Overdue ({abs(days_until)} days)", "red"
    elif days_until == 0:
        return "Due today", "yellow"
    elif days_until <= 7:
        return f"Due in {days_until} days", "yellow"
    elif days_until <= 30:
        return f"Due in {days_until} days", "green"
    else:
        return f"Due in {days_until} days", "dim"


def _export_csv(data: list[dict], output_path: Path) -> None:
    """Export data to CSV file."""
    if not data:
        console.print("[yellow]No data to export.[/yellow]")
        return

    fieldnames = list(data[0].keys())
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    console.print(f"[green]Exported {len(data)} records to {output_path}[/green]")


def _export_json(data: dict | list, output_path: Path) -> None:
    """Export data to JSON file."""
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    console.print(f"[green]Exported report to {output_path}[/green]")


def _fetch_models() -> list[AIModel] | None:
    """Fetch all models, returning None and printing error if failed."""
    try:
        models = get_all_models()
    except DatabaseError as e:
        console.print(f"[red]Database error:[/red] {e.details}")
        return None

    if not models:
        console.print(
            Panel(
                "[yellow]No models in inventory.[/yellow]\n\n"
                "[dim]Add models with:[/dim] [cyan]mltrack add --interactive[/cyan]",
                title="Empty Inventory",
                border_style="yellow",
            )
        )
        return None

    return models


# =============================================================================
# COMPLIANCE REPORT
# =============================================================================

def _generate_compliance_report_terminal(models: list[AIModel]) -> None:
    """Generate compliance report for terminal output."""
    summary = ValidationSummary()
    for model in models:
        result = validate_model(model)
        summary.add_result(result)

    risk_counts = defaultdict(int)
    for model in models:
        risk_counts[model.risk_tier.value] += 1

    overdue = []
    upcoming = []
    current = []

    for model in models:
        if model.status != ModelStatus.ACTIVE:
            continue
        if model.next_review_date is None:
            continue

        days_until = (model.next_review_date - date.today()).days
        if days_until < 0:
            overdue.append(model)
        elif days_until <= 30:
            upcoming.append(model)
        else:
            current.append(model)

    console.print()
    console.print(Panel(
        "[bold]Compliance Report[/bold]\n"
        f"[dim]Generated: {date.today()}[/dim]",
        border_style="blue",
    ))

    console.print()
    console.print("[bold cyan]Risk Tier Distribution[/bold cyan]")
    risk_table = Table(box=box.SIMPLE)
    risk_table.add_column("Risk Tier", style="bold")
    risk_table.add_column("Count", justify="right")
    risk_table.add_column("Percentage", justify="right")

    total = len(models)
    for tier in ["critical", "high", "medium", "low"]:
        count = risk_counts.get(tier, 0)
        pct = (count / total * 100) if total > 0 else 0
        color = RISK_COLORS.get(RiskTier(tier), "white")
        risk_table.add_row(
            f"[{color}]{tier.upper()}[/{color}]",
            str(count),
            f"{pct:.1f}%",
        )
    risk_table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]", "100%")
    console.print(risk_table)

    console.print()
    console.print("[bold cyan]Compliance Status[/bold cyan]")
    compliance_table = Table(box=box.SIMPLE)
    compliance_table.add_column("Status", style="bold")
    compliance_table.add_column("Count", justify="right")

    compliance_table.add_row(
        "[green]Compliant[/green]",
        str(summary.passed_models),
    )
    compliance_table.add_row(
        "[red]Non-Compliant[/red]",
        str(summary.failed_models),
    )
    compliance_table.add_row(
        "[bold]Compliance Rate[/bold]",
        f"[bold]{summary.compliance_rate:.1f}%[/bold]",
    )
    console.print(compliance_table)

    console.print()
    console.print("[bold cyan]Review Status[/bold cyan]")
    review_table = Table(box=box.SIMPLE)
    review_table.add_column("Status", style="bold")
    review_table.add_column("Count", justify="right")

    review_table.add_row("[red]Overdue[/red]", str(len(overdue)))
    review_table.add_row("[yellow]Upcoming (30 days)[/yellow]", str(len(upcoming)))
    review_table.add_row("[green]Current[/green]", str(len(current)))
    console.print(review_table)

    failed_results = [r for r in summary.results if not r.passed]
    if failed_results:
        console.print()
        console.print("[bold red]Non-Compliant Models[/bold red]")
        for result in failed_results:
            console.print(f"\n  [cyan]{result.model.model_name}[/cyan] ({result.model.risk_tier.value.upper()})")
            for violation in result.violations:
                console.print(f"    [red]•[/red] {violation}")

    if overdue:
        console.print()
        console.print("[bold red]Overdue Reviews[/bold red]")
        overdue_table = Table(box=box.SIMPLE)
        overdue_table.add_column("Model")
        overdue_table.add_column("Risk")
        overdue_table.add_column("Days Overdue", justify="right")
        overdue_table.add_column("Last Review")

        for model in sorted(overdue, key=lambda m: m.next_review_date):
            days_overdue = (date.today() - model.next_review_date).days
            last_review = str(model.last_review_date) if model.last_review_date else "Never"
            overdue_table.add_row(
                model.model_name,
                _format_risk_tier(model.risk_tier),
                f"[red]{days_overdue}[/red]",
                last_review,
            )
        console.print(overdue_table)


def _generate_compliance_report_data(models: list[AIModel]) -> dict:
    """Generate compliance report data for JSON/CSV export."""
    summary = ValidationSummary()
    for model in models:
        result = validate_model(model)
        summary.add_result(result)

    risk_counts = defaultdict(int)
    for model in models:
        risk_counts[model.risk_tier.value] += 1

    overdue_count = 0
    upcoming_count = 0
    current_count = 0

    for model in models:
        if model.status != ModelStatus.ACTIVE or model.next_review_date is None:
            continue
        days_until = (model.next_review_date - date.today()).days
        if days_until < 0:
            overdue_count += 1
        elif days_until <= 30:
            upcoming_count += 1
        else:
            current_count += 1

    failed_results = [r for r in summary.results if not r.passed]

    return {
        "report_type": "compliance",
        "generated_date": date.today().isoformat(),
        "summary": {
            "total_models": len(models),
            "compliant": summary.passed_models,
            "non_compliant": summary.failed_models,
            "compliance_rate": round(summary.compliance_rate, 1),
        },
        "risk_distribution": dict(risk_counts),
        "review_status": {
            "overdue": overdue_count,
            "upcoming_30_days": upcoming_count,
            "current": current_count,
        },
        "violations": [
            {
                "model_name": r.model.model_name,
                "model_id": r.model.id,
                "risk_tier": r.model.risk_tier.value,
                "violations": r.violations,
            }
            for r in failed_results
        ],
    }


@report_app.command("compliance")
def compliance_report(
    format: str = typer.Option(
        "terminal",
        "--format", "-f",
        help=f"Output format: {', '.join(OUTPUT_FORMATS)} (csv/json require -o)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (required when using csv or json format)",
    ),
) -> None:
    """
    Generate compliance status report for auditors.

    Comprehensive compliance overview including:
    • Risk tier distribution with percentages
    • Compliance rate (passed vs failed validation)
    • Review status (overdue, upcoming, current)
    • List of non-compliant models with violations
    • Detailed overdue review list

    Ideal for quarterly compliance reviews and audit documentation.

    \b
    [bold cyan]Report Sections:[/bold cyan]
      Risk Distribution     Count and percentage by risk tier
      Compliance Status     Pass/fail counts and compliance rate
      Review Status         Overdue, upcoming (30 days), current
      Non-Compliant Models  Detailed violation list per model
      Overdue Reviews       Models past their review date

    \b
    [bold]Examples:[/bold]
      [dim]# Display in terminal[/dim]
      mltrack report compliance

      [dim]# Export to JSON for audit records[/dim]
      mltrack report compliance -f json -o compliance-q1-2025.json

      [dim]# Export violations to CSV for spreadsheet analysis[/dim]
      mltrack report compliance -f csv -o violations.csv

    \b
    [bold cyan]Related Commands:[/bold cyan]
      mltrack validate --all   Run compliance checks interactively
      mltrack reviewed <name>  Record a review to clear violations
    """
    if format not in OUTPUT_FORMATS:
        console.print(
            f"[red]Invalid format:[/red] '{format}'. "
            f"Must be one of: {', '.join(OUTPUT_FORMATS)}"
        )
        raise typer.Exit(1)

    if format != "terminal" and output is None:
        console.print(
            f"[red]Output file required for {format} format.[/red]\n"
            f"[dim]Use: mltrack report compliance -f {format} -o filename.{format}[/dim]"
        )
        raise typer.Exit(1)

    models = _fetch_models()
    if models is None:
        raise typer.Exit(0)

    if format == "terminal":
        _generate_compliance_report_terminal(models)
    else:
        data = _generate_compliance_report_data(models)
        if format == "json":
            if output:
                _export_json(data, output)
            else:
                print(json.dumps(data, indent=2))
        elif format == "csv":
            csv_data = []
            for violation in data.get("violations", []):
                for v in violation["violations"]:
                    csv_data.append({
                        "model_name": violation["model_name"],
                        "model_id": violation["model_id"],
                        "risk_tier": violation["risk_tier"],
                        "violation": v,
                    })
            if output:
                _export_csv(csv_data, output)


# =============================================================================
# INVENTORY REPORT
# =============================================================================

def _generate_inventory_report_terminal(models: list[AIModel]) -> None:
    """Generate inventory report for terminal output."""
    console.print()
    console.print(Panel(
        "[bold]Model Inventory Report[/bold]\n"
        f"[dim]Generated: {date.today()}[/dim]",
        border_style="blue",
    ))

    console.print()
    console.print("[bold cyan]Summary Statistics[/bold cyan]")
    stats_table = Table(box=box.SIMPLE)
    stats_table.add_column("Metric", style="bold")
    stats_table.add_column("Value", justify="right")

    active = len([m for m in models if m.status == ModelStatus.ACTIVE])
    deprecated = len([m for m in models if m.status == ModelStatus.DEPRECATED])
    decommissioned = len([m for m in models if m.status == ModelStatus.DECOMMISSIONED])

    stats_table.add_row("Total Models", str(len(models)))
    stats_table.add_row("Active", f"[green]{active}[/green]")
    stats_table.add_row("Deprecated", f"[yellow]{deprecated}[/yellow]")
    stats_table.add_row("Decommissioned", f"[dim]{decommissioned}[/dim]")
    console.print(stats_table)

    console.print()
    console.print("[bold cyan]Models by Vendor[/bold cyan]")
    vendor_groups = defaultdict(list)
    for model in models:
        vendor_groups[model.vendor].append(model)

    for vendor in sorted(vendor_groups.keys()):
        vendor_models = vendor_groups[vendor]
        console.print(f"\n  [bold]{vendor}[/bold] ({len(vendor_models)} models)")
        for model in sorted(vendor_models, key=lambda m: m.model_name):
            status, color = _get_review_status(model)
            console.print(
                f"    • {model.model_name} "
                f"[{RISK_COLORS.get(model.risk_tier, 'white')}]{model.risk_tier.value.upper()}[/{RISK_COLORS.get(model.risk_tier, 'white')}] "
                f"[{color}]{status}[/{color}]"
            )

    console.print()
    console.print("[bold cyan]Models by Risk Tier[/bold cyan]")
    risk_groups = defaultdict(list)
    for model in models:
        risk_groups[model.risk_tier].append(model)

    for tier in [RiskTier.CRITICAL, RiskTier.HIGH, RiskTier.MEDIUM, RiskTier.LOW]:
        tier_models = risk_groups.get(tier, [])
        if tier_models:
            color = RISK_COLORS.get(tier, "white")
            console.print(f"\n  [{color}]{tier.value.upper()}[/{color}] ({len(tier_models)} models)")
            for model in sorted(tier_models, key=lambda m: m.model_name):
                env = model.deployment_environment.value.upper() if model.deployment_environment else "—"
                console.print(f"    • {model.model_name} ({model.vendor}) [{env}]")


def _generate_inventory_report_data(models: list[AIModel]) -> list[dict]:
    """Generate inventory report data for JSON/CSV export."""
    return [
        {
            "id": m.id,
            "model_name": m.model_name,
            "vendor": m.vendor,
            "model_version": m.model_version,
            "risk_tier": m.risk_tier.value,
            "status": m.status.value,
            "use_case": m.use_case,
            "business_owner": m.business_owner,
            "technical_owner": m.technical_owner,
            "deployment_date": m.deployment_date.isoformat() if m.deployment_date else None,
            "deployment_environment": m.deployment_environment.value if m.deployment_environment else None,
            "data_classification": m.data_classification.value if m.data_classification else None,
            "last_review_date": m.last_review_date.isoformat() if m.last_review_date else None,
            "next_review_date": m.next_review_date.isoformat() if m.next_review_date else None,
            "api_endpoint": m.api_endpoint,
            "notes": m.notes,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
        for m in models
    ]


@report_app.command("inventory")
def inventory_report(
    format: str = typer.Option(
        "terminal",
        "--format", "-f",
        help=f"Output format: {', '.join(OUTPUT_FORMATS)} (csv/json require -o)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (required when using csv or json format)",
    ),
) -> None:
    """
    Generate complete model inventory report.

    Full listing of all AI models organized for easy review:
    • Summary statistics (total, active, deprecated, decommissioned)
    • Models grouped by vendor with review status
    • Models grouped by risk tier with environment info

    Useful for inventory audits and management reporting.

    \b
    [bold cyan]Report Sections:[/bold cyan]
      Summary Statistics    Model counts by lifecycle status
      Models by Vendor      Grouped listing with risk and review status
      Models by Risk Tier   Critical → Low with vendor and environment

    \b
    [bold cyan]Export Fields (CSV/JSON):[/bold cyan]
      All model attributes including ID, dates, owners, notes, timestamps

    \b
    [bold]Examples:[/bold]
      [dim]# Display in terminal[/dim]
      mltrack report inventory

      [dim]# Export full inventory to CSV[/dim]
      mltrack report inventory -f csv -o inventory.csv

      [dim]# Export to JSON for integration[/dim]
      mltrack report inventory -f json -o models.json

    \b
    [bold cyan]Related Commands:[/bold cyan]
      mltrack list              Simple model list with filtering
      mltrack export <file>     Export with filtering options
    """
    if format not in OUTPUT_FORMATS:
        console.print(
            f"[red]Invalid format:[/red] '{format}'. "
            f"Must be one of: {', '.join(OUTPUT_FORMATS)}"
        )
        raise typer.Exit(1)

    if format != "terminal" and output is None:
        console.print(
            f"[red]Output file required for {format} format.[/red]\n"
            f"[dim]Use: mltrack report inventory -f {format} -o filename.{format}[/dim]"
        )
        raise typer.Exit(1)

    models = _fetch_models()
    if models is None:
        raise typer.Exit(0)

    if format == "terminal":
        _generate_inventory_report_terminal(models)
    else:
        data = _generate_inventory_report_data(models)
        if format == "json":
            if output:
                _export_json(data, output)
            else:
                print(json.dumps(data, indent=2))
        elif format == "csv":
            if output:
                _export_csv(data, output)


# =============================================================================
# RISK REPORT
# =============================================================================

def _generate_risk_report_terminal(models: list[AIModel]) -> None:
    """Generate risk analysis report for terminal output."""
    console.print()
    console.print(Panel(
        "[bold]Risk Distribution Report[/bold]\n"
        f"[dim]Generated: {date.today()}[/dim]",
        border_style="blue",
    ))

    console.print()
    console.print("[bold cyan]Risk Tier Distribution[/bold cyan]")
    risk_counts = defaultdict(int)
    for model in models:
        if model.status == ModelStatus.ACTIVE:
            risk_counts[model.risk_tier] += 1

    total_active = sum(risk_counts.values())
    risk_table = Table(box=box.SIMPLE)
    risk_table.add_column("Risk Tier", style="bold")
    risk_table.add_column("Count", justify="right")
    risk_table.add_column("Percentage", justify="right")
    risk_table.add_column("Review Cycle", justify="right")

    for tier in [RiskTier.CRITICAL, RiskTier.HIGH, RiskTier.MEDIUM, RiskTier.LOW]:
        count = risk_counts.get(tier, 0)
        pct = (count / total_active * 100) if total_active > 0 else 0
        color = RISK_COLORS.get(tier, "white")
        risk_table.add_row(
            f"[{color}]{tier.value.upper()}[/{color}]",
            str(count),
            f"{pct:.1f}%",
            f"{REVIEW_FREQUENCY[tier]} days",
        )
    console.print(risk_table)

    high_risk_prod = [
        m for m in models
        if m.risk_tier in (RiskTier.CRITICAL, RiskTier.HIGH)
        and m.deployment_environment == DeploymentEnvironment.PROD
        and m.status == ModelStatus.ACTIVE
    ]

    console.print()
    console.print("[bold cyan]High-Risk Models in Production[/bold cyan]")
    if high_risk_prod:
        prod_table = Table(box=box.SIMPLE)
        prod_table.add_column("Model")
        prod_table.add_column("Risk")
        prod_table.add_column("Vendor")
        prod_table.add_column("Business Owner")
        prod_table.add_column("Review Status")

        for model in sorted(high_risk_prod, key=lambda m: (m.risk_tier.value, m.model_name)):
            status, color = _get_review_status(model)
            prod_table.add_row(
                model.model_name,
                _format_risk_tier(model.risk_tier),
                model.vendor,
                model.business_owner,
                f"[{color}]{status}[/{color}]",
            )
        console.print(prod_table)
    else:
        console.print("  [dim]No high-risk models in production[/dim]")

    console.print()
    console.print("[bold cyan]Models Without Recent Review[/bold cyan]")
    stale_models = []
    for model in models:
        if model.status != ModelStatus.ACTIVE:
            continue
        if model.last_review_date is None:
            stale_models.append((model, "Never reviewed"))
        elif (date.today() - model.last_review_date).days > 180:
            days_ago = (date.today() - model.last_review_date).days
            stale_models.append((model, f"{days_ago} days ago"))

    if stale_models:
        stale_table = Table(box=box.SIMPLE)
        stale_table.add_column("Model")
        stale_table.add_column("Risk")
        stale_table.add_column("Last Review")

        for model, last_review in sorted(stale_models, key=lambda x: x[0].risk_tier.value):
            stale_table.add_row(
                model.model_name,
                _format_risk_tier(model.risk_tier),
                f"[yellow]{last_review}[/yellow]",
            )
        console.print(stale_table)
    else:
        console.print("  [dim]All models have recent reviews[/dim]")

    console.print()
    console.print("[bold cyan]Risk Concentration by Vendor[/bold cyan]")
    vendor_risk = defaultdict(lambda: defaultdict(int))
    for model in models:
        if model.status == ModelStatus.ACTIVE:
            vendor_risk[model.vendor][model.risk_tier] += 1

    vendor_table = Table(box=box.SIMPLE)
    vendor_table.add_column("Vendor", style="bold")
    vendor_table.add_column("Critical", justify="right")
    vendor_table.add_column("High", justify="right")
    vendor_table.add_column("Medium", justify="right")
    vendor_table.add_column("Low", justify="right")
    vendor_table.add_column("Total", justify="right")

    for vendor in sorted(vendor_risk.keys()):
        risks = vendor_risk[vendor]
        total = sum(risks.values())
        vendor_table.add_row(
            vendor,
            f"[bold red]{risks.get(RiskTier.CRITICAL, 0)}[/bold red]" if risks.get(RiskTier.CRITICAL, 0) > 0 else "0",
            f"[red]{risks.get(RiskTier.HIGH, 0)}[/red]" if risks.get(RiskTier.HIGH, 0) > 0 else "0",
            f"[yellow]{risks.get(RiskTier.MEDIUM, 0)}[/yellow]" if risks.get(RiskTier.MEDIUM, 0) > 0 else "0",
            f"[green]{risks.get(RiskTier.LOW, 0)}[/green]" if risks.get(RiskTier.LOW, 0) > 0 else "0",
            str(total),
        )
    console.print(vendor_table)


def _generate_risk_report_data(models: list[AIModel]) -> dict:
    """Generate risk report data for JSON export."""
    risk_counts = defaultdict(int)
    for model in models:
        if model.status == ModelStatus.ACTIVE:
            risk_counts[model.risk_tier.value] += 1

    high_risk_prod = [
        {
            "model_name": m.model_name,
            "model_id": m.id,
            "risk_tier": m.risk_tier.value,
            "vendor": m.vendor,
            "business_owner": m.business_owner,
            "next_review_date": m.next_review_date.isoformat() if m.next_review_date else None,
        }
        for m in models
        if m.risk_tier in (RiskTier.CRITICAL, RiskTier.HIGH)
        and m.deployment_environment == DeploymentEnvironment.PROD
        and m.status == ModelStatus.ACTIVE
    ]

    stale_models = []
    for model in models:
        if model.status != ModelStatus.ACTIVE:
            continue
        if model.last_review_date is None:
            stale_models.append({
                "model_name": model.model_name,
                "model_id": model.id,
                "risk_tier": model.risk_tier.value,
                "last_review": None,
            })
        elif (date.today() - model.last_review_date).days > 180:
            stale_models.append({
                "model_name": model.model_name,
                "model_id": model.id,
                "risk_tier": model.risk_tier.value,
                "last_review": model.last_review_date.isoformat(),
            })

    vendor_risk = defaultdict(lambda: defaultdict(int))
    for model in models:
        if model.status == ModelStatus.ACTIVE:
            vendor_risk[model.vendor][model.risk_tier.value] += 1

    return {
        "report_type": "risk",
        "generated_date": date.today().isoformat(),
        "risk_distribution": dict(risk_counts),
        "high_risk_production": high_risk_prod,
        "models_without_recent_review": stale_models,
        "vendor_risk_concentration": {
            vendor: dict(risks) for vendor, risks in vendor_risk.items()
        },
    }


@report_app.command("risk")
def risk_report(
    format: str = typer.Option(
        "terminal",
        "--format", "-f",
        help=f"Output format: {', '.join(OUTPUT_FORMATS)} (csv/json require -o)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (required when using csv or json format)",
    ),
) -> None:
    """
    Generate risk distribution and concentration analysis.

    Risk-focused report for governance committees and risk managers:
    • Risk tier distribution with review cycle info
    • High-risk models deployed in production
    • Models without recent reviews (stale)
    • Risk concentration by vendor

    Helps identify risk concentrations and governance gaps.

    \b
    [bold cyan]Report Sections:[/bold cyan]
      Risk Tier Distribution       Count, percentage, review cycle per tier
      High-Risk in Production      Critical/High models in prod environment
      Without Recent Review        Models not reviewed in 180+ days
      Vendor Risk Concentration    Risk breakdown per vendor

    \b
    [bold cyan]Key Insights:[/bold cyan]
      • Identify vendor concentration risk
      • Spot high-risk production deployments
      • Find models needing attention
      • Track risk distribution trends

    \b
    [bold]Examples:[/bold]
      [dim]# Display in terminal[/dim]
      mltrack report risk

      [dim]# Export for risk committee[/dim]
      mltrack report risk -f json -o risk-analysis.json

      [dim]# Export vendor risk matrix to CSV[/dim]
      mltrack report risk -f csv -o vendor-risk.csv

    \b
    [bold cyan]Related Commands:[/bold cyan]
      mltrack validate --risk critical  Check critical models specifically
      mltrack dashboard --risk high     Dashboard filtered by risk
    """
    if format not in OUTPUT_FORMATS:
        console.print(
            f"[red]Invalid format:[/red] '{format}'. "
            f"Must be one of: {', '.join(OUTPUT_FORMATS)}"
        )
        raise typer.Exit(1)

    if format != "terminal" and output is None:
        console.print(
            f"[red]Output file required for {format} format.[/red]\n"
            f"[dim]Use: mltrack report risk -f {format} -o filename.{format}[/dim]"
        )
        raise typer.Exit(1)

    models = _fetch_models()
    if models is None:
        raise typer.Exit(0)

    if format == "terminal":
        _generate_risk_report_terminal(models)
    else:
        data = _generate_risk_report_data(models)
        if format == "json":
            if output:
                _export_json(data, output)
            else:
                print(json.dumps(data, indent=2))
        elif format == "csv":
            csv_data = []
            for vendor, risks in data.get("vendor_risk_concentration", {}).items():
                csv_data.append({
                    "vendor": vendor,
                    "critical": risks.get("critical", 0),
                    "high": risks.get("high", 0),
                    "medium": risks.get("medium", 0),
                    "low": risks.get("low", 0),
                })
            if output:
                _export_csv(csv_data, output)
