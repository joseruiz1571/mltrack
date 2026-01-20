"""Rich formatting utilities for terminal output."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from mltrack.models.ai_model import AIModel, RiskTier, ModelStatus

console = Console()

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


def format_risk_tier(tier: RiskTier) -> str:
    """Format risk tier with color."""
    color = RISK_COLORS.get(tier, "white")
    return f"[{color}]{tier.value.upper()}[/{color}]"


def format_status(status: ModelStatus) -> str:
    """Format status with color."""
    color = STATUS_COLORS.get(status, "white")
    return f"[{color}]{status.value.upper()}[/{color}]"


def create_model_table(models: list[AIModel]) -> Table:
    """Create a Rich table for displaying models."""
    table = Table(title="AI Model Inventory", show_header=True, header_style="bold")

    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Vendor")
    table.add_column("Risk", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Business Owner")
    table.add_column("Deployed")

    for model in models:
        table.add_row(
            model.model_name,
            model.vendor,
            format_risk_tier(model.risk_tier),
            format_status(model.status),
            model.business_owner,
            str(model.deployment_date),
        )

    return table


def create_model_detail_panel(model: AIModel) -> Panel:
    """Create a Rich panel showing model details."""
    # Format optional values
    env = model.deployment_environment.value.upper() if model.deployment_environment else "N/A"
    data_class = model.data_classification.value.upper() if model.data_classification else "N/A"

    content = f"""[bold cyan]Core Information[/bold cyan]
[bold]Model Name:[/bold] {model.model_name}
[bold]Vendor:[/bold] {model.vendor}
[bold]Version:[/bold] {model.model_version or 'N/A'}
[bold]Risk Tier:[/bold] {format_risk_tier(model.risk_tier)}
[bold]Status:[/bold] {format_status(model.status)}

[bold cyan]Ownership[/bold cyan]
[bold]Business Owner:[/bold] {model.business_owner}
[bold]Technical Owner:[/bold] {model.technical_owner}
[bold]Use Case:[/bold] {model.use_case}

[bold cyan]Deployment[/bold cyan]
[bold]Deployment Date:[/bold] {model.deployment_date}
[bold]Environment:[/bold] {env}
[bold]API Endpoint:[/bold] {model.api_endpoint or 'N/A'}

[bold cyan]Compliance[/bold cyan]
[bold]Last Review:[/bold] {model.last_review_date or 'Never reviewed'}
[bold]Next Review:[/bold] {model.next_review_date or 'Not scheduled'}
[bold]Data Classification:[/bold] {data_class}

[bold cyan]Notes[/bold cyan]
{model.notes or '[dim]No notes[/dim]'}"""

    return Panel(
        content,
        title=f"[bold]Model: {model.model_name}[/bold]",
        subtitle=f"ID: {model.id}",
        border_style="blue",
    )


def create_risk_summary_table(distribution: dict[str, int]) -> Table:
    """Create a table showing risk distribution."""
    table = Table(title="Risk Distribution", show_header=True, header_style="bold")

    table.add_column("Risk Tier", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Bar", min_width=20)

    total = sum(distribution.values())
    max_count = max(distribution.values()) if distribution.values() else 1

    # Order by severity
    order = ["critical", "high", "medium", "low"]

    for tier_name in order:
        count = distribution.get(tier_name, 0)
        tier = RiskTier(tier_name)
        bar_width = int((count / max_count) * 20) if max_count > 0 else 0
        color = RISK_COLORS.get(tier, "white").replace("bold ", "")
        bar = f"[{color}]{'█' * bar_width}[/{color}]"

        table.add_row(
            format_risk_tier(tier),
            str(count),
            bar,
        )

    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]", "")

    return table
