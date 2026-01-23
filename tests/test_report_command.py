"""Tests for the mltrack report CLI commands."""

import csv
import json
import pytest
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from typer.testing import CliRunner

from mltrack.cli.main import app
from mltrack.core.database import init_db
from mltrack.core.storage import create_model, update_model

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("mltrack.core.database.DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr("mltrack.core.storage.init_db", lambda p=None: init_db(db_path))
    init_db(db_path)
    yield db_path


@pytest.fixture
def sample_models(clean_db):
    """Create a set of sample models for testing."""
    models = []

    # Critical risk model in production
    models.append(create_model({
        "model_name": "fraud-detection-v1",
        "vendor": "Anthropic",
        "risk_tier": "critical",
        "use_case": "Fraud detection",
        "business_owner": "Risk Team",
        "technical_owner": "ML Team",
        "deployment_date": date.today() - timedelta(days=60),
        "deployment_environment": "prod",
        "data_classification": "confidential",
        "status": "active",
    }))

    # High risk model with overdue review
    models.append(create_model({
        "model_name": "credit-scoring-v2",
        "vendor": "OpenAI",
        "risk_tier": "high",
        "use_case": "Credit scoring",
        "business_owner": "Lending Team",
        "technical_owner": "ML Team",
        "deployment_date": date.today() - timedelta(days=120),
        "deployment_environment": "prod",
        "status": "active",
    }))

    # Medium risk model
    models.append(create_model({
        "model_name": "customer-segmentation",
        "vendor": "Anthropic",
        "risk_tier": "medium",
        "use_case": "Customer segmentation",
        "business_owner": "Marketing",
        "technical_owner": "Data Team",
        "deployment_date": date.today() - timedelta(days=30),
        "deployment_environment": "staging",
        "status": "active",
    }))

    # Low risk model
    models.append(create_model({
        "model_name": "email-classifier",
        "vendor": "Google",
        "risk_tier": "low",
        "use_case": "Email classification",
        "business_owner": "Support Team",
        "technical_owner": "Engineering",
        "deployment_date": date.today() - timedelta(days=10),
        "status": "active",
    }))

    # Decommissioned model
    models.append(create_model({
        "model_name": "legacy-model",
        "vendor": "Internal",
        "risk_tier": "low",
        "use_case": "Legacy use case",
        "business_owner": "Legacy Team",
        "technical_owner": "Legacy Tech",
        "deployment_date": date.today() - timedelta(days=365),
        "status": "decommissioned",
    }))

    return models


class TestReportCommandBasics:
    """Basic tests for report command."""

    def test_report_help(self):
        """Test that --help shows usage information."""
        result = runner.invoke(app, ["report", "--help"])

        assert result.exit_code == 0
        assert "compliance" in result.output
        assert "inventory" in result.output
        assert "risk" in result.output

    def test_report_no_args_shows_help(self):
        """Test that report with no args shows help."""
        result = runner.invoke(app, ["report"])

        # no_args_is_help=True causes exit code 2 (usage error showing help)
        # This is expected typer behavior
        assert "compliance" in result.output or "Usage" in result.output

    def test_report_empty_inventory(self, clean_db):
        """Test report on empty inventory."""
        result = runner.invoke(app, ["report", "compliance"])

        assert result.exit_code == 0
        assert "No models" in result.output or "Empty" in result.output


class TestComplianceReport:
    """Tests for compliance report."""

    def test_compliance_terminal(self, sample_models):
        """Test compliance report in terminal format."""
        result = runner.invoke(app, ["report", "compliance"])

        assert result.exit_code == 0
        assert "Compliance Report" in result.output
        assert "Risk Tier Distribution" in result.output
        assert "Compliance Status" in result.output
        assert "Review Status" in result.output

    def test_compliance_shows_risk_counts(self, sample_models):
        """Test that compliance report shows risk tier counts."""
        result = runner.invoke(app, ["report", "compliance"])

        assert result.exit_code == 0
        assert "CRITICAL" in result.output
        assert "HIGH" in result.output
        assert "MEDIUM" in result.output
        assert "LOW" in result.output

    def test_compliance_shows_overdue(self, sample_models):
        """Test that compliance report shows overdue reviews."""
        result = runner.invoke(app, ["report", "compliance"])

        assert result.exit_code == 0
        # Should show overdue since models were created with past deployment dates
        assert "Overdue" in result.output

    def test_compliance_json_output(self, sample_models, tmp_path):
        """Test compliance report JSON output."""
        output_file = tmp_path / "compliance.json"

        result = runner.invoke(app, [
            "report", "compliance",
            "-f", "json",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0
        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)

        assert data["report_type"] == "compliance"
        assert "summary" in data
        assert "risk_distribution" in data
        assert "review_status" in data
        assert "violations" in data

    def test_compliance_csv_output(self, sample_models, tmp_path):
        """Test compliance report CSV output."""
        output_file = tmp_path / "compliance.csv"

        result = runner.invoke(app, [
            "report", "compliance",
            "-f", "csv",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0
        # CSV may be empty if no violations
        assert output_file.exists() or "No data" in result.output

    def test_compliance_requires_output_for_csv(self, sample_models):
        """Test that CSV format requires output file."""
        result = runner.invoke(app, ["report", "compliance", "-f", "csv"])

        assert result.exit_code == 1
        assert "Output file required" in result.output


class TestInventoryReport:
    """Tests for inventory report."""

    def test_inventory_terminal(self, sample_models):
        """Test inventory report in terminal format."""
        result = runner.invoke(app, ["report", "inventory"])

        assert result.exit_code == 0
        assert "Model Inventory Report" in result.output
        assert "Summary Statistics" in result.output
        assert "Models by Vendor" in result.output
        assert "Models by Risk Tier" in result.output

    def test_inventory_shows_status_counts(self, sample_models):
        """Test that inventory shows status counts."""
        result = runner.invoke(app, ["report", "inventory"])

        assert result.exit_code == 0
        assert "Active" in result.output
        assert "Decommissioned" in result.output

    def test_inventory_shows_model_names(self, sample_models):
        """Test that inventory shows model names."""
        result = runner.invoke(app, ["report", "inventory"])

        assert result.exit_code == 0
        assert "fraud-detection-v1" in result.output
        assert "credit-scoring-v2" in result.output
        assert "customer-segmentation" in result.output

    def test_inventory_shows_vendors(self, sample_models):
        """Test that inventory groups by vendor."""
        result = runner.invoke(app, ["report", "inventory"])

        assert result.exit_code == 0
        assert "Anthropic" in result.output
        assert "OpenAI" in result.output
        assert "Google" in result.output

    def test_inventory_json_output(self, sample_models, tmp_path):
        """Test inventory report JSON output."""
        output_file = tmp_path / "inventory.json"

        result = runner.invoke(app, [
            "report", "inventory",
            "-f", "json",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0
        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 5  # 5 sample models
        assert all("model_name" in item for item in data)
        assert all("vendor" in item for item in data)
        assert all("risk_tier" in item for item in data)

    def test_inventory_csv_output(self, sample_models, tmp_path):
        """Test inventory report CSV output."""
        output_file = tmp_path / "inventory.csv"

        result = runner.invoke(app, [
            "report", "inventory",
            "-f", "csv",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0
        assert output_file.exists()

        # Read and verify CSV content
        with open(output_file) as f:
            content = f.read()

        assert "model_name" in content
        assert "fraud-detection-v1" in content


class TestRiskReport:
    """Tests for risk report."""

    def test_risk_terminal(self, sample_models):
        """Test risk report in terminal format."""
        result = runner.invoke(app, ["report", "risk"])

        assert result.exit_code == 0
        assert "Risk Distribution Report" in result.output
        assert "Risk Tier Distribution" in result.output
        assert "Review Cycle" in result.output

    def test_risk_shows_tier_counts(self, sample_models):
        """Test that risk report shows tier counts."""
        result = runner.invoke(app, ["report", "risk"])

        assert result.exit_code == 0
        assert "CRITICAL" in result.output
        assert "HIGH" in result.output
        assert "MEDIUM" in result.output
        assert "LOW" in result.output

    def test_risk_shows_review_cycles(self, sample_models):
        """Test that risk report shows review cycles."""
        result = runner.invoke(app, ["report", "risk"])

        assert result.exit_code == 0
        assert "30 days" in result.output  # Critical
        assert "90 days" in result.output  # High
        assert "180 days" in result.output  # Medium
        assert "365 days" in result.output  # Low

    def test_risk_shows_high_risk_production(self, sample_models):
        """Test that risk report shows high-risk production models."""
        result = runner.invoke(app, ["report", "risk"])

        assert result.exit_code == 0
        assert "High-Risk Models in Production" in result.output
        assert "fraud-detection-v1" in result.output  # Critical in prod

    def test_risk_shows_vendor_concentration(self, sample_models):
        """Test that risk report shows vendor concentration."""
        result = runner.invoke(app, ["report", "risk"])

        assert result.exit_code == 0
        assert "Risk Concentration by Vendor" in result.output
        assert "Anthropic" in result.output

    def test_risk_json_output(self, sample_models, tmp_path):
        """Test risk report JSON output."""
        output_file = tmp_path / "risk.json"

        result = runner.invoke(app, [
            "report", "risk",
            "-f", "json",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0
        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)

        assert data["report_type"] == "risk"
        assert "risk_distribution" in data
        assert "high_risk_production" in data
        assert "vendor_risk_concentration" in data

    def test_risk_csv_output(self, sample_models, tmp_path):
        """Test risk report CSV output."""
        output_file = tmp_path / "risk.csv"

        result = runner.invoke(app, [
            "report", "risk",
            "-f", "csv",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0
        assert output_file.exists()

        with open(output_file) as f:
            content = f.read()

        assert "vendor" in content
        assert "critical" in content
        assert "high" in content


class TestReportOutputFormats:
    """Tests for report output format handling."""

    def test_json_requires_output_file(self, sample_models):
        """Test that JSON format requires output file."""
        result = runner.invoke(app, ["report", "inventory", "-f", "json"])

        assert result.exit_code == 1
        assert "Output file required" in result.output

    def test_csv_requires_output_file(self, sample_models):
        """Test that CSV format requires output file."""
        result = runner.invoke(app, ["report", "risk", "-f", "csv"])

        assert result.exit_code == 1
        assert "Output file required" in result.output

    def test_invalid_format(self, sample_models):
        """Test invalid format."""
        result = runner.invoke(app, ["report", "compliance", "-f", "pdf"])

        assert result.exit_code == 1
        assert "Invalid format" in result.output

    def test_terminal_ignores_output_file(self, sample_models, tmp_path):
        """Test that terminal format ignores output file if provided."""
        output_file = tmp_path / "output.txt"

        result = runner.invoke(app, [
            "report", "compliance",
            "-f", "terminal",
            "-o", str(output_file),
        ])

        # Should succeed and show in terminal
        assert result.exit_code == 0
        assert "Compliance Report" in result.output


class TestReportDataIntegrity:
    """Tests for report data integrity."""

    def test_inventory_includes_all_models(self, sample_models, tmp_path):
        """Test that inventory includes all models."""
        output_file = tmp_path / "inventory.json"

        result = runner.invoke(app, [
            "report", "inventory",
            "-f", "json",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0

        with open(output_file) as f:
            data = json.load(f)

        assert len(data) == 5

    def test_risk_excludes_decommissioned(self, sample_models, tmp_path):
        """Test that risk report excludes decommissioned models from counts."""
        output_file = tmp_path / "risk.json"

        result = runner.invoke(app, [
            "report", "risk",
            "-f", "json",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0

        with open(output_file) as f:
            data = json.load(f)

        # Sum of risk distribution should be 4 (excluding decommissioned)
        total_in_distribution = sum(data["risk_distribution"].values())
        assert total_in_distribution == 4


class TestComplianceScenarios:
    """Tests for specific compliance scenarios."""

    @pytest.fixture
    def compliant_models(self, clean_db):
        """Create models that are fully compliant."""
        models = []

        # Model with recent review (within cycle)
        model1 = create_model({
            "model_name": "compliant-model-1",
            "vendor": "Anthropic",
            "risk_tier": "high",  # 90-day cycle
            "use_case": "Compliant testing",
            "business_owner": "Owner A",
            "technical_owner": "Tech A",
            "deployment_date": date.today() - timedelta(days=30),
            "deployment_environment": "prod",
            "data_classification": "confidential",  # Required for prod
            "status": "active",
        })
        # Mark as reviewed recently
        update_model(model1.id, {"last_review_date": date.today() - timedelta(days=10)})
        models.append(model1)

        # Another compliant model
        model2 = create_model({
            "model_name": "compliant-model-2",
            "vendor": "OpenAI",
            "risk_tier": "medium",  # 180-day cycle
            "use_case": "Another compliant model",
            "business_owner": "Owner B",
            "technical_owner": "Tech B",
            "deployment_date": date.today() - timedelta(days=60),
            "deployment_environment": "staging",  # Non-prod doesn't need classification
            "status": "active",
        })
        update_model(model2.id, {"last_review_date": date.today() - timedelta(days=30)})
        models.append(model2)

        return models

    def test_compliance_all_compliant_shows_100_percent(self, compliant_models, tmp_path):
        """Test compliance report with all-compliant models shows 100%."""
        output_file = tmp_path / "compliance.json"

        result = runner.invoke(app, [
            "report", "compliance",
            "-f", "json",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0

        with open(output_file) as f:
            data = json.load(f)

        assert data["summary"]["compliance_rate"] == 100.0
        assert data["summary"]["compliant"] == 2
        assert data["summary"]["non_compliant"] == 0
        assert len(data["violations"]) == 0

    def test_compliance_all_compliant_terminal_output(self, compliant_models):
        """Test terminal output shows success for all-compliant models."""
        result = runner.invoke(app, ["report", "compliance"])

        assert result.exit_code == 0
        assert "100" in result.output  # 100% compliance rate
        assert "Non-Compliant Models" not in result.output  # No violations section

    @pytest.fixture
    def models_with_violations(self, clean_db):
        """Create models with specific violations."""
        models = []

        # Model missing data classification for prod (violation)
        models.append(create_model({
            "model_name": "missing-classification",
            "vendor": "Test",
            "risk_tier": "high",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today() - timedelta(days=100),  # Overdue review
            "deployment_environment": "prod",
            # Missing data_classification - violation for prod
            "status": "active",
        }))

        # Model with overdue review
        models.append(create_model({
            "model_name": "overdue-review",
            "vendor": "Test",
            "risk_tier": "critical",  # 30-day cycle
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today() - timedelta(days=60),  # Way overdue
            "deployment_environment": "staging",
            "status": "active",
        }))

        return models

    def test_compliance_with_violations_lists_issues(self, models_with_violations, tmp_path):
        """Test compliance report correctly lists violations."""
        output_file = tmp_path / "compliance.json"

        result = runner.invoke(app, [
            "report", "compliance",
            "-f", "json",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0

        with open(output_file) as f:
            data = json.load(f)

        assert data["summary"]["non_compliant"] == 2
        assert data["summary"]["compliance_rate"] == 0.0
        assert len(data["violations"]) == 2

        # Verify violation details
        violation_models = {v["model_name"] for v in data["violations"]}
        assert "missing-classification" in violation_models
        assert "overdue-review" in violation_models

    def test_compliance_violations_terminal_output(self, models_with_violations):
        """Test terminal output shows violations clearly."""
        result = runner.invoke(app, ["report", "compliance"])

        assert result.exit_code == 0
        assert "Non-Compliant Models" in result.output
        assert "missing-classification" in result.output
        assert "overdue-review" in result.output


class TestReportExportFormats:
    """Tests for export format validity."""

    def test_inventory_csv_valid_format(self, sample_models, tmp_path):
        """Test inventory CSV is valid CSV format with correct headers."""
        output_file = tmp_path / "inventory.csv"

        result = runner.invoke(app, [
            "report", "inventory",
            "-f", "csv",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0

        with open(output_file, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Verify correct number of rows
        assert len(rows) == 5

        # Verify required columns exist
        required_columns = [
            "id", "model_name", "vendor", "risk_tier", "status",
            "use_case", "business_owner", "technical_owner",
            "deployment_date", "next_review_date",
        ]
        for col in required_columns:
            assert col in reader.fieldnames, f"Missing column: {col}"

        # Verify data integrity
        model_names = {row["model_name"] for row in rows}
        assert "fraud-detection-v1" in model_names
        assert "credit-scoring-v2" in model_names

    def test_risk_json_valid_schema(self, sample_models, tmp_path):
        """Test risk report JSON has valid schema structure."""
        output_file = tmp_path / "risk.json"

        result = runner.invoke(app, [
            "report", "risk",
            "-f", "json",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0

        with open(output_file) as f:
            data = json.load(f)

        # Validate top-level structure
        assert "report_type" in data
        assert data["report_type"] == "risk"
        assert "generated_date" in data
        assert "risk_distribution" in data
        assert "high_risk_production" in data
        assert "models_without_recent_review" in data
        assert "vendor_risk_concentration" in data

        # Validate risk_distribution structure
        risk_dist = data["risk_distribution"]
        assert isinstance(risk_dist, dict)
        for tier in ["critical", "high", "medium", "low"]:
            if tier in risk_dist:
                assert isinstance(risk_dist[tier], int)

        # Validate high_risk_production array structure
        for model in data["high_risk_production"]:
            assert "model_name" in model
            assert "model_id" in model
            assert "risk_tier" in model
            assert "vendor" in model

        # Validate vendor_risk_concentration structure
        for vendor, risks in data["vendor_risk_concentration"].items():
            assert isinstance(vendor, str)
            assert isinstance(risks, dict)


class TestReportCalculations:
    """Tests for correct calculation of percentages and counts."""

    @pytest.fixture
    def known_distribution_models(self, clean_db):
        """Create models with known distribution for calculation testing."""
        # Create exactly: 2 critical, 3 high, 4 medium, 1 low = 10 active models
        models = []

        for i in range(2):
            models.append(create_model({
                "model_name": f"critical-{i}",
                "vendor": "VendorA",
                "risk_tier": "critical",
                "use_case": "Test",
                "business_owner": "Owner",
                "technical_owner": "Tech",
                "deployment_date": date.today(),
                "status": "active",
            }))

        for i in range(3):
            models.append(create_model({
                "model_name": f"high-{i}",
                "vendor": "VendorB",
                "risk_tier": "high",
                "use_case": "Test",
                "business_owner": "Owner",
                "technical_owner": "Tech",
                "deployment_date": date.today(),
                "status": "active",
            }))

        for i in range(4):
            models.append(create_model({
                "model_name": f"medium-{i}",
                "vendor": "VendorA",
                "risk_tier": "medium",
                "use_case": "Test",
                "business_owner": "Owner",
                "technical_owner": "Tech",
                "deployment_date": date.today(),
                "status": "active",
            }))

        models.append(create_model({
            "model_name": "low-0",
            "vendor": "VendorC",
            "risk_tier": "low",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today(),
            "status": "active",
        }))

        return models

    def test_risk_distribution_counts_correct(self, known_distribution_models, tmp_path):
        """Test risk distribution counts are calculated correctly."""
        output_file = tmp_path / "risk.json"

        result = runner.invoke(app, [
            "report", "risk",
            "-f", "json",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0

        with open(output_file) as f:
            data = json.load(f)

        # Verify exact counts
        assert data["risk_distribution"]["critical"] == 2
        assert data["risk_distribution"]["high"] == 3
        assert data["risk_distribution"]["medium"] == 4
        assert data["risk_distribution"]["low"] == 1

        # Verify total
        total = sum(data["risk_distribution"].values())
        assert total == 10

    def test_vendor_concentration_counts_correct(self, known_distribution_models, tmp_path):
        """Test vendor concentration is calculated correctly."""
        output_file = tmp_path / "risk.json"

        result = runner.invoke(app, [
            "report", "risk",
            "-f", "json",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0

        with open(output_file) as f:
            data = json.load(f)

        vendor_conc = data["vendor_risk_concentration"]

        # VendorA: 2 critical + 4 medium = 6 total
        assert vendor_conc["VendorA"]["critical"] == 2
        assert vendor_conc["VendorA"]["medium"] == 4

        # VendorB: 3 high
        assert vendor_conc["VendorB"]["high"] == 3

        # VendorC: 1 low
        assert vendor_conc["VendorC"]["low"] == 1

    def test_compliance_rate_percentage_correct(self, clean_db, tmp_path):
        """Test compliance rate percentage is calculated correctly."""
        # Create 3 compliant, 1 non-compliant = 75% compliance
        for i in range(3):
            model = create_model({
                "model_name": f"compliant-{i}",
                "vendor": "Test",
                "risk_tier": "low",
                "use_case": "Test",
                "business_owner": "Owner",
                "technical_owner": "Tech",
                "deployment_date": date.today(),
                "status": "active",
            })
            update_model(model.id, {"last_review_date": date.today()})

        # Non-compliant: overdue critical model
        create_model({
            "model_name": "non-compliant",
            "vendor": "Test",
            "risk_tier": "critical",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today() - timedelta(days=60),  # Overdue
            "status": "active",
        })

        output_file = tmp_path / "compliance.json"

        result = runner.invoke(app, [
            "report", "compliance",
            "-f", "json",
            "-o", str(output_file),
        ])

        assert result.exit_code == 0

        with open(output_file) as f:
            data = json.load(f)

        assert data["summary"]["total_models"] == 4
        assert data["summary"]["compliant"] == 3
        assert data["summary"]["non_compliant"] == 1
        assert data["summary"]["compliance_rate"] == 75.0


class TestReportEmptyStates:
    """Tests for empty state handling across all report types."""

    def test_compliance_empty_shows_message(self, clean_db):
        """Test compliance report handles empty inventory."""
        result = runner.invoke(app, ["report", "compliance"])

        assert result.exit_code == 0
        assert "No models" in result.output or "Empty" in result.output

    def test_inventory_empty_shows_message(self, clean_db):
        """Test inventory report handles empty inventory."""
        result = runner.invoke(app, ["report", "inventory"])

        assert result.exit_code == 0
        assert "No models" in result.output or "Empty" in result.output

    def test_risk_empty_shows_message(self, clean_db):
        """Test risk report handles empty inventory."""
        result = runner.invoke(app, ["report", "risk"])

        assert result.exit_code == 0
        assert "No models" in result.output or "Empty" in result.output
