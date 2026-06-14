"""CLI commands for exporting and validating Governance Model Cards.

``mltrack card export <model>``  — inventory record -> schema-valid Model Card
``mltrack card validate <file>`` — check a Model Card JSON against the schema
"""

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from mltrack.core.exceptions import DatabaseError, ModelNotFoundError
from mltrack.core.storage import get_all_models, get_model
from mltrack.cli.error_helpers import (
    error_database,
    error_file_not_found,
    error_file_read,
    error_file_write,
    error_model_not_found,
)
from mltrack.services.card_service import (
    CARD_SPEC_VERSION,
    model_to_card,
    validate_card,
)

console = Console()

card_app = typer.Typer(
    name="card",
    help="Export and validate Governance Model Cards",
    no_args_is_help=True,
)


@card_app.command("export")
def export_card(
    identifier: str = typer.Argument(
        ..., help="Model name or UUID to export (partial ID match supported)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write the card to this file (default: stdout)"
    ),
    no_validate: bool = typer.Option(
        False, "--no-validate", help="Skip schema validation of the generated card"
    ),
) -> None:
    """
    Export an mltrack model as a Governance Model Card (JSON).

    Maps the model's inventory record onto the Governance Card Stack model-card
    schema, producing a portable, schema-valid governance artifact. The card is
    validated against the schema before it is emitted unless --no-validate is set.

    \b
    [bold]Examples:[/bold]
      [dim]# Print a card to stdout (pipe to jq, a file, etc.)[/dim]
      mltrack card export fraud-detector
      mltrack card export fraud-detector | jq .metadata

      [dim]# Write a card to a file[/dim]
      mltrack card export fraud-detector -o fraud-detector.card.json
    """
    try:
        model = get_model(identifier)
    except ModelNotFoundError:
        try:
            available = [m.model_name for m in get_all_models()]
        except DatabaseError:
            available = None
        error_model_not_found(identifier, available)
        raise typer.Exit(1)
    except DatabaseError as exc:
        error_database(exc.operation, exc.details)
        raise typer.Exit(1)

    card = model_to_card(model)

    if not no_validate:
        errors = validate_card(card)
        if errors:
            console.print(
                Panel(
                    "\n".join(f"[red]•[/red] {e}" for e in errors),
                    title="[bold red]Generated card failed schema validation[/bold red]",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

    payload = json.dumps(card, indent=2)

    if output is not None:
        try:
            output.write_text(payload + "\n", encoding="utf-8")
        except OSError as exc:
            error_file_write(str(output), str(exc))
            raise typer.Exit(1)
        console.print(
            Panel(
                f"[green]✓[/green] Model Card written to [cyan]{output}[/cyan]\n"
                f"[dim]card_type=model  spec_version={CARD_SPEC_VERSION}  "
                f"uuid={card['metadata']['uuid']}[/dim]",
                title="[bold green]Card Exported[/bold green]",
                title_align="left",
                border_style="green",
            )
        )
    else:
        # Raw JSON to stdout so it pipes cleanly into jq / files.
        print(payload)


@card_app.command("validate")
def validate_card_file(
    card_file: Path = typer.Argument(..., help="Path to a Model Card JSON file"),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress output; rely on the exit code (for CI gates)"
    ),
) -> None:
    """
    Validate a Model Card JSON file against the Governance Card Stack schema.

    Exit code 0 = valid, 1 = invalid. Designed to gate CI pipelines.

    \b
    [bold]Examples:[/bold]
      mltrack card validate fraud-detector.card.json
      mltrack card export fraud-detector -o c.json && mltrack card validate c.json
    """
    if not card_file.is_file():
        error_file_not_found(str(card_file), expected_format="JSON")
        raise typer.Exit(1)

    try:
        raw = card_file.read_text(encoding="utf-8")
    except OSError as exc:
        error_file_read(str(card_file), str(exc))
        raise typer.Exit(1)

    try:
        card = json.loads(raw)
    except json.JSONDecodeError as exc:
        if not quiet:
            console.print(
                Panel(
                    f"[red]Invalid JSON:[/red] {exc}",
                    title="[bold red]Validation Failed[/bold red]",
                    border_style="red",
                )
            )
        raise typer.Exit(1)

    errors = validate_card(card)
    if errors:
        if not quiet:
            count = len(errors)
            console.print(
                Panel(
                    "\n".join(f"[red]•[/red] {e}" for e in errors),
                    title=f"[bold red]✗ Invalid Model Card[/bold red] "
                    f"[dim]({count} issue{'s' if count != 1 else ''})[/dim]",
                    border_style="red",
                )
            )
        raise typer.Exit(1)

    if not quiet:
        console.print(
            Panel(
                f"[green]✓[/green] [bold]{card_file.name}[/bold] is a valid "
                f"Governance Model Card\n"
                f"[dim]card_type={card.get('card_type')}  "
                f"spec_version={card.get('spec_version')}[/dim]",
                title="[bold green]Valid[/bold green]",
                title_align="left",
                border_style="green",
            )
        )
