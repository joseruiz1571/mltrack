"""Registry discovery command — surface untracked models before examiners do.

MLTrack is a governance overlay, not a duplicate registry. This command
connects to an external ML platform registry, discovers all models there,
and compares them against MLTrack's inventory to identify governance gaps.
"""

import json
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from mltrack.core.registry import find_untracked
from mltrack.core.storage import get_all_models
from mltrack.core.exceptions import DatabaseError
from mltrack.adapters.mock_adapter import MockAdapter

console = Console()

# Registry sources available today
VALID_SOURCES = ["mock", "mlflow"]


def _get_adapter(source: str, uri: Optional[str] = None):
    """Return an adapter instance for the given source name."""
    if source == "mock":
        return MockAdapter()
    if source == "mlflow":
        try:
            from mltrack.adapters.mlflow_adapter import MlflowAdapter
            return MlflowAdapter(tracking_uri=uri)
        except ImportError:
            console.print(
                Panel(
                    "[red]mlflow is not installed.[/red]\n\n"
                    "[dim]Install it with:[/dim] [cyan]pip install mlflow[/cyan]",
                    title="[red]Missing Dependency[/red]",
                    border_style="red",
                )
            )
            return None
    return None


def _format_json_output(
    source: str,
    discovered_count: int,
    tracked_count: int,
    untracked: list,
) -> str:
    """Format discovery results as JSON for scripting."""
    return json.dumps(
        {
            "source": source,
            "summary": {
                "discovered": discovered_count,
                "tracked": tracked_count,
                "untracked": len(untracked),
                "governance_gap": len(untracked) > 0,
            },
            "untracked_models": [
                {
                    "name": m.name,
                    "version": m.version,
                    "source": m.source,
                    "description": m.description,
                    "tags": m.tags,
                }
                for m in untracked
            ],
        },
        indent=2,
        default=str,
    )


def discover_command(
    source: str = typer.Option(
        "mock",
        "--source", "-s",
        help=f"Registry to scan: {', '.join(VALID_SOURCES)}",
    ),
    uri: Optional[str] = typer.Option(
        None,
        "--uri",
        help="Registry URI (e.g. http://localhost:5000 for MLflow). Falls back to env var.",
    ),
    untracked_only: bool = typer.Option(
        False,
        "--untracked-only", "-u",
        help="Show only models missing from governance inventory",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON (for scripting)",
    ),
) -> None:
    """
    Scan an external ML registry and surface untracked models.

    Compares what exists in your ML platform against MLTrack's governance
    inventory. Any model found in the registry but absent from MLTrack is
    a governance gap — a model making decisions without documented ownership,
    risk classification, or review schedule.

    \b
    [bold cyan]Available Sources:[/bold cyan]
      mock        Realistic demo data — no external connection required
      mlflow      MLflow Model Registry (requires: pip install mlflow)

    \b
    [bold cyan]Examples:[/bold cyan]
      [dim]# Demo mode — no server needed[/dim]
      mltrack discover --source mock

      [dim]# MLflow — local server (default port)[/dim]
      mltrack discover --source mlflow --uri http://localhost:5000

      [dim]# MLflow — uses MLFLOW_TRACKING_URI env var[/dim]
      mltrack discover --source mlflow

      [dim]# Show only governance gaps[/dim]
      mltrack discover --source mlflow --uri http://localhost:5000 --untracked-only

      [dim]# JSON output for scripting[/dim]
      mltrack discover --source mlflow --json

    \b
    [bold cyan]Related Commands:[/bold cyan]
      mltrack add --interactive    Register a discovered model
      mltrack validate --all       Check compliance on tracked models
    """
    # Validate source
    if source not in VALID_SOURCES:
        console.print(
            Panel(
                f"[red]Unknown registry source:[/red] '{source}'\n\n"
                f"[dim]Available sources: {', '.join(VALID_SOURCES)}[/dim]",
                title="[red]Invalid Source[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    adapter = _get_adapter(source, uri=uri)
    if adapter is None:
        raise typer.Exit(1)

    # Test connection
    try:
        if not adapter.test_connection():
            console.print(
                Panel(
                    f"[red]Cannot connect to '{source}' registry.[/red]\n\n"
                    "[dim]Check your credentials and network access.[/dim]",
                    title="[red]Connection Failed[/red]",
                    border_style="red",
                )
            )
            raise typer.Exit(1)
    except ConnectionError as e:
        console.print(
            Panel(
                f"[red]Connection error:[/red] {e}",
                title="[red]Connection Failed[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    # Discover models from registry
    try:
        discovered = adapter.discover()
    except ConnectionError as e:
        console.print(
            Panel(
                f"[red]Discovery failed:[/red] {e}",
                title="[red]Registry Error[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    if not discovered:
        console.print(
            Panel(
                f"[yellow]No models found in '{source}' registry.[/yellow]",
                title="[yellow]Empty Registry[/yellow]",
                border_style="yellow",
            )
        )
        raise typer.Exit(0)

    # Get MLTrack inventory for comparison
    try:
        tracked_models = get_all_models()
        tracked_names = {m.model_name for m in tracked_models}
    except DatabaseError as e:
        console.print(
            Panel(
                f"[red]Could not read MLTrack inventory:[/red] {e.operation}\n\n"
                f"[dim]Details: {e.details}[/dim]",
                title="[red]Database Error[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    untracked = find_untracked(discovered, tracked_names)

    # JSON output
    if json_output:
        print(
            _format_json_output(
                source=source,
                discovered_count=len(discovered),
                tracked_count=len(tracked_names),
                untracked=untracked,
            )
        )
        raise typer.Exit(1 if untracked else 0)

    # Rich output
    models_to_show = untracked if untracked_only else discovered

    if not models_to_show:
        console.print(
            Panel(
                f"[green]All {len(discovered)} models in '{source}' registry are tracked.[/green]\n\n"
                "[dim]No governance gaps detected.[/dim]",
                title="[green]Fully Covered[/green]",
                border_style="green",
            )
        )
        raise typer.Exit(0)

    # Header
    console.print()
    console.print(
        Panel(
            f"[bold]Scanning [cyan]{source}[/cyan] registry…[/bold]\n"
            f"[dim]{len(discovered)} model{'s' if len(discovered) != 1 else ''} discovered "
            f"· {len(tracked_names)} in MLTrack inventory[/dim]",
            border_style="blue",
        )
    )
    console.print()

    # Results table
    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold",
        padding=(0, 1),
    )
    table.add_column("Model", style="cyan", min_width=28)
    table.add_column("Version", style="dim", min_width=8)
    table.add_column("Source", style="dim", min_width=8)
    table.add_column("Governance Status", min_width=20)

    for m in models_to_show:
        is_tracked = m.name in tracked_names
        if is_tracked:
            status = "[green]✓ tracked[/green]"
        else:
            status = "[bold red]⚠ NOT TRACKED[/bold red]"

        table.add_row(
            m.name,
            m.version or "—",
            m.source,
            status,
        )

    console.print(table)

    # Summary panel
    gap_count = len(untracked)
    if gap_count == 0:
        border = "green"
        title = "[green]NO GOVERNANCE GAPS[/green]"
    elif gap_count <= 2:
        border = "yellow"
        title = "[yellow]GOVERNANCE GAPS DETECTED[/yellow]"
    else:
        border = "red"
        title = "[red]GOVERNANCE GAPS DETECTED[/red]"

    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value", justify="right")

    summary_table.add_row("Discovered in registry", str(len(discovered)))
    summary_table.add_row(
        "Already tracked",
        f"[green]{len(discovered) - gap_count}[/green]",
    )
    summary_table.add_row(
        "Missing from inventory",
        f"[{'red' if gap_count > 0 else 'green'}]{gap_count}[/{'red' if gap_count > 0 else 'green'}]"
        + (" [dim]← action required[/dim]" if gap_count > 0 else ""),
    )

    console.print()
    console.print(Panel(summary_table, title=title, border_style=border))

    if gap_count > 0:
        console.print()
        console.print(
            f"[dim]{gap_count} model{'s' if gap_count != 1 else ''} found in registry "
            f"but missing from governance inventory.[/dim]"
        )
        console.print(
            "[dim]Register them with:[/dim] [cyan]mltrack add --interactive[/cyan]"
        )

    raise typer.Exit(1 if gap_count > 0 else 0)
