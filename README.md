# MLTrack

**Model Lineage Tracker** - A CLI tool for AI model governance and compliance management in financial services.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-469%20passing-brightgreen.svg)](#testing)

---

## Overview

MLTrack helps AI Risk Managers and compliance teams track deployed AI/ML models with automated review scheduling aligned to regulatory frameworks:

- **[SR 11-7](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm)** - Federal Reserve Model Risk Management Guidance
- **[NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework)** - AI Risk Management Framework
- **[ISO 42001](https://www.iso.org/standard/81230.html)** - AI Management System Standard

Built for financial services firms managing AI model inventories where regulatory compliance requires documented model governance, ownership tracking, and scheduled reviews.

---

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Model Inventory** | Track AI models with vendor, ownership, risk tier, and deployment metadata |
| **Risk-Based Review Cycles** | Automatic review scheduling based on risk tier (Critical: 30d, High: 90d, Medium: 180d, Low: 365d) |
| **Compliance Validation** | Check models against governance requirements with detailed violation reports |
| **Interactive Dashboard** | Real-time terminal dashboard with filtering and auto-refresh |
| **Audit Reports** | Generate compliance, inventory, and risk reports (terminal, CSV, JSON) |
| **Bulk Import/Export** | Import/export model data via CSV or JSON with field mapping |
| **Sample Data Generation** | Generate realistic financial services demo data |

### Terminal Dashboard

```
┌─────────────────────────── Model Inventory Summary ───────────────────────────┐
│                                                                               │
│  Total Models      20       CRITICAL   3                                      │
│  Active Models     18       HIGH       5                                      │
│  Compliance      85.0%      MEDIUM     7                                      │
│  Overdue Reviews   3        LOW        5                                      │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
┌─── Recent Additions ────┐┌─── Reviews Needed (30 days) ─┐┌─ High Risk in Prod ─┐
│ Model         Risk Added││ Model         Risk Due Status││ Model      Vendor   │
│ claude-3      HIGH 01-22││ gpt-4-turbo   CRIT 5d  SOON  ││ gpt-4      OpenAI   │
│ fraud-v2      CRIT 01-21││ fraud-v2      CRIT 12d SOON  ││ claude-3   Anthropic│
│ bedrock-titan MED  01-20││ credit-risk   HIGH 3d overdue││ fraud-v2   In-house │
└─────────────────────────┘└───────────────────────────────┘└─────────────────────┘
┌──────────── By Vendor ────────────┐┌──────────── By Environment ─────────────┐
│ Anthropic  ████████████████  8    ││ PROD     ████████████████████  12       │
│ OpenAI     ████████████      5    ││ STAGING  ████████            4          │
│ AWS        ██████            3    ││ DEV      ████████            4          │
│ In-house   ████              2    │└──────────────────────────────────────────┘
└───────────────────────────────────┘
```

### Compliance Validation

```
┌──────────────────── Validating 20 models ────────────────────┐
│                                                              │
│  ✗ FAIL  gpt-4-turbo  CRITICAL                              │
│      • Review overdue by 5 days (CRITICAL requires 30 days) │
│      • Production model missing data classification         │
│                                                              │
│  ✗ FAIL  credit-risk-model  HIGH                            │
│      • Review overdue by 12 days (HIGH requires 90 days)    │
│                                                              │
│  ✓ PASS  claude-3-opus  HIGH                                │
│  ✓ PASS  fraud-detector  CRITICAL                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
┌─────────────── NEEDS ATTENTION ───────────────┐
│  Total Models      20                         │
│  Passed            18                         │
│  Failed            2                          │
│  Compliance Rate   90.0%                      │
└───────────────────────────────────────────────┘
```

---

## Installation

### Requirements

- Python 3.9 or higher
- pip (Python package manager)

### Install from Source

```bash
# Clone the repository
git clone https://github.com/joseruiz1571/mltrack.git
cd mltrack

# Install in development mode
pip install -e ".[dev]"

# Verify installation
mltrack --version
```

### Dependencies

- **typer** - CLI framework with Rich integration
- **rich** - Terminal formatting and layouts
- **sqlalchemy** - Database ORM (SQLite by default)

---

## Quick Start

### 1. Generate Sample Data

Start with realistic demo data to explore all features:

```bash
mltrack sample-data --count 20
```

This creates 20 AI models with realistic financial services use cases, various vendors, and a mix of compliant/overdue review statuses.

### 2. View the Dashboard

```bash
mltrack dashboard
```

Or with auto-refresh:

```bash
mltrack dashboard --watch --interval 30
```

### 3. Run Compliance Checks

```bash
mltrack validate --all
```

### 4. Add Your First Model

Interactive mode with guided prompts:

```bash
mltrack add --interactive
```

Or via command-line flags:

```bash
mltrack add \
  --name "claude-sonnet-4" \
  --vendor "Anthropic" \
  --risk-tier high \
  --use-case "Customer service chatbot for financial advice" \
  --business-owner "Jane Smith (Product)" \
  --technical-owner "ML Platform Team" \
  --deployment-date 2025-01-15 \
  --environment prod
```

---

## Command Reference

### Model Management

| Command | Description | Example |
|---------|-------------|---------|
| `mltrack add` | Add a new model | `mltrack add -i` |
| `mltrack list` | List all models | `mltrack list --risk critical` |
| `mltrack show <name>` | Show model details | `mltrack show claude-sonnet-4` |
| `mltrack update <name>` | Update a model | `mltrack update claude-sonnet-4 --status deprecated` |
| `mltrack delete <name>` | Delete a model | `mltrack delete old-model` |

### Compliance & Reviews

| Command | Description | Example |
|---------|-------------|---------|
| `mltrack validate` | Validate compliance | `mltrack validate --all` |
| `mltrack reviewed <name>` | Record a review | `mltrack reviewed claude-sonnet-4 -d today` |
| `mltrack dashboard` | View dashboard | `mltrack dashboard --watch` |

### Reports

| Command | Description | Example |
|---------|-------------|---------|
| `mltrack report compliance` | Compliance status | `mltrack report compliance -f json -o report.json` |
| `mltrack report inventory` | Full inventory | `mltrack report inventory -f csv -o inventory.csv` |
| `mltrack report risk` | Risk analysis | `mltrack report risk` |

### Data Operations

| Command | Description | Example |
|---------|-------------|---------|
| `mltrack import <file>` | Import from CSV/JSON | `mltrack import models.csv --update` |
| `mltrack export <file>` | Export to CSV/JSON | `mltrack export backup.json --risk high` |
| `mltrack sample-data` | Generate demo data | `mltrack sample-data -n 50 --clear` |

---

## Use Case Examples

### Adding Your First Model

```bash
# Interactive mode - recommended for first-time users
mltrack add --interactive

# Output:
# ┌─────────────── Add New AI Model ───────────────┐
# │ Enter model details below.                     │
# │ Required fields are marked with *              │
# └────────────────────────────────────────────────┘
#
# * Model name (e.g., fraud-detection-v2): claude-sonnet-4
# * Vendor (e.g., anthropic, openai): Anthropic
# ...
```

### Running Compliance Checks

```bash
# Check all models
mltrack validate --all

# Check only critical risk models
mltrack validate --risk critical

# Check a specific model
mltrack validate --model-id "claude-sonnet-4"

# Output as JSON for CI/CD integration
mltrack validate --all --json
```

### Recording a Model Review

After completing a quarterly model review:

```bash
mltrack reviewed "gpt-4-turbo" --date 2025-01-22 --notes "Quarterly security review completed"

# Output:
# ┌────────────── ✓ Review Recorded ──────────────┐
# │ Model          gpt-4-turbo                    │
# │ Risk Tier      CRITICAL                       │
# │ Review Cycle   30 days                        │
# │                                               │
# │ Last Review (was)   2024-12-20               │
# │ Last Review (now)   2025-01-22               │
# │                                               │
# │ Next Review (was)   2025-01-19 (3 days overdue)│
# │ Next Review (now)   2025-02-21 (in 30 days)  │
# └───────────────────────────────────────────────┘
```

### Generating Audit Reports

```bash
# Terminal report
mltrack report compliance

# Export for auditors (JSON)
mltrack report compliance -f json -o compliance-q1-2025.json

# Export inventory to CSV
mltrack report inventory -f csv -o model-inventory.csv
```

### Viewing the Dashboard

```bash
# Static view
mltrack dashboard

# Auto-refresh every 60 seconds
mltrack dashboard --watch --interval 60

# Filter by risk tier
mltrack dashboard --risk critical

# Filter by vendor
mltrack dashboard --vendor anthropic

# Combine filters
mltrack dashboard --risk high --environment prod
```

### Bulk Import/Export

```bash
# Export current inventory
mltrack export backup.json

# Export only production models
mltrack export production-models.csv --environment prod

# Export template for new data entry
mltrack export template.csv --template

# Import from CSV (skip duplicates by default)
mltrack import new-models.csv

# Import with updates for existing models
mltrack import updates.csv --update

# Validate without importing
mltrack import data.csv --validate
```

---

## Data Model

### AIModel Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_name` | string | Yes | Unique identifier for the model |
| `vendor` | string | Yes | Model provider (Anthropic, OpenAI, AWS, etc.) |
| `risk_tier` | enum | Yes | critical, high, medium, low |
| `use_case` | text | Yes | Business use case description |
| `business_owner` | string | Yes | Accountable business stakeholder |
| `technical_owner` | string | Yes | Technical team/person maintaining the model |
| `deployment_date` | date | Yes | When the model was deployed |
| `model_version` | string | No | Version identifier |
| `deployment_environment` | enum | No | prod, staging, dev |
| `api_endpoint` | string | No | API endpoint URL |
| `data_classification` | enum | No | public, internal, confidential, restricted |
| `status` | enum | Auto | active, deprecated, decommissioned |
| `last_review_date` | date | Auto | Last compliance review date |
| `next_review_date` | date | Auto | Calculated based on risk tier |
| `notes` | text | No | Additional notes and review history |

### Risk Tier Review Cycles

Aligned with SR 11-7 Model Risk Management guidance:

| Risk Tier | Review Frequency | Typical Use Cases |
|-----------|------------------|-------------------|
| **CRITICAL** | Every 30 days | Trading algorithms, credit decisioning, fraud detection |
| **HIGH** | Every 90 days | Customer-facing chatbots, KYC verification, AML monitoring |
| **MEDIUM** | Every 180 days | Document summarization, internal search, meeting transcription |
| **LOW** | Every 365 days | Developer tools, test data generation, internal documentation |

---

## Testing

MLTrack includes a comprehensive test suite with 469 tests covering all functionality.

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=mltrack --cov-report=term-missing

# Run specific test file
pytest tests/test_dashboard_command.py

# Run tests matching a pattern
pytest -k "test_validate"
```

### Test Categories

| Category | Tests | Coverage |
|----------|-------|----------|
| Model CRUD | 45 | Core storage operations |
| Add Command | 28 | Interactive and flag-based model creation |
| List/Show/Update/Delete | 52 | Model retrieval and modification |
| Validate Command | 38 | Compliance validation logic |
| Dashboard | 74 | Metrics, filtering, display |
| Import Command | 52 | CSV/JSON parsing, field mapping |
| Export Command | 45 | File generation, filtering |
| Sample Data | 33 | Demo data generation |
| Reports | 42 | Compliance, inventory, risk reports |

---

## Project Structure

```
mltrack/
├── src/mltrack/
│   ├── cli/                    # CLI commands
│   │   ├── main.py            # Entry point, command registration
│   │   ├── add_command.py     # mltrack add
│   │   ├── list_command.py    # mltrack list
│   │   ├── show_command.py    # mltrack show
│   │   ├── update_command.py  # mltrack update
│   │   ├── delete_command.py  # mltrack delete
│   │   ├── validate_command.py # mltrack validate
│   │   ├── reviewed_command.py # mltrack reviewed
│   │   ├── dashboard_commands.py # mltrack dashboard
│   │   ├── report_commands.py  # mltrack report
│   │   ├── import_command.py   # mltrack import
│   │   ├── export_command.py   # mltrack export
│   │   └── sample_data_command.py # mltrack sample-data
│   ├── core/                   # Business logic
│   │   ├── database.py        # SQLAlchemy setup
│   │   ├── storage.py         # CRUD operations
│   │   └── exceptions.py      # Custom exceptions
│   ├── models/                 # Data models
│   │   └── ai_model.py        # AIModel SQLAlchemy model
│   └── display/               # Output formatting
│       └── formatters.py      # Rich formatting helpers
├── tests/                      # Test suite (469 tests)
├── pyproject.toml             # Project configuration
└── README.md
```

---

## Contributing

Contributions are welcome! This project follows standard Python development practices.

### Development Setup

```bash
# Clone and install
git clone https://github.com/joseruiz1571/mltrack.git
cd mltrack
pip install -e ".[dev]"

# Create a branch
git checkout -b feature/your-feature

# Make changes and run tests
pytest

# Submit a pull request
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Write docstrings for public functions
- Add tests for new functionality

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Roadmap

- [ ] Model lineage tracking (upstream/downstream dependencies)
- [ ] Integration with model registries (MLflow, Weights & Biases)
- [ ] Slack/Teams notifications for overdue reviews
- [ ] Web UI dashboard
- [ ] Multi-user support with RBAC
- [ ] Audit log export for regulators

---

## Author

**Jose Ruiz-Vazquez**

- GitHub: [@joseruiz1571](https://github.com/joseruiz1571)

---

## Acknowledgments

- Built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)
- Regulatory guidance from Federal Reserve SR 11-7 and NIST AI RMF
- Inspired by the real-world challenges of AI governance in financial services

---

<p align="center">
  <i>Built for AI Risk Managers who take model governance seriously.</i>
</p>
