# MLTrack

**Model Lineage Tracker** - A CLI tool for AI model governance and compliance management in financial services.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-566%20passing-brightgreen.svg)](#testing)

---

## The Problem

**Financial institutions deploying AI models face a critical governance gap.**

As AI adoption accelerates in banking and financial services, regulatory scrutiny is intensifying. The Federal Reserve, OCC, and FDIC now require firms to maintain comprehensive AI model inventories with documented ownership, risk assessments, and scheduled reviews. Yet most organizations still track this information in spreadsheets—if at all.

**The consequences of poor AI governance are severe:**

- **Regulatory penalties**: Examiners cite inadequate model inventories as MRA (Matter Requiring Attention) findings
- **Operational risk**: Orphaned models with no documented owner continue running in production
- **Compliance failures**: Review deadlines pass unnoticed, creating audit trail gaps
- **Reputational damage**: Models making decisions without proper oversight

**MLTrack solves this by providing:**

- A single source of truth for all deployed AI/ML models
- Automated review scheduling based on risk tier
- Compliance validation against governance requirements
- Audit-ready reports for regulatory examinations

---

## Regulatory Alignment

### NIST AI Risk Management Framework (AI RMF)

MLTrack directly supports the NIST AI RMF core functions:

| NIST AI RMF Function | MLTrack Feature | How It Helps |
|---------------------|-----------------|--------------|
| **GOVERN 1.1** - Legal/regulatory requirements | Risk tier classification | Maps models to review frequencies based on regulatory expectations |
| **GOVERN 1.5** - Ongoing monitoring | `mltrack validate --all` | Automated compliance checking across entire inventory |
| **GOVERN 4.1** - Organizational practices | Dashboard & reports | Centralized visibility into AI deployment landscape |
| **MAP 1.1** - Intended purpose documented | Use case field | Captures business context for each model |
| **MAP 1.5** - Risk assessment | Risk tier + validation rules | Identifies high-risk deployments requiring closer oversight |
| **MEASURE 2.2** - Evaluation documented | Review tracking | Maintains audit trail of periodic assessments |
| **MANAGE 1.1** - Risk response | Status lifecycle | Track deprecated/decommissioned models |
| **MANAGE 2.3** - Risk monitoring | Overdue review alerts | Proactive notification of governance gaps |

### Federal Reserve SR 11-7 (Model Risk Management)

SR 11-7 requires banks to maintain "a comprehensive set of models in use across the organization." MLTrack implements key requirements:

| SR 11-7 Requirement | MLTrack Implementation |
|--------------------|------------------------|
| Model inventory | Full model registry with metadata |
| Ownership documentation | Business owner + technical owner fields |
| Risk ranking | Four-tier risk classification system |
| Ongoing monitoring | Risk-based review cycles (30/90/180/365 days) |
| Validation documentation | Review notes and date tracking |
| Reporting to board/management | Compliance and risk reports |

### OCC 2011-12 & FDIC FIL-22-2017

These complementary guidelines emphasize model governance practices that MLTrack supports:

- **Effective challenge**: Documented review process with date tracking
- **Model inventory maintenance**: Centralized registry with search/filter capabilities
- **Third-party model risk**: Vendor tracking distinguishes in-house vs. external models
- **Model lifecycle management**: Status field tracks active → deprecated → decommissioned

---

## Why Financial Services Needs This

### The AI Governance Challenge

Financial services firms face unique challenges with AI governance:

1. **Volume**: Large banks may deploy hundreds of AI/ML models across business lines
2. **Velocity**: New models are deployed weekly; existing models are updated constantly
3. **Variety**: Models range from simple classifiers to complex LLM applications
4. **Scrutiny**: Regulators examine AI use with increasing rigor

### Current State at Most Firms

- Model inventories live in Excel spreadsheets (if they exist at all)
- Review schedules are tracked manually or forgotten entirely
- No automated compliance checking
- Audit preparation requires weeks of manual data gathering
- No single view of AI risk concentration

### How MLTrack Helps

| Pain Point | MLTrack Solution |
|------------|------------------|
| "We don't know what models we have" | Centralized inventory with search |
| "Reviews fall through the cracks" | Automated scheduling + overdue alerts |
| "Audit prep takes weeks" | One-command report generation |
| "No visibility into risk concentration" | Dashboard with risk distribution |
| "Spreadsheets are error-prone" | Validated data entry + imports |

---

## Who This Is For

**Model risk teams** at banks and financial institutions who need to move from spreadsheet-based model inventories to auditable, automated governance — without replacing their existing ML infrastructure.

**ML platform engineers** who want a lightweight compliance gate in their CI/CD pipelines, not a heavyweight GRC platform.

**AI risk managers** preparing for SR 11-7 examinations who need defensible evidence that models were reviewed, when, by whom, and that nothing changed after the fact.

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
| **Defensible Audit Trail** | Structured, immutable review records with SHA-256 model state hashes for tamper evidence |
| **OSCAL Export** | Generate NIST OSCAL 1.1.2 Assessment Results documents for regulatory submission |
| **Interactive Dashboard** | Real-time terminal dashboard with filtering and auto-refresh |
| **Audit Reports** | Generate compliance, inventory, and risk reports (terminal, CSV, JSON, OSCAL) |
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
| `mltrack check <name>` | CI/CD compliance gate (exit 0/1) | `mltrack check fraud-detector --json` |
| `mltrack validate` | Validate compliance | `mltrack validate --all` |
| `mltrack reviewed <name>` | Record a review with audit trail | `mltrack reviewed claude-sonnet-4 -d today --outcome passed --reviewer "Jane Smith"` |
| `mltrack dashboard` | View dashboard | `mltrack dashboard --watch` |

### Reports

| Command | Description | Example |
|---------|-------------|---------|
| `mltrack report compliance` | Compliance status | `mltrack report compliance -f json -o report.json` |
| `mltrack report compliance` | OSCAL Assessment Results | `mltrack report compliance -f oscal -o assessment-results.json` |
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
mltrack reviewed "gpt-4-turbo" \
  --date 2025-01-22 \
  --outcome passed \
  --reviewer "Jane Smith (Model Risk)" \
  --notes "Quarterly security review completed. No material issues."

# Output:
# ┌────────────── ✓ Review Recorded ──────────────┐
# │ Model          gpt-4-turbo                    │
# │ Risk Tier      CRITICAL                       │
# │ Review Cycle   30 days                        │
# │ Outcome        PASSED                         │
# │ Reviewer       Jane Smith (Model Risk)        │
# │                                               │
# │ Last Review (was)   2024-12-20               │
# │ Last Review (now)   2025-01-22               │
# │                                               │
# │ Next Review (was)   2025-01-19 (3 days overdue)│
# │ Next Review (now)   2025-02-21 (in 30 days)  │
# └───────────────────────────────────────────────┘
#
# Review note: Quarterly security review completed. No material issues.
# Review record written to audit trail.
```

Each review creates an immutable record in the `model_reviews` table, including a SHA-256 hash of the model's definition at review time. This allows auditors to verify the model hasn't been altered after a review was recorded.

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

### ModelReview Schema (Audit Trail)

Each call to `mltrack reviewed` creates one immutable record:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique review record identifier |
| `model_id` | FK | Reference to reviewed model |
| `model_name` | string | Model name (denormalized for audit readability) |
| `reviewed_at` | date | Date the review took place |
| `reviewer` | string | Who performed the review (optional) |
| `outcome` | enum | `passed`, `warning`, or `failed` |
| `notes` | text | Review observations (optional) |
| `model_state_hash` | SHA-256 | Hash of model definition at review time — tamper evidence |
| `created_at` | datetime | When this record was inserted (UTC, immutable) |

The `model_state_hash` covers: model_name, vendor, risk_tier, use_case, business_owner, technical_owner, deployment_date, model_version, deployment_environment, api_endpoint, data_classification, status.

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

MLTrack includes a comprehensive test suite with 566 tests covering all functionality.

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
| Reports | 42 | Compliance, inventory, risk, OSCAL reports |
| Check Command (CI/CD Gate) | 21 | Exit codes, JSON output, silent mode, risk filtering |
| Registry Discovery | 23 | Adapter ABC, mock adapter, untracked model detection |
| Model Review / Audit Trail | 28 | Review records, state hashing, audit trail integrity |
| Integration Workflows | 14 | End-to-end workflow testing |
| Performance | 6 | Pagination, batch operations |

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
│   │   ├── check_command.py    # mltrack check (CI/CD gate)
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
│   │   ├── review_storage.py  # Audit trail operations
│   │   ├── config.py          # Configuration
│   │   └── exceptions.py      # Custom exceptions
│   ├── models/                 # Data models
│   │   ├── ai_model.py        # AIModel SQLAlchemy model
│   │   └── model_review.py    # ModelReview audit trail model
│   ├── adapters/               # Registry platform adapters
│   │   └── mock_adapter.py    # Mock adapter for testing/demos
│   └── display/               # Output formatting
│       └── formatters.py      # Rich formatting helpers
├── tests/                      # Test suite (566 tests)
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

MLTrack is built in tiers, each adding regulatory value on top of the last.

### Done: Defensible Audit Trail

The foundation — every review creates an immutable, hash-verified record.

- [x] `ModelReview` table with SHA-256 model state hashes (tamper evidence)
- [x] `mltrack reviewed` writes structured audit records, not free-text notes
- [x] OSCAL 1.1.2 Assessment Results export (`mltrack report compliance -f oscal`)

**Why it matters:** Examiners ask "prove this model was reviewed and unchanged since." This tier answers that question with cryptographic evidence.

### Done: CI/CD Compliance Gate

- [x] `mltrack check <model-name>` — exit code 0 (compliant) or 1 (fail) for pipeline integration
- [x] `mltrack check --all` / `--risk <tier>` — inventory-wide or tier-filtered checks
- [x] `--json` structured output for pipeline parsing, `--verbose` for human-readable details
- [x] Silent by default — no stdout noise in CI logs, just the exit code

**Why it matters:** Shifts compliance from periodic audits to continuous enforcement. Every deploy can include a governance gate.

### Next: Registry Discovery

MLTrack becomes a governance overlay on your existing ML infrastructure — not a duplicate registry.

- [ ] `RegistryAdapter` interface with swappable backends (MLflow first, then SageMaker, Azure ML, Vertex)
- [ ] `mltrack discover --source mlflow` — surface untracked models before examiners find them

**Why it matters:** The biggest governance risk isn't a poorly reviewed model — it's a model nobody knows about. Discovery closes that gap.

### Future: Examination Evidence Package

- [ ] `mltrack package --model <name> --framework sr117 --output exam-package/` — generate examiner-ready artifact bundles
- [ ] Pre-built templates for SR 11-7, OCC 2011-12, and NIST AI RMF examination workflows

**Why it matters:** Audit preparation currently takes weeks of manual document assembly. This tier automates the packaging. The real moat here is examiner-facing workflow knowledge — what artifacts examiners actually ask for, in what order, with what context. Building this right requires practitioner input from model risk officers who have run these exams.

### On the Horizon: Model Cards, System Cards & Agent Cards

As AI transparency documentation matures, structured cards are becoming the standard way to describe what a model is, how it behaves, and what risks it carries:

- [ ] **Model Cards** — standardized documentation of model purpose, performance, limitations, and ethical considerations ([Mitchell et al., 2019](https://arxiv.org/abs/1908.09203))
- [ ] **System Cards** — document the full AI system: model + data pipeline + deployment context + safeguards
- [ ] **Agent Cards** — emerging format for agentic AI: autonomy level, tool access, decision boundaries, human oversight requirements

**Why it matters:** Governance tools that only track *metadata about* models will fall behind. The next layer is generating, validating, and versioning the transparency documentation that regulators and stakeholders increasingly expect. MLTrack's audit trail and model inventory are the natural foundation for card generation — the data is already there, it just needs the output format.

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
