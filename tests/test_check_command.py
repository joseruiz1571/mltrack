"""Tests for the mltrack check CLI command (CI/CD compliance gate)."""

import json
import pytest
from datetime import date, timedelta
from typer.testing import CliRunner

from mltrack.cli.main import app
from mltrack.core.database import init_db
from mltrack.core.storage import create_model

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
def compliant_model(clean_db):
    """Create a fully compliant model."""
    return create_model({
        "model_name": "compliant-model",
        "vendor": "test-vendor",
        "risk_tier": "low",
        "use_case": "Testing check command",
        "business_owner": "Business Owner",
        "technical_owner": "Technical Owner",
        "deployment_date": date.today(),
        "deployment_environment": "dev",
        "status": "active",
    })


@pytest.fixture
def non_compliant_model(clean_db):
    """Create a model with compliance issues (overdue critical review)."""
    return create_model({
        "model_name": "non-compliant-model",
        "vendor": "test-vendor",
        "risk_tier": "critical",
        "use_case": "Testing check failures",
        "business_owner": "Business Owner",
        "technical_owner": "Technical Owner",
        "deployment_date": date.today() - timedelta(days=60),
        "deployment_environment": "prod",
        "status": "active",
    })


@pytest.fixture
def mixed_models(clean_db):
    """Create a mix of compliant and non-compliant models."""
    create_model({
        "model_name": "good-model",
        "vendor": "vendor-a",
        "risk_tier": "low",
        "use_case": "Compliant model",
        "business_owner": "Owner A",
        "technical_owner": "Tech A",
        "deployment_date": date.today(),
        "status": "active",
    })
    create_model({
        "model_name": "bad-model",
        "vendor": "vendor-b",
        "risk_tier": "critical",
        "use_case": "Overdue model",
        "business_owner": "Owner B",
        "technical_owner": "Tech B",
        "deployment_date": date.today() - timedelta(days=60),
        "deployment_environment": "prod",
        "status": "active",
    })


# --- Exit code tests ---

class TestExitCodes:
    """The core contract: exit 0 = pass, exit 1 = fail."""

    def test_compliant_model_exits_0(self, compliant_model):
        result = runner.invoke(app, ["check", "compliant-model"])
        assert result.exit_code == 0

    def test_non_compliant_model_exits_1(self, non_compliant_model):
        result = runner.invoke(app, ["check", "non-compliant-model"])
        assert result.exit_code == 1

    def test_all_compliant_exits_0(self, compliant_model):
        result = runner.invoke(app, ["check", "--all"])
        assert result.exit_code == 0

    def test_all_with_failures_exits_1(self, mixed_models):
        result = runner.invoke(app, ["check", "--all"])
        assert result.exit_code == 1

    def test_model_not_found_exits_1(self, clean_db):
        result = runner.invoke(app, ["check", "nonexistent-model"])
        assert result.exit_code == 1

    def test_no_args_exits_1(self, clean_db):
        result = runner.invoke(app, ["check"])
        assert result.exit_code == 1


# --- Silent by default ---

class TestSilentDefault:
    """Check produces no stdout by default (pipeline-friendly)."""

    def test_pass_silent(self, compliant_model):
        result = runner.invoke(app, ["check", "compliant-model"])
        assert result.output.strip() == ""

    def test_fail_silent(self, non_compliant_model):
        result = runner.invoke(app, ["check", "non-compliant-model"])
        # No JSON or rich output on stdout
        assert "FAIL" not in result.output
        assert "{" not in result.output


# --- JSON output ---

class TestJsonOutput:
    """--json produces structured, parseable output."""

    def test_json_compliant(self, compliant_model):
        result = runner.invoke(app, ["check", "compliant-model", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["passed"] is True
        assert data["summary"]["total"] == 1
        assert data["summary"]["failed"] == 0
        assert data["failures"] == []

    def test_json_non_compliant(self, non_compliant_model):
        result = runner.invoke(app, ["check", "non-compliant-model", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["passed"] is False
        assert data["summary"]["failed"] >= 1
        assert len(data["failures"]) >= 1
        assert data["failures"][0]["model"] == "non-compliant-model"
        assert len(data["failures"][0]["violations"]) >= 1

    def test_json_all(self, mixed_models):
        result = runner.invoke(app, ["check", "--all", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["summary"]["total"] == 2
        assert data["summary"]["passed"] == 1
        assert data["summary"]["failed"] == 1

    def test_json_compliance_rate(self, mixed_models):
        result = runner.invoke(app, ["check", "--all", "--json"])
        data = json.loads(result.output)
        assert data["summary"]["compliance_rate"] == 50.0


# --- Verbose output ---

class TestVerboseOutput:
    """--verbose shows human-readable details."""

    def test_verbose_shows_pass(self, compliant_model):
        result = runner.invoke(app, ["check", "compliant-model", "--verbose"])
        assert result.exit_code == 0
        assert "PASS" in result.output
        assert "compliant-model" in result.output

    def test_verbose_shows_fail_with_violations(self, non_compliant_model):
        result = runner.invoke(app, ["check", "non-compliant-model", "--verbose"])
        assert result.exit_code == 1
        assert "FAIL" in result.output
        assert "overdue" in result.output.lower() or "missing" in result.output.lower()

    def test_verbose_shows_summary(self, mixed_models):
        result = runner.invoke(app, ["check", "--all", "--verbose"])
        assert "1/2 compliant" in result.output or "50%" in result.output


# --- Risk tier filtering ---

class TestRiskFilter:
    """--risk filters to specific tier."""

    def test_risk_filter(self, mixed_models):
        result = runner.invoke(app, ["check", "--risk", "low"])
        assert result.exit_code == 0

    def test_risk_filter_critical_fails(self, mixed_models):
        result = runner.invoke(app, ["check", "--risk", "critical"])
        assert result.exit_code == 1

    def test_invalid_risk_tier_exits_1(self, clean_db):
        result = runner.invoke(app, ["check", "--risk", "bogus"])
        assert result.exit_code == 1


# --- Empty inventory ---

class TestEmptyInventory:
    """Empty inventory is compliant (nothing to fail)."""

    def test_all_empty_exits_0(self, clean_db):
        result = runner.invoke(app, ["check", "--all"])
        assert result.exit_code == 0

    def test_risk_filter_empty_exits_0(self, clean_db):
        result = runner.invoke(app, ["check", "--risk", "critical"])
        assert result.exit_code == 0


# --- Combined flags ---

class TestCombinedFlags:
    """--json and --verbose can be used together."""

    def test_json_and_verbose(self, mixed_models):
        result = runner.invoke(app, ["check", "--all", "--json", "--verbose"])
        assert result.exit_code == 1
        # JSON should still be parseable from output
        # (verbose goes to stderr in real usage, but CliRunner merges them)
        assert "FAIL" in result.output or '"passed"' in result.output
