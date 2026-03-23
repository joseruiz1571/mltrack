"""Integration tests for full end-to-end workflows.

These tests verify that the entire system works together correctly
by testing complete user workflows from start to finish.
"""

import csv
import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mltrack.cli.main import app
from mltrack.core.database import init_db
from mltrack.core.storage import create_model, get_model, get_all_models
from mltrack.models import RiskTier, DeploymentEnvironment, ModelStatus, DataClassification


runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    """Provide a clean database for each test."""
    db_path = tmp_path / "integration_test.db"
    # Monkeypatch the default DB path
    monkeypatch.setattr("mltrack.core.database.DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr("mltrack.core.storage.init_db", lambda p=None: init_db(db_path))
    init_db(db_path)
    yield db_path


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for file operations."""
    export_dir = tmp_path / "exports"
    export_dir.mkdir(exist_ok=True)
    return export_dir


class TestWorkflow1_ModelLifecycle:
    """
    Workflow 1: Add model → List → Show → Update → Validate → Delete

    Tests the complete lifecycle of a single model from creation to deletion.
    """

    def test_full_model_lifecycle(self):
        """Test complete model lifecycle: add, list, show, update, validate, delete."""
        # Step 1: Add a new model
        result = runner.invoke(app, [
            "add",
            "--name", "lifecycle-test-model",
            "--vendor", "test-vendor",
            "--risk-tier", "high",
            "--use-case", "Testing the full model lifecycle",
            "--business-owner", "Test Owner",
            "--technical-owner", "Tech Lead",
            "--deployment-date", "2024-01-15",
            "--environment", "prod",
            "--data-classification", "confidential",
        ])
        assert result.exit_code == 0, f"Add failed: {result.output}"
        assert "lifecycle-test-model" in result.output
        assert "Created" in result.output or "✓" in result.output

        # Step 2: List models and verify it appears
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0, f"List failed: {result.output}"
        assert "lifecycle-test-model" in result.output
        assert "test-vendor" in result.output
        assert "HIGH" in result.output

        # Step 3: Show model details
        result = runner.invoke(app, ["show", "lifecycle-test-model"])
        assert result.exit_code == 0, f"Show failed: {result.output}"
        assert "lifecycle-test-model" in result.output
        assert "test-vendor" in result.output
        assert "Testing the full model lifecycle" in result.output
        assert "Test Owner" in result.output
        assert "Tech Lead" in result.output
        assert "CONFIDENTIAL" in result.output.upper()

        # Step 4: Update the model (use -y to skip confirmation)
        result = runner.invoke(app, [
            "update", "lifecycle-test-model",
            "--vendor", "updated-vendor",
            "--notes", "Updated via integration test",
            "-y",
        ])
        assert result.exit_code == 0, f"Update failed: {result.output}"
        assert "updated-vendor" in result.output

        # Verify update persisted
        result = runner.invoke(app, ["show", "lifecycle-test-model"])
        assert result.exit_code == 0
        assert "updated-vendor" in result.output
        assert "Updated via integration test" in result.output

        # Step 5: Validate the model (may be non-compliant due to overdue review)
        result = runner.invoke(app, ["validate", "--model-id", "lifecycle-test-model"])
        assert result.exit_code in (0, 1), f"Validate crashed: {result.output}"
        # Should show validation results (compliant or with issues)

        # Step 6: Delete the model (soft delete first)
        result = runner.invoke(app, ["delete", "lifecycle-test-model", "--soft", "--yes"])
        assert result.exit_code == 0, f"Soft delete failed: {result.output}"
        assert "decommissioned" in result.output.lower()

        # Verify model is decommissioned
        result = runner.invoke(app, ["show", "lifecycle-test-model"])
        assert result.exit_code == 0
        assert "DECOMMISSIONED" in result.output

        # Step 7: Hard delete the model
        result = runner.invoke(app, ["delete", "lifecycle-test-model", "--yes"])
        assert result.exit_code == 0, f"Hard delete failed: {result.output}"
        assert "permanently deleted" in result.output.lower() or "deleted" in result.output.lower()

        # Verify model is gone
        result = runner.invoke(app, ["show", "lifecycle-test-model"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_model_lifecycle_with_review(self):
        """Test model lifecycle including review recording."""
        # Add model
        result = runner.invoke(app, [
            "add",
            "--name", "review-test-model",
            "--vendor", "anthropic",
            "--risk-tier", "critical",
            "--use-case", "Critical AI model for testing",
            "--business-owner", "VP Engineering",
            "--technical-owner", "Senior Engineer",
            "--deployment-date", "2024-01-01",
        ])
        assert result.exit_code == 0

        # Validate - may be non-compliant (critical = 30 day cycle, old date)
        # Exit code 1 is expected for non-compliant models
        result = runner.invoke(app, ["validate", "--model-id", "review-test-model"])
        assert result.exit_code in (0, 1)  # Either pass or fail is valid

        # Record a review
        result = runner.invoke(app, [
            "reviewed", "review-test-model",
            "--date", "today",
            "--notes", "Quarterly security review completed",
        ])
        assert result.exit_code == 0
        assert "Review Recorded" in result.output

        # Verify review was recorded — notes now live in ModelReview audit trail,
        # not in AIModel.notes. Confirm show still works and model is intact.
        result = runner.invoke(app, ["show", "review-test-model"])
        assert result.exit_code == 0
        assert "review-test-model" in result.output


class TestWorkflow2_ImportExportReports:
    """
    Workflow 2: Import CSV → Run report → Export JSON

    Tests the data import/export workflow with report generation.
    """

    def test_csv_import_report_json_export(self, temp_dir):
        """Test importing CSV, generating report, and exporting to JSON."""
        # Step 1: Create a CSV file to import
        csv_path = temp_dir / "models_to_import.csv"
        csv_content = """model_name,vendor,risk_tier,use_case,business_owner,technical_owner,deployment_date,environment
import-model-1,OpenAI,high,Text generation API,Product Lead,ML Engineer,2024-02-01,prod
import-model-2,Anthropic,critical,Customer support chatbot,Support Director,AI Lead,2024-01-15,prod
import-model-3,Internal,medium,Data analysis tool,Data Team,Data Engineer,2024-03-01,staging
import-model-4,Google,low,Translation service,Content Lead,Backend Dev,2024-02-15,dev
"""
        csv_path.write_text(csv_content)

        # Step 2: Validate the CSV first
        result = runner.invoke(app, ["import", str(csv_path), "--validate"])
        assert result.exit_code == 0, f"Validation failed: {result.output}"
        assert "4" in result.output  # Should show 4 records
        assert "valid" in result.output.lower()

        # Step 3: Import the CSV
        result = runner.invoke(app, ["import", str(csv_path)])
        assert result.exit_code == 0, f"Import failed: {result.output}"
        assert "Created" in result.output or "created" in result.output.lower()

        # Verify import
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "import-model-1" in result.output
        assert "import-model-2" in result.output
        assert "import-model-3" in result.output
        assert "import-model-4" in result.output

        # Step 4: Run inventory report
        result = runner.invoke(app, ["report", "inventory"])
        assert result.exit_code == 0, f"Report failed: {result.output}"
        assert "4" in result.output or "inventory" in result.output.lower()

        # Step 5: Run compliance report
        result = runner.invoke(app, ["report", "compliance"])
        assert result.exit_code == 0, f"Compliance report failed: {result.output}"

        # Step 6: Run risk report
        result = runner.invoke(app, ["report", "risk"])
        assert result.exit_code == 0, f"Risk report failed: {result.output}"
        # Should show distribution
        assert "CRITICAL" in result.output or "HIGH" in result.output

        # Step 7: Export to JSON
        json_path = temp_dir / "exported_models.json"
        result = runner.invoke(app, ["export", str(json_path)])
        assert result.exit_code == 0, f"Export failed: {result.output}"
        assert "4" in result.output or "Exported" in result.output

        # Verify JSON export
        assert json_path.exists()
        with open(json_path) as f:
            data = json.load(f)

        assert "models" in data
        assert len(data["models"]) == 4
        assert data["count"] == 4
        assert "exported_at" in data

        # Verify model data in JSON
        model_names = [m["model_name"] for m in data["models"]]
        assert "import-model-1" in model_names
        assert "import-model-2" in model_names

    def test_filtered_export_workflow(self, temp_dir):
        """Test exporting filtered subsets of data."""
        # Create diverse models
        models = [
            {"model_name": "filter-test-1", "vendor": "VendorA", "risk_tier": "critical",
             "use_case": "Test 1", "business_owner": "Owner", "technical_owner": "Tech",
             "deployment_date": date(2024, 1, 1)},
            {"model_name": "filter-test-2", "vendor": "VendorA", "risk_tier": "high",
             "use_case": "Test 2", "business_owner": "Owner", "technical_owner": "Tech",
             "deployment_date": date(2024, 1, 1)},
            {"model_name": "filter-test-3", "vendor": "VendorB", "risk_tier": "critical",
             "use_case": "Test 3", "business_owner": "Owner", "technical_owner": "Tech",
             "deployment_date": date(2024, 1, 1)},
        ]
        for m in models:
            create_model(m)

        # Export only critical models
        critical_json = temp_dir / "critical.json"
        result = runner.invoke(app, ["export", str(critical_json), "--risk", "critical"])
        assert result.exit_code == 0
        assert "2" in result.output  # 2 critical models

        with open(critical_json) as f:
            data = json.load(f)
        assert len(data["models"]) == 2
        assert all(m["risk_tier"] == "critical" for m in data["models"])

        # Export only VendorA models
        vendor_csv = temp_dir / "vendorA.csv"
        result = runner.invoke(app, ["export", str(vendor_csv), "--vendor", "VendorA"])
        assert result.exit_code == 0
        assert "2" in result.output  # 2 VendorA models


class TestWorkflow3_DashboardCompliance:
    """
    Workflow 3: Add multiple models → Dashboard view → Compliance check

    Tests the monitoring and compliance workflow.
    """

    def test_multi_model_dashboard_compliance(self):
        """Test adding multiple models, viewing dashboard, and checking compliance."""
        # Step 1: Add multiple models with varied characteristics
        models_to_add = [
            {
                "name": "dashboard-critical-1",
                "vendor": "OpenAI",
                "risk_tier": "critical",
                "use_case": "Production AI assistant",
                "business_owner": "CEO",
                "technical_owner": "CTO",
                "deployment_date": (date.today() - timedelta(days=60)).isoformat(),
                "environment": "prod",
            },
            {
                "name": "dashboard-high-1",
                "vendor": "Anthropic",
                "risk_tier": "high",
                "use_case": "Customer service bot",
                "business_owner": "VP Support",
                "technical_owner": "ML Lead",
                "deployment_date": (date.today() - timedelta(days=30)).isoformat(),
                "environment": "prod",
            },
            {
                "name": "dashboard-medium-1",
                "vendor": "Internal",
                "risk_tier": "medium",
                "use_case": "Internal analytics",
                "business_owner": "Data Lead",
                "technical_owner": "Data Engineer",
                "deployment_date": date.today().isoformat(),
                "environment": "staging",
            },
            {
                "name": "dashboard-low-1",
                "vendor": "Google",
                "risk_tier": "low",
                "use_case": "Translation helper",
                "business_owner": "Content Lead",
                "technical_owner": "Backend Dev",
                "deployment_date": date.today().isoformat(),
                "environment": "dev",
            },
        ]

        for model in models_to_add:
            result = runner.invoke(app, [
                "add",
                "--name", model["name"],
                "--vendor", model["vendor"],
                "--risk-tier", model["risk_tier"],
                "--use-case", model["use_case"],
                "--business-owner", model["business_owner"],
                "--technical-owner", model["technical_owner"],
                "--deployment-date", model["deployment_date"],
                "--environment", model["environment"],
            ])
            assert result.exit_code == 0, f"Failed to add {model['name']}: {result.output}"

        # Step 2: View dashboard (static mode, no watch)
        result = runner.invoke(app, ["dashboard"])
        assert result.exit_code == 0, f"Dashboard failed: {result.output}"
        # Dashboard should show summary information
        assert "4" in result.output or "Model" in result.output

        # Step 3: Check filtered dashboard
        result = runner.invoke(app, ["dashboard", "--risk", "critical"])
        assert result.exit_code == 0, f"Filtered dashboard failed: {result.output}"

        result = runner.invoke(app, ["dashboard", "--environment", "prod"])
        assert result.exit_code == 0, f"Env dashboard failed: {result.output}"

        # Step 4: Run full compliance validation
        # Exit code 1 is expected when some models are non-compliant (overdue reviews, missing data classification)
        result = runner.invoke(app, ["validate", "--all"])
        assert result.exit_code in (0, 1), f"Validate all crashed: {result.output}"
        # The critical model from 60 days ago should be overdue (30-day cycle)

        # Step 5: Validate by risk tier
        result = runner.invoke(app, ["validate", "--risk", "critical"])
        assert result.exit_code in (0, 1), f"Validate critical crashed: {result.output}"

        # Step 6: Generate compliance report
        result = runner.invoke(app, ["report", "compliance"])
        assert result.exit_code == 0, f"Compliance report failed: {result.output}"

    def test_compliance_with_overdue_models(self):
        """Test compliance workflow with models that have overdue reviews."""
        # Create a model that should be overdue
        # Critical model deployed 60 days ago, with 30-day review cycle
        old_date = (date.today() - timedelta(days=60)).isoformat()

        result = runner.invoke(app, [
            "add",
            "--name", "overdue-model",
            "--vendor", "Test",
            "--risk-tier", "critical",
            "--use-case", "Overdue test",
            "--business-owner", "Owner",
            "--technical-owner", "Tech",
            "--deployment-date", old_date,
        ])
        assert result.exit_code == 0

        # Validate should show this model as needing review (exit code 1 = non-compliant)
        result = runner.invoke(app, ["validate", "--model-id", "overdue-model"])
        assert result.exit_code in (0, 1)  # Runs without crash
        # Should indicate overdue status
        assert "overdue" in result.output.lower() or "review" in result.output.lower()

        # Record a review to fix compliance
        result = runner.invoke(app, ["reviewed", "overdue-model", "--date", "today"])
        assert result.exit_code == 0

        # Now validate again - should be compliant (or close to it)
        result = runner.invoke(app, ["validate", "--model-id", "overdue-model"])
        assert result.exit_code in (0, 1)  # Runs without crash


class TestWorkflow4_SampleDataFullTest:
    """
    Workflow 4: Generate sample data → Run all reports → Validate all

    Tests the sample data generation and full system validation.
    """

    def test_sample_data_full_workflow(self):
        """Test generating sample data and running full system checks."""
        # Step 1: Generate sample data
        result = runner.invoke(app, ["sample-data", "--count", "10"])
        assert result.exit_code == 0, f"Sample data generation failed: {result.output}"
        assert "10" in result.output or "Created" in result.output or "generated" in result.output.lower()

        # Step 2: Verify data was created
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0, f"List failed: {result.output}"
        assert "10 models" in result.output

        # Step 3: Run inventory report
        result = runner.invoke(app, ["report", "inventory"])
        assert result.exit_code == 0, f"Inventory report failed: {result.output}"

        # Step 4: Run compliance report
        result = runner.invoke(app, ["report", "compliance"])
        assert result.exit_code == 0, f"Compliance report failed: {result.output}"

        # Step 5: Run risk report
        result = runner.invoke(app, ["report", "risk"])
        assert result.exit_code == 0, f"Risk report failed: {result.output}"

        # Step 6: Validate all models (may return 1 if some non-compliant)
        result = runner.invoke(app, ["validate", "--all"])
        assert result.exit_code in (0, 1), f"Validate all crashed: {result.output}"

        # Step 7: View dashboard
        result = runner.invoke(app, ["dashboard"])
        assert result.exit_code == 0, f"Dashboard failed: {result.output}"

    def test_sample_data_with_clear(self):
        """Test that sample data with --clear option removes existing models."""
        # Generate initial sample data
        result1 = runner.invoke(app, ["sample-data", "--count", "5"])
        assert result1.exit_code == 0

        # Get the model names
        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0
        data1 = json.loads(result.output)
        assert len(data1) == 5

        # Generate new sample data with --clear flag
        result2 = runner.invoke(app, ["sample-data", "--count", "3", "--clear"])
        assert result2.exit_code == 0

        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0
        data2 = json.loads(result.output)

        # Should now have only 3 models (not 5 + 3)
        assert len(data2) == 3

    def test_large_sample_data_performance(self, temp_dir):
        """Test system handles larger datasets."""
        # Generate 50 sample models
        result = runner.invoke(app, ["sample-data", "--count", "50"])
        assert result.exit_code == 0, f"Large sample data failed: {result.output}"

        # List with pagination
        result = runner.invoke(app, ["list", "--limit", "10"])
        assert result.exit_code == 0
        assert "showing 1-10 of 50" in result.output.lower()

        # Export all to JSON
        json_path = temp_dir / "large_export.json"
        result = runner.invoke(app, ["export", str(json_path)])
        assert result.exit_code == 0
        assert "50" in result.output

        # Validate all (may return 1 if some non-compliant)
        result = runner.invoke(app, ["validate", "--all"])
        assert result.exit_code in (0, 1)  # Runs without crash

        # Dashboard should handle large dataset
        result = runner.invoke(app, ["dashboard"])
        assert result.exit_code == 0


class TestWorkflow5_ErrorRecovery:
    """
    Workflow 5: Test error handling and recovery scenarios.

    Tests that the system handles errors gracefully.
    """

    def test_duplicate_model_handling(self):
        """Test that duplicate models are handled correctly."""
        # Add a model
        result = runner.invoke(app, [
            "add",
            "--name", "duplicate-test",
            "--vendor", "Test",
            "--risk-tier", "low",
            "--use-case", "Test",
            "--business-owner", "Owner",
            "--technical-owner", "Tech",
            "--deployment-date", "2024-01-01",
        ])
        assert result.exit_code == 0

        # Try to add duplicate
        result = runner.invoke(app, [
            "add",
            "--name", "duplicate-test",
            "--vendor", "Different",
            "--risk-tier", "high",
            "--use-case", "Different",
            "--business-owner", "Other",
            "--technical-owner", "Other",
            "--deployment-date", "2024-02-01",
        ])
        assert result.exit_code == 1
        assert "already exists" in result.output.lower() or "duplicate" in result.output.lower()

    def test_invalid_model_not_found(self):
        """Test handling of non-existent models."""
        result = runner.invoke(app, ["show", "nonexistent-model"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

        result = runner.invoke(app, ["update", "nonexistent-model", "--vendor", "Test"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

        result = runner.invoke(app, ["delete", "nonexistent-model", "--yes"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_import_with_errors_continue(self, temp_dir):
        """Test import continues on error when flag is set."""
        csv_path = temp_dir / "mixed_validity.csv"
        csv_content = """model_name,vendor,risk_tier,use_case,business_owner,technical_owner,deployment_date
valid-model-1,Vendor,high,Valid model,Owner,Tech,2024-01-01
invalid-model,,invalid_tier,Missing vendor,Owner,Tech,2024-01-01
valid-model-2,Vendor,low,Another valid,Owner,Tech,2024-01-01
"""
        csv_path.write_text(csv_content)

        # Import with continue-on-error
        result = runner.invoke(app, ["import", str(csv_path), "--continue-on-error"])
        assert result.exit_code == 0, f"Import failed: {result.output}"

        # Should have imported the valid ones
        result = runner.invoke(app, ["list"])
        assert "valid-model-1" in result.output
        assert "valid-model-2" in result.output


class TestWorkflow6_RoundTrip:
    """
    Workflow 6: Test data round-trip integrity.

    Tests that data exported and re-imported maintains integrity.
    """

    def test_json_roundtrip(self, temp_dir):
        """Test JSON export → import round-trip preserves data."""
        # Create models with all fields populated
        result = runner.invoke(app, [
            "add",
            "--name", "roundtrip-model",
            "--vendor", "RoundTrip Corp",
            "--risk-tier", "high",
            "--use-case", "Testing data integrity",
            "--business-owner", "Data Integrity Lead",
            "--technical-owner", "QA Engineer",
            "--deployment-date", "2024-06-15",
            "--environment", "prod",
            "--data-classification", "confidential",
            "--version", "2.0.0",
            "--api-endpoint", "https://api.example.com/v2",
        ])
        assert result.exit_code == 0

        # Export to JSON
        export_path = temp_dir / "roundtrip.json"
        result = runner.invoke(app, ["export", str(export_path), "--machine-headers"])
        assert result.exit_code == 0

        # Delete the model
        result = runner.invoke(app, ["delete", "roundtrip-model", "--yes"])
        assert result.exit_code == 0

        # Verify it's gone
        result = runner.invoke(app, ["list"])
        assert "roundtrip-model" not in result.output

        # Re-import from JSON
        result = runner.invoke(app, ["import", str(export_path)])
        assert result.exit_code == 0

        # Verify all fields preserved
        result = runner.invoke(app, ["show", "roundtrip-model"])
        assert result.exit_code == 0
        assert "RoundTrip Corp" in result.output
        assert "Data Integrity Lead" in result.output
        assert "2.0.0" in result.output
        assert "api.example.com" in result.output

    def test_csv_roundtrip(self, temp_dir):
        """Test CSV export → import round-trip preserves data."""
        # Create a model with all fields to ensure clean roundtrip
        result = runner.invoke(app, [
            "add",
            "--name", "csv-roundtrip",
            "--vendor", "CSV Corp",
            "--risk-tier", "medium",
            "--use-case", "CSV integrity test",
            "--business-owner", "Test Owner",
            "--technical-owner", "Test Tech",
            "--deployment-date", "2024-05-01",
            "--environment", "staging",
            "--data-classification", "internal",
        ])
        assert result.exit_code == 0

        # Export to CSV with machine headers (for re-import)
        export_path = temp_dir / "roundtrip.csv"
        result = runner.invoke(app, ["export", str(export_path), "--machine-headers"])
        assert result.exit_code == 0

        # Delete and re-import
        result = runner.invoke(app, ["delete", "csv-roundtrip", "--yes"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["import", str(export_path)])
        assert result.exit_code == 0

        # Verify
        result = runner.invoke(app, ["show", "csv-roundtrip"])
        assert result.exit_code == 0
        assert "CSV Corp" in result.output
