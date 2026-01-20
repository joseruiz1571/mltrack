# MLTrack - Model Lineage Tracker

AI governance tool for tracking deployed models in financial services.

## Features

- Model inventory management (add, edit, list, show, delete)
- Required field validation (owner, risk tier, use case, deployment date)
- Compliance reporting (missing documentation, overdue reviews)
- Risk visualization dashboard

## Compliance Frameworks

MLTrack helps organizations comply with:

- **NIST AI RMF** - AI Risk Management Framework
- **ISO 42001** - AI Management System Standard
- **SR 11-7** - Federal Reserve Model Risk Management

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Show help
mltrack --help

# Model management
mltrack model add <name>
mltrack model list
mltrack model show <name>
mltrack model edit <name>
mltrack model delete <name>

# Compliance reports
mltrack report overdue
mltrack report gaps
mltrack report summary

# Dashboard
mltrack dashboard
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=mltrack
```

## License

MIT
