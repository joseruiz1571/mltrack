"""CLI command for generating sample data for demos."""

import random
from datetime import date, timedelta

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich import box

from mltrack.core.storage import create_model, get_all_models, delete_model, REVIEW_FREQUENCY
from mltrack.core.exceptions import ModelAlreadyExistsError, DatabaseError
from mltrack.models.ai_model import RiskTier, DeploymentEnvironment, DataClassification

console = Console()

# Realistic vendor data
VENDORS = [
    ("Anthropic", ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku", "claude-2"]),
    ("OpenAI", ["gpt-4-turbo", "gpt-4o", "gpt-4", "gpt-3.5-turbo", "text-embedding-ada"]),
    ("AWS", ["bedrock-titan", "comprehend-pii", "textract-analyzer", "fraud-detector"]),
    ("Azure", ["azure-openai-gpt4", "azure-cognitive", "form-recognizer", "anomaly-detector"]),
    ("Google", ["gemini-pro", "palm-2", "vertex-ai-fraud", "dialogflow-cx"]),
    ("In-house", ["credit-risk-model", "churn-predictor", "ltv-estimator", "fraud-detector-v2"]),
    ("Cohere", ["command-r", "embed-v3", "rerank-v3"]),
    ("Meta", ["llama-3-70b", "llama-3-8b"]),
]

# Financial services use cases with risk implications
USE_CASES = [
    # Critical risk - direct financial impact
    ("Automated trading signal generation for equities desk", RiskTier.CRITICAL, ["OpenAI", "Anthropic"]),
    ("Real-time credit decisioning for consumer loans", RiskTier.CRITICAL, ["In-house", "AWS"]),
    ("Algorithmic pricing for mortgage products", RiskTier.CRITICAL, ["In-house"]),
    ("High-frequency trading anomaly detection", RiskTier.CRITICAL, ["In-house", "AWS"]),
    ("Fraud detection for wire transfers over $1M", RiskTier.CRITICAL, ["AWS", "In-house"]),

    # High risk - significant regulatory or customer impact
    ("Customer service chatbot for investment advice", RiskTier.HIGH, ["Anthropic", "OpenAI"]),
    ("KYC document verification and extraction", RiskTier.HIGH, ["Azure", "AWS", "Google"]),
    ("Anti-money laundering transaction monitoring", RiskTier.HIGH, ["In-house", "AWS"]),
    ("Loan underwriting risk assessment", RiskTier.HIGH, ["In-house"]),
    ("Insurance claim fraud detection", RiskTier.HIGH, ["AWS", "In-house"]),
    ("Regulatory reporting automation (SEC/FINRA)", RiskTier.HIGH, ["Azure", "OpenAI"]),
    ("Customer sentiment analysis for complaints", RiskTier.HIGH, ["Anthropic", "Cohere"]),
    ("Portfolio risk analytics and stress testing", RiskTier.HIGH, ["In-house"]),

    # Medium risk - operational efficiency
    ("Document summarization for due diligence", RiskTier.MEDIUM, ["Anthropic", "OpenAI", "Cohere"]),
    ("Internal knowledge base search", RiskTier.MEDIUM, ["OpenAI", "Cohere", "Google"]),
    ("Meeting transcription and action items", RiskTier.MEDIUM, ["Azure", "Google", "OpenAI"]),
    ("Email classification and routing", RiskTier.MEDIUM, ["Google", "Azure", "AWS"]),
    ("Contract clause extraction", RiskTier.MEDIUM, ["Anthropic", "OpenAI", "Azure"]),
    ("Customer inquiry categorization", RiskTier.MEDIUM, ["Cohere", "OpenAI"]),
    ("Market research summarization", RiskTier.MEDIUM, ["Anthropic", "OpenAI"]),
    ("Compliance policy Q&A assistant", RiskTier.MEDIUM, ["Anthropic", "OpenAI"]),

    # Low risk - internal tools, non-customer facing
    ("Developer code assistance", RiskTier.LOW, ["Anthropic", "OpenAI", "Meta"]),
    ("Internal documentation generation", RiskTier.LOW, ["Anthropic", "OpenAI"]),
    ("Test data generation for QA", RiskTier.LOW, ["OpenAI", "Meta"]),
    ("Log analysis and anomaly alerting", RiskTier.LOW, ["AWS", "Azure", "In-house"]),
    ("IT helpdesk chatbot for employees", RiskTier.LOW, ["Azure", "OpenAI"]),
    ("Marketing content draft generation", RiskTier.LOW, ["Anthropic", "OpenAI", "Cohere"]),
]

# Owner names
BUSINESS_OWNERS = [
    "Sarah Chen (Trading Desk)",
    "Michael Rodriguez (Risk Management)",
    "Emily Watson (Compliance)",
    "David Kim (Consumer Lending)",
    "Jennifer Park (Wealth Management)",
    "Robert Singh (Operations)",
    "Lisa Thompson (Digital Banking)",
    "James Wilson (Commercial Banking)",
    "Maria Garcia (Insurance Products)",
    "Kevin O'Brien (Treasury)",
    "Amanda Foster (Customer Experience)",
    "Thomas Lee (IT Security)",
    "Rachel Green (Marketing)",
    "Daniel Brown (Legal)",
]

TECHNICAL_OWNERS = [
    "ML Platform Team",
    "Data Science - Risk",
    "AI Engineering",
    "Cloud Infrastructure",
    "Data Engineering",
    "Applied AI Team",
    "NLP Research Group",
    "Fraud Analytics",
    "Credit Modeling Team",
    "Digital Platforms",
    "Enterprise Architecture",
    "DevOps - AI/ML",
]

# API endpoints
API_ENDPOINTS = [
    "https://api.internal.bank.com/ml/v1/{model}",
    "https://ml-gateway.prod.internal/{model}",
    "https://ai-services.bank.com/v2/{model}",
    "https://models.internal.bank.com/{model}/predict",
    None,  # Some models don't have endpoints
    None,
]


def _generate_model_name(vendor: str, base_name: str, existing_names: set) -> str:
    """Generate a unique model name."""
    # Add some variation
    suffixes = ["", "-prod", "-v2", "-enterprise", "-fsi"]

    for suffix in suffixes:
        name = f"{base_name}{suffix}"
        if name not in existing_names:
            return name

    # Add number if still not unique
    for i in range(1, 100):
        name = f"{base_name}-{i}"
        if name not in existing_names:
            return name

    return f"{base_name}-{random.randint(1000, 9999)}"


def _generate_deployment_date(risk_tier: RiskTier, make_overdue: bool) -> date:
    """Generate a deployment date, optionally making the model overdue for review."""
    today = date.today()
    review_days = REVIEW_FREQUENCY[risk_tier]

    if make_overdue:
        # Deploy far enough back that review is overdue
        days_back = review_days + random.randint(10, 60)
    else:
        # Deploy within review window (compliant)
        days_back = random.randint(1, max(1, review_days - 10))

    return today - timedelta(days=days_back)


def _generate_sample_model(
    existing_names: set,
    overdue_probability: float = 0.25,
) -> dict:
    """Generate a single sample model."""
    # Pick a use case (determines risk tier and suitable vendors)
    use_case_text, risk_tier, suitable_vendors = random.choice(USE_CASES)

    # Pick vendor from suitable ones
    vendor_name = random.choice(suitable_vendors)

    # Find vendor's model names
    vendor_models = None
    for v_name, v_models in VENDORS:
        if v_name == vendor_name:
            vendor_models = v_models
            break

    if vendor_models:
        base_name = random.choice(vendor_models)
    else:
        base_name = f"{vendor_name.lower()}-model"

    model_name = _generate_model_name(vendor_name, base_name, existing_names)
    existing_names.add(model_name)

    # Determine if this model should be overdue
    make_overdue = random.random() < overdue_probability

    # Generate deployment date
    deployment_date = _generate_deployment_date(risk_tier, make_overdue)

    # Pick environment (production more likely for critical/high risk)
    if risk_tier in [RiskTier.CRITICAL, RiskTier.HIGH]:
        env_weights = [0.7, 0.2, 0.1]  # prod, staging, dev
    else:
        env_weights = [0.4, 0.3, 0.3]

    environment = random.choices(
        [DeploymentEnvironment.PROD, DeploymentEnvironment.STAGING, DeploymentEnvironment.DEV],
        weights=env_weights,
    )[0]

    # Data classification based on risk tier
    if risk_tier == RiskTier.CRITICAL:
        classification = random.choice([DataClassification.RESTRICTED, DataClassification.CONFIDENTIAL])
    elif risk_tier == RiskTier.HIGH:
        classification = random.choice([DataClassification.CONFIDENTIAL, DataClassification.INTERNAL])
    else:
        classification = random.choice([DataClassification.INTERNAL, DataClassification.PUBLIC, None])

    # Build model data
    model_data = {
        "model_name": model_name,
        "vendor": vendor_name,
        "risk_tier": risk_tier.value,
        "use_case": use_case_text,
        "business_owner": random.choice(BUSINESS_OWNERS),
        "technical_owner": random.choice(TECHNICAL_OWNERS),
        "deployment_date": deployment_date,
        "deployment_environment": environment.value if environment else None,
    }

    # Add optional fields randomly
    if random.random() > 0.3:
        model_data["model_version"] = f"{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 20)}"

    endpoint = random.choice(API_ENDPOINTS)
    if endpoint:
        model_data["api_endpoint"] = endpoint.format(model=model_name)

    if classification:
        model_data["data_classification"] = classification.value

    return model_data


def sample_data(
    count: int = typer.Option(
        20,
        "--count",
        "-n",
        help="Number of sample models to generate (1-100, default: 20)",
        min=1,
        max=100,
    ),
    clear: bool = typer.Option(
        False,
        "--clear",
        "-c",
        help="Delete all existing models before generating new samples",
    ),
    overdue_percent: int = typer.Option(
        25,
        "--overdue-percent",
        help="Percentage of models to make overdue for review (0-100, default: 25)",
        min=0,
        max=100,
    ),
) -> None:
    """
    Generate realistic sample data for demos and testing.

    Creates AI models with realistic financial services use cases,
    various vendors, risk tiers, and compliance states. Perfect for
    demonstrating MLTrack's governance capabilities.

    \b
    [bold cyan]Generated Data Includes:[/bold cyan]
      [bold]Vendors:[/bold]      Anthropic, OpenAI, AWS, Azure, Google, In-house,
                   Cohere, Meta
      [bold]Risk Tiers:[/bold]   Mix across Critical, High, Medium, Low
      [bold]Use Cases:[/bold]    26+ realistic financial services scenarios
      [bold]Environments:[/bold] Production, Staging, Development
      [bold]Compliance:[/bold]   Mix of compliant and overdue models

    \b
    [bold cyan]Financial Services Use Cases:[/bold cyan]
      • Trading signal generation (Critical)
      • Credit decisioning, fraud detection (Critical)
      • Customer service chatbots (High)
      • KYC verification, AML monitoring (High)
      • Document summarization (Medium)
      • Developer tools, code assistance (Low)

    \b
    [bold cyan]Options:[/bold cyan]
      --count, -n         Number of models to generate (default: 20)
      --clear, -c         Remove existing data first (fresh start)
      --overdue-percent   Control how many models are overdue (default: 25%)

    \b
    [bold]Examples:[/bold]
      [dim]# Generate 20 sample models (default)[/dim]
      mltrack sample-data

      [dim]# Generate more models[/dim]
      mltrack sample-data --count 50
      mltrack sample-data -n 100

      [dim]# Start fresh (clear existing data first)[/dim]
      mltrack sample-data --clear
      mltrack sample-data -c -n 30

      [dim]# Control compliance distribution[/dim]
      mltrack sample-data --overdue-percent 50   [dim]# Half overdue[/dim]
      mltrack sample-data --overdue-percent 0    [dim]# All compliant[/dim]

      [dim]# Demo setup: fresh start with 30 models, 40% overdue[/dim]
      mltrack sample-data --clear --count 30 --overdue-percent 40

    \b
    [bold cyan]After Generating:[/bold cyan]
      mltrack dashboard           View the dashboard with sample data
      mltrack validate --all      See compliance violations
      mltrack list                Browse the generated models
      mltrack report compliance   Generate compliance report
    """
    overdue_probability = overdue_percent / 100.0

    # Clear existing data if requested
    if clear:
        try:
            existing = get_all_models()
            if existing:
                console.print(f"\n[yellow]Clearing {len(existing)} existing model(s)...[/yellow]")
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("[red]Deleting models...", total=len(existing))
                    for model in existing:
                        delete_model(model.model_name)
                        progress.update(task, advance=1)
                console.print("[green]Existing data cleared.[/green]\n")
        except DatabaseError as e:
            console.print(f"[red]Error clearing data:[/red] {e.details}")
            raise typer.Exit(1)

    # Get existing model names to avoid duplicates
    try:
        existing_models = get_all_models()
        existing_names = {m.model_name for m in existing_models}
    except DatabaseError:
        existing_names = set()

    # Generate sample models
    console.print(f"\n[cyan]Generating {count} sample model(s)...[/cyan]\n")

    created = []
    skipped = []
    errors = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Creating models...", total=count)

        for _ in range(count):
            try:
                model_data = _generate_sample_model(existing_names, overdue_probability)
                model = create_model(model_data)
                created.append(model)
            except ModelAlreadyExistsError:
                skipped.append(model_data.get("model_name", "unknown"))
            except Exception as e:
                errors.append(str(e))

            progress.update(task, advance=1)

    # Show summary
    console.print()

    # Risk tier distribution
    risk_counts = {tier: 0 for tier in RiskTier}
    env_counts = {"prod": 0, "staging": 0, "dev": 0, "unset": 0}
    overdue_count = 0
    today = date.today()

    for model in created:
        risk_counts[model.risk_tier] += 1
        if model.deployment_environment:
            env_counts[model.deployment_environment.value] += 1
        else:
            env_counts["unset"] += 1
        if model.next_review_date and model.next_review_date < today:
            overdue_count += 1

    # Summary table
    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Models Created", f"[green]{len(created)}[/green]")
    if skipped:
        table.add_row("Skipped (duplicate)", f"[yellow]{len(skipped)}[/yellow]")
    if errors:
        table.add_row("Errors", f"[red]{len(errors)}[/red]")

    table.add_row("", "")
    table.add_row("[bold cyan]Risk Distribution[/bold cyan]", "")
    table.add_row("  Critical", f"[bold red]{risk_counts[RiskTier.CRITICAL]}[/bold red]")
    table.add_row("  High", f"[red]{risk_counts[RiskTier.HIGH]}[/red]")
    table.add_row("  Medium", f"[yellow]{risk_counts[RiskTier.MEDIUM]}[/yellow]")
    table.add_row("  Low", f"[green]{risk_counts[RiskTier.LOW]}[/green]")

    table.add_row("", "")
    table.add_row("[bold cyan]Environment[/bold cyan]", "")
    table.add_row("  Production", f"[red]{env_counts['prod']}[/red]")
    table.add_row("  Staging", f"[yellow]{env_counts['staging']}[/yellow]")
    table.add_row("  Development", f"[green]{env_counts['dev']}[/green]")

    table.add_row("", "")
    table.add_row("[bold cyan]Compliance[/bold cyan]", "")
    compliant = len(created) - overdue_count
    table.add_row("  Compliant", f"[green]{compliant}[/green]")
    table.add_row("  Overdue for review", f"[red]{overdue_count}[/red]")

    console.print(
        Panel(
            table,
            title="[green]✓ Sample Data Generated[/green]",
            border_style="green",
            subtitle="[dim]Run 'mltrack dashboard' to view • 'mltrack validate' to check compliance[/dim]",
        )
    )

    # Show some example models
    if created:
        console.print("\n[bold]Sample models created:[/bold]")
        example_table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
        example_table.add_column("Model", style="cyan", max_width=25)
        example_table.add_column("Vendor", max_width=12)
        example_table.add_column("Risk", justify="center")
        example_table.add_column("Use Case", max_width=40)

        risk_colors = {
            RiskTier.CRITICAL: "bold red",
            RiskTier.HIGH: "red",
            RiskTier.MEDIUM: "yellow",
            RiskTier.LOW: "green",
        }

        for model in created[:5]:
            color = risk_colors[model.risk_tier]
            example_table.add_row(
                model.model_name[:25],
                model.vendor[:12],
                f"[{color}]{model.risk_tier.value.upper()}[/{color}]",
                model.use_case[:40] + "..." if len(model.use_case) > 40 else model.use_case,
            )

        if len(created) > 5:
            example_table.add_row(
                f"[dim]... and {len(created) - 5} more[/dim]",
                "",
                "",
                "",
            )

        console.print(example_table)
