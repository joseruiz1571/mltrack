"""Dashboard CLI commands."""

import time
from datetime import date, timedelta
from pathlib import Path

import typer
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich import box

from mltrack.core.storage import get_all_models, get_models_needing_review, get_risk_distribution
from mltrack.core.exceptions import DatabaseError
from mltrack.models.ai_model import (
    AIModel,
    RiskTier,
    DeploymentEnvironment,
    ModelStatus,
)
from mltrack.display.formatters import RISK_COLORS, format_risk_tier, format_status

console = Console()

dashboard_app = typer.Typer(
    help="View compliance dashboard.",
    invoke_without_command=True,
)


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
    # Handle common aliases
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


def _filter_models(
    models: list[AIModel],
    risk_tier: RiskTier | None = None,
    vendor: str | None = None,
    environment: DeploymentEnvironment | None = None,
) -> list[AIModel]:
    """Filter models based on criteria."""
    filtered = models

    if risk_tier is not None:
        filtered = [m for m in filtered if m.risk_tier == risk_tier]

    if vendor is not None:
        # Case-insensitive vendor matching
        vendor_lower = vendor.lower()
        filtered = [m for m in filtered if m.vendor and m.vendor.lower() == vendor_lower]

    if environment is not None:
        filtered = [m for m in filtered if m.deployment_environment == environment]

    return filtered


def _get_filter_description(
    risk_tier: RiskTier | None,
    vendor: str | None,
    environment: DeploymentEnvironment | None,
) -> str | None:
    """Build a description of active filters."""
    filters = []

    if risk_tier is not None:
        filters.append(f"Risk: {risk_tier.value.upper()}")

    if vendor is not None:
        filters.append(f"Vendor: {vendor}")

    if environment is not None:
        filters.append(f"Env: {environment.value.upper()}")

    return " | ".join(filters) if filters else None


def _get_overdue_count(models: list[AIModel]) -> int:
    """Count models with overdue reviews."""
    today = date.today()
    return sum(
        1 for m in models
        if m.status == ModelStatus.ACTIVE
        and m.next_review_date
        and m.next_review_date < today
    )


def _get_compliance_percentage(models: list[AIModel]) -> float:
    """Calculate percentage of models that are compliant (not overdue)."""
    active_models = [m for m in models if m.status == ModelStatus.ACTIVE]
    if not active_models:
        return 100.0

    today = date.today()
    compliant = sum(
        1 for m in active_models
        if not m.next_review_date or m.next_review_date >= today
    )
    return (compliant / len(active_models)) * 100


def _create_summary_panel(models: list[AIModel]) -> Panel:
    """Create the top summary panel with key metrics."""
    total = len(models)
    active = len([m for m in models if m.status == ModelStatus.ACTIVE])
    overdue = _get_overdue_count(models)
    compliance = _get_compliance_percentage(models)

    # Risk distribution
    risk_counts = {tier: 0 for tier in RiskTier}
    for model in models:
        if model.status == ModelStatus.ACTIVE:
            risk_counts[model.risk_tier] += 1

    # Build metrics table
    metrics_table = Table(box=None, show_header=False, padding=(0, 2))
    metrics_table.add_column("Metric", style="bold")
    metrics_table.add_column("Value", justify="right")

    metrics_table.add_row("Total Models", f"[bold cyan]{total}[/bold cyan]")
    metrics_table.add_row("Active Models", f"[green]{active}[/green]")

    # Compliance with color coding
    compliance_color = "green" if compliance >= 90 else "yellow" if compliance >= 70 else "red"
    metrics_table.add_row("Compliance", f"[{compliance_color}]{compliance:.1f}%[/{compliance_color}]")

    # Overdue with color
    overdue_color = "red" if overdue > 0 else "green"
    metrics_table.add_row("Overdue Reviews", f"[{overdue_color}]{overdue}[/{overdue_color}]")

    # Risk tier table
    risk_table = Table(box=None, show_header=False, padding=(0, 1))
    risk_table.add_column("Tier")
    risk_table.add_column("Count", justify="right")

    for tier in [RiskTier.CRITICAL, RiskTier.HIGH, RiskTier.MEDIUM, RiskTier.LOW]:
        count = risk_counts[tier]
        risk_table.add_row(format_risk_tier(tier), str(count))

    # Combine into grid
    grid = Table.grid(padding=(0, 4))
    grid.add_column()
    grid.add_column()
    grid.add_row(metrics_table, risk_table)

    return Panel(
        grid,
        title="[bold]Model Inventory Summary[/bold]",
        border_style="blue",
        padding=(1, 2),
    )


def _create_recent_additions_panel(models: list[AIModel]) -> Panel:
    """Create panel showing last 5 models added."""
    # Sort by created_at descending
    sorted_models = sorted(models, key=lambda m: m.created_at, reverse=True)[:5]

    if not sorted_models:
        return Panel(
            "[dim]No models in inventory[/dim]",
            title="[bold]Recent Additions[/bold]",
            border_style="cyan",
        )

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    table.add_column("Model", style="cyan", no_wrap=True, max_width=25)
    table.add_column("Vendor", max_width=15)
    table.add_column("Risk", justify="center")
    table.add_column("Added", style="dim")

    for model in sorted_models:
        added_date = model.created_at.strftime("%Y-%m-%d")
        table.add_row(
            model.model_name[:25],
            model.vendor[:15] if model.vendor else "",
            format_risk_tier(model.risk_tier),
            added_date,
        )

    return Panel(
        table,
        title="[bold]Recent Additions[/bold]",
        border_style="cyan",
        padding=(0, 1),
    )


def _create_reviews_needed_panel(models: list[AIModel]) -> Panel:
    """Create panel showing models needing review in next 30 days."""
    today = date.today()
    cutoff = today + timedelta(days=30)

    # Filter active models needing review
    needing_review = [
        m for m in models
        if m.status == ModelStatus.ACTIVE
        and m.next_review_date
        and m.next_review_date <= cutoff
    ]
    # Sort by next_review_date
    needing_review.sort(key=lambda m: m.next_review_date or date.max)
    needing_review = needing_review[:7]  # Show up to 7

    if not needing_review:
        return Panel(
            "[green]All models are up to date[/green]",
            title="[bold]Reviews Needed (30 days)[/bold]",
            border_style="yellow",
        )

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    table.add_column("Model", style="cyan", no_wrap=True, max_width=25)
    table.add_column("Risk", justify="center")
    table.add_column("Due", justify="right")
    table.add_column("Status")

    for model in needing_review:
        days_until = (model.next_review_date - today).days
        if days_until < 0:
            due_str = f"[bold red]{abs(days_until)}d overdue[/bold red]"
            status = "[bold red]OVERDUE[/bold red]"
        elif days_until == 0:
            due_str = "[yellow]Today[/yellow]"
            status = "[yellow]DUE[/yellow]"
        elif days_until <= 7:
            due_str = f"[yellow]{days_until}d[/yellow]"
            status = "[yellow]SOON[/yellow]"
        else:
            due_str = f"{days_until}d"
            status = "[dim]Upcoming[/dim]"

        table.add_row(
            model.model_name[:25],
            format_risk_tier(model.risk_tier),
            due_str,
            status,
        )

    return Panel(
        table,
        title="[bold]Reviews Needed (30 days)[/bold]",
        border_style="yellow",
        padding=(0, 1),
    )


def _create_high_risk_prod_panel(models: list[AIModel]) -> Panel:
    """Create panel showing high/critical risk models in production."""
    high_risk_prod = [
        m for m in models
        if m.status == ModelStatus.ACTIVE
        and m.deployment_environment == DeploymentEnvironment.PROD
        and m.risk_tier in [RiskTier.CRITICAL, RiskTier.HIGH]
    ]
    # Sort by risk tier (critical first), then name
    tier_order = {RiskTier.CRITICAL: 0, RiskTier.HIGH: 1}
    high_risk_prod.sort(key=lambda m: (tier_order.get(m.risk_tier, 2), m.model_name))

    if not high_risk_prod:
        return Panel(
            "[green]No high-risk models in production[/green]",
            title="[bold]High Risk in Production[/bold]",
            border_style="red",
        )

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    table.add_column("Model", style="cyan", no_wrap=True, max_width=25)
    table.add_column("Vendor", max_width=15)
    table.add_column("Risk", justify="center")
    table.add_column("Owner")

    for model in high_risk_prod[:7]:  # Show up to 7
        table.add_row(
            model.model_name[:25],
            model.vendor[:15] if model.vendor else "",
            format_risk_tier(model.risk_tier),
            model.business_owner[:15] if model.business_owner else "",
        )

    total = len(high_risk_prod)
    if total > 7:
        table.add_row(f"[dim]... and {total - 7} more[/dim]", "", "", "")

    return Panel(
        table,
        title=f"[bold]High Risk in Production ({total})[/bold]",
        border_style="red",
        padding=(0, 1),
    )


def _create_vendor_chart(models: list[AIModel]) -> Panel:
    """Create a horizontal bar chart of models by vendor."""
    active_models = [m for m in models if m.status == ModelStatus.ACTIVE]

    # Count by vendor
    vendor_counts: dict[str, int] = {}
    for model in active_models:
        vendor = model.vendor or "Unknown"
        vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1

    if not vendor_counts:
        return Panel(
            "[dim]No data[/dim]",
            title="[bold]By Vendor[/bold]",
            border_style="green",
        )

    # Sort by count descending, take top 6
    sorted_vendors = sorted(vendor_counts.items(), key=lambda x: x[1], reverse=True)[:6]
    max_count = sorted_vendors[0][1] if sorted_vendors else 1

    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_column("Vendor", style="bold", max_width=15, no_wrap=True)
    table.add_column("Bar", min_width=20)
    table.add_column("Count", justify="right", style="cyan")

    colors = ["blue", "cyan", "green", "yellow", "magenta", "red"]
    for i, (vendor, count) in enumerate(sorted_vendors):
        bar_width = int((count / max_count) * 18) if max_count > 0 else 0
        color = colors[i % len(colors)]
        bar = f"[{color}]{'█' * bar_width}[/{color}]"
        table.add_row(vendor[:15], bar, str(count))

    return Panel(
        table,
        title="[bold]By Vendor[/bold]",
        border_style="green",
        padding=(0, 1),
    )


def _create_environment_chart(models: list[AIModel]) -> Panel:
    """Create a horizontal bar chart of models by environment."""
    active_models = [m for m in models if m.status == ModelStatus.ACTIVE]

    # Count by environment
    env_counts = {
        "prod": 0,
        "staging": 0,
        "dev": 0,
        "unset": 0,
    }
    for model in active_models:
        if model.deployment_environment:
            env_counts[model.deployment_environment.value] += 1
        else:
            env_counts["unset"] += 1

    total = sum(env_counts.values())
    if total == 0:
        return Panel(
            "[dim]No data[/dim]",
            title="[bold]By Environment[/bold]",
            border_style="magenta",
        )

    max_count = max(env_counts.values()) if env_counts.values() else 1

    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_column("Env", style="bold", width=10)
    table.add_column("Bar", min_width=18)
    table.add_column("Count", justify="right", style="cyan")

    env_colors = {
        "prod": "red",
        "staging": "yellow",
        "dev": "green",
        "unset": "dim",
    }
    env_labels = {
        "prod": "PROD",
        "staging": "STAGING",
        "dev": "DEV",
        "unset": "Unset",
    }

    for env in ["prod", "staging", "dev", "unset"]:
        count = env_counts[env]
        if count > 0 or env != "unset":  # Always show prod/staging/dev
            bar_width = int((count / max_count) * 16) if max_count > 0 else 0
            color = env_colors[env]
            bar = f"[{color}]{'█' * bar_width}[/{color}]"
            table.add_row(env_labels[env], bar, str(count))

    return Panel(
        table,
        title="[bold]By Environment[/bold]",
        border_style="magenta",
        padding=(0, 1),
    )


def _build_dashboard(
    db_path: Path | None = None,
    risk_tier: RiskTier | None = None,
    vendor: str | None = None,
    environment: DeploymentEnvironment | None = None,
) -> Layout:
    """Build the complete dashboard layout."""
    try:
        models = get_all_models(db_path)
    except DatabaseError as e:
        # Return error layout
        layout = Layout()
        layout.update(Panel(
            f"[red]Database Error:[/red] {e.details}",
            title="[bold red]Error[/bold red]",
            border_style="red",
        ))
        return layout

    # Apply filters
    models = _filter_models(models, risk_tier, vendor, environment)

    # Create layout structure
    layout = Layout()

    layout.split_column(
        Layout(name="top", size=9),
        Layout(name="middle", size=14),
        Layout(name="bottom", size=10),
    )

    # Top section: Summary
    layout["top"].update(_create_summary_panel(models))

    # Middle section: Three panels
    layout["middle"].split_row(
        Layout(name="recent"),
        Layout(name="reviews"),
        Layout(name="high_risk"),
    )
    layout["middle"]["recent"].update(_create_recent_additions_panel(models))
    layout["middle"]["reviews"].update(_create_reviews_needed_panel(models))
    layout["middle"]["high_risk"].update(_create_high_risk_prod_panel(models))

    # Bottom section: Charts
    layout["bottom"].split_row(
        Layout(name="vendor"),
        Layout(name="environment"),
    )
    layout["bottom"]["vendor"].update(_create_vendor_chart(models))
    layout["bottom"]["environment"].update(_create_environment_chart(models))

    return layout


def _get_dashboard_header(
    watch: bool = False,
    filter_description: str | None = None,
) -> Panel:
    """Create the dashboard header."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    lines = ["[bold blue]MLTrack[/bold blue] Compliance Dashboard"]

    if filter_description:
        lines.append(f"[yellow]Filtered:[/yellow] {filter_description}")

    if watch:
        lines.append(f"[dim]Auto-refresh enabled | Last updated: {timestamp} | Press Ctrl+C to exit[/dim]")
    else:
        lines.append(f"[dim]{timestamp}[/dim]")

    return Panel(
        "\n".join(lines),
        border_style="blue",
        padding=(0, 1),
    )


@dashboard_app.callback(invoke_without_command=True)
def show_dashboard(
    ctx: typer.Context,
    watch: bool = typer.Option(
        False,
        "--watch",
        "-w",
        help="Enable auto-refresh mode (updates in place, press Ctrl+C to exit)",
    ),
    refresh_interval: int = typer.Option(
        30,
        "--interval",
        "-i",
        help="Seconds between refreshes in watch mode (5-300, default: 30)",
        min=5,
        max=300,
    ),
    risk: str | None = typer.Option(
        None,
        "--risk",
        "-r",
        help="Show only models with this risk tier (critical/high/medium/low)",
    ),
    vendor: str | None = typer.Option(
        None,
        "--vendor",
        "-V",
        help="Show only models from this vendor (case-insensitive)",
    ),
    environment: str | None = typer.Option(
        None,
        "--environment",
        "-e",
        help="Show only models in this environment (prod/staging/dev)",
    ),
) -> None:
    """
    Display an interactive compliance dashboard.

    Shows a real-time overview of your AI model inventory with:

    \b
    [bold cyan]Top Section - Summary Metrics:[/bold cyan]
      • Total models and active count
      • Compliance percentage
      • Overdue review count
      • Risk tier distribution

    \b
    [bold cyan]Middle Section - Key Lists:[/bold cyan]
      • Recent additions (last 5 models added)
      • Reviews needed in next 30 days
      • High/Critical risk models in production

    \b
    [bold cyan]Bottom Section - Distribution Charts:[/bold cyan]
      • Models by vendor (bar chart)
      • Models by environment (bar chart)

    \b
    [bold cyan]Watch Mode:[/bold cyan]
      Use --watch to enable auto-refresh. The dashboard updates in place
      at the specified interval. Press Ctrl+C to exit.

    \b
    [bold cyan]Filters:[/bold cyan]
      Filters can be combined to focus on specific model subsets.
      All metrics update to reflect the filtered view.

    \b
    [bold]Examples:[/bold]
      [dim]# View dashboard (one-time)[/dim]
      mltrack dashboard

      [dim]# Auto-refresh mode (default 30 seconds)[/dim]
      mltrack dashboard --watch
      mltrack dashboard -w

      [dim]# Custom refresh interval[/dim]
      mltrack dashboard --watch --interval 60
      mltrack dashboard -w -i 10

      [dim]# Filter by risk tier[/dim]
      mltrack dashboard --risk critical
      mltrack dashboard -r high

      [dim]# Filter by vendor[/dim]
      mltrack dashboard --vendor anthropic
      mltrack dashboard --vendor "In-house"

      [dim]# Filter by environment[/dim]
      mltrack dashboard --environment prod
      mltrack dashboard -e staging

      [dim]# Combine filters[/dim]
      mltrack dashboard --risk critical --environment prod
      mltrack dashboard -r high -V openai

      [dim]# Watch with filters[/dim]
      mltrack dashboard --watch --risk critical --environment prod

    \b
    [bold cyan]Related Commands:[/bold cyan]
      mltrack validate --all     See detailed compliance violations
      mltrack report compliance  Generate exportable compliance report
      mltrack list               See full model list
    """
    if ctx.invoked_subcommand is not None:
        return

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
                    title="[bold red]Error[/bold red]",
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
                    title="[bold red]Error[/bold red]",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

    # Get filter description for header
    filter_desc = _get_filter_description(risk_tier, vendor, env)

    if watch:
        # Use rich.live for auto-refresh
        console.print(_get_dashboard_header(watch=True, filter_description=filter_desc))
        console.print()

        try:
            with Live(
                _build_dashboard(risk_tier=risk_tier, vendor=vendor, environment=env),
                console=console,
                refresh_per_second=1,
                screen=False,
            ) as live:
                while True:
                    time.sleep(refresh_interval)
                    live.update(_build_dashboard(risk_tier=risk_tier, vendor=vendor, environment=env))
        except KeyboardInterrupt:
            console.print("\n[dim]Dashboard stopped.[/dim]")
    else:
        # Static display
        console.print(_get_dashboard_header(watch=False, filter_description=filter_desc))
        console.print()
        console.print(_build_dashboard(risk_tier=risk_tier, vendor=vendor, environment=env))
