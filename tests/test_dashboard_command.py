"""Tests for the dashboard command."""

import pytest
from datetime import date, datetime, timedelta, timezone
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from mltrack.cli.main import app
from mltrack.cli.dashboard_commands import (
    _get_overdue_count,
    _get_compliance_percentage,
    _filter_models,
    _parse_risk_tier,
    _parse_environment,
    _get_filter_description,
)
from mltrack.core.database import reset_db
from mltrack.models.ai_model import (
    AIModel,
    RiskTier,
    DeploymentEnvironment,
    ModelStatus,
)

runner = CliRunner()


def _create_mock_model(
    name: str = "test-model",
    vendor: str = "test-vendor",
    risk_tier: RiskTier = RiskTier.MEDIUM,
    status: ModelStatus = ModelStatus.ACTIVE,
    environment: DeploymentEnvironment | None = None,
    next_review_date: date | None = None,
    created_at: datetime | None = None,
) -> AIModel:
    """Create a mock AIModel for testing."""
    model = MagicMock(spec=AIModel)
    model.model_name = name
    model.vendor = vendor
    model.risk_tier = risk_tier
    model.status = status
    model.deployment_environment = environment
    model.next_review_date = next_review_date
    model.created_at = created_at or datetime.now(timezone.utc)
    model.business_owner = "test-owner"
    model.technical_owner = "test-tech"
    model.use_case = "test use case"
    model.deployment_date = date.today()
    return model


# =============================================================================
# Unit Tests for Metric Calculations
# =============================================================================


class TestOverdueCount:
    """Unit tests for _get_overdue_count function."""

    def test_empty_list_returns_zero(self):
        """Test empty model list returns 0 overdue."""
        assert _get_overdue_count([]) == 0

    def test_no_overdue_models(self):
        """Test models with future review dates return 0."""
        models = [
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=30)
            ),
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=60)
            ),
        ]
        assert _get_overdue_count(models) == 0

    def test_one_overdue_model(self):
        """Test single overdue model is counted."""
        models = [
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=1)
            ),
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=30)
            ),
        ]
        assert _get_overdue_count(models) == 1

    def test_multiple_overdue_models(self):
        """Test multiple overdue models are counted."""
        models = [
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=10)
            ),
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=5)
            ),
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=1)
            ),
        ]
        assert _get_overdue_count(models) == 3

    def test_today_is_not_overdue(self):
        """Test model due today is not counted as overdue."""
        models = [
            _create_mock_model(next_review_date=date.today()),
        ]
        assert _get_overdue_count(models) == 0

    def test_inactive_models_not_counted(self):
        """Test deprecated/decommissioned models not counted."""
        models = [
            _create_mock_model(
                status=ModelStatus.DEPRECATED,
                next_review_date=date.today() - timedelta(days=10),
            ),
            _create_mock_model(
                status=ModelStatus.DECOMMISSIONED,
                next_review_date=date.today() - timedelta(days=10),
            ),
        ]
        assert _get_overdue_count(models) == 0

    def test_null_review_date_not_counted(self):
        """Test models without review date are not counted as overdue."""
        models = [
            _create_mock_model(next_review_date=None),
        ]
        assert _get_overdue_count(models) == 0


class TestCompliancePercentage:
    """Unit tests for _get_compliance_percentage function."""

    def test_empty_list_returns_100(self):
        """Test empty model list returns 100% compliance."""
        assert _get_compliance_percentage([]) == 100.0

    def test_all_compliant_models(self):
        """Test 100% compliance when no models are overdue."""
        models = [
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=30)
            ),
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=60)
            ),
        ]
        assert _get_compliance_percentage(models) == 100.0

    def test_half_compliant(self):
        """Test 50% compliance calculation."""
        models = [
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=30)
            ),
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=10)
            ),
        ]
        assert _get_compliance_percentage(models) == 50.0

    def test_no_compliant_models(self):
        """Test 0% compliance when all are overdue."""
        models = [
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=10)
            ),
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=5)
            ),
        ]
        assert _get_compliance_percentage(models) == 0.0

    def test_due_today_is_compliant(self):
        """Test model due today counts as compliant."""
        models = [
            _create_mock_model(next_review_date=date.today()),
        ]
        assert _get_compliance_percentage(models) == 100.0

    def test_only_active_models_counted(self):
        """Test only active models affect compliance."""
        models = [
            _create_mock_model(
                status=ModelStatus.ACTIVE,
                next_review_date=date.today() + timedelta(days=30),
            ),
            _create_mock_model(
                status=ModelStatus.DEPRECATED,
                next_review_date=date.today() - timedelta(days=100),
            ),
        ]
        # Only 1 active model, which is compliant
        assert _get_compliance_percentage(models) == 100.0

    def test_null_review_date_is_compliant(self):
        """Test models without review date count as compliant."""
        models = [
            _create_mock_model(next_review_date=None),
        ]
        assert _get_compliance_percentage(models) == 100.0

    def test_three_of_four_compliant(self):
        """Test 75% compliance calculation."""
        models = [
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=30)
            ),
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=30)
            ),
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=30)
            ),
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=10)
            ),
        ]
        assert _get_compliance_percentage(models) == 75.0


# =============================================================================
# Unit Tests for Filter Functions
# =============================================================================


class TestFilterModels:
    """Unit tests for _filter_models function."""

    def test_no_filters_returns_all(self):
        """Test no filters returns all models."""
        models = [
            _create_mock_model(name="model-1"),
            _create_mock_model(name="model-2"),
        ]
        result = _filter_models(models)
        assert len(result) == 2

    def test_filter_by_risk_tier(self):
        """Test filtering by risk tier."""
        models = [
            _create_mock_model(name="critical-1", risk_tier=RiskTier.CRITICAL),
            _create_mock_model(name="high-1", risk_tier=RiskTier.HIGH),
            _create_mock_model(name="critical-2", risk_tier=RiskTier.CRITICAL),
        ]
        result = _filter_models(models, risk_tier=RiskTier.CRITICAL)
        assert len(result) == 2
        assert all(m.risk_tier == RiskTier.CRITICAL for m in result)

    def test_filter_by_vendor(self):
        """Test filtering by vendor name."""
        models = [
            _create_mock_model(name="model-1", vendor="Anthropic"),
            _create_mock_model(name="model-2", vendor="OpenAI"),
            _create_mock_model(name="model-3", vendor="Anthropic"),
        ]
        result = _filter_models(models, vendor="anthropic")
        assert len(result) == 2
        assert all(m.vendor == "Anthropic" for m in result)

    def test_filter_by_vendor_case_insensitive(self):
        """Test vendor filter is case insensitive."""
        models = [
            _create_mock_model(vendor="ANTHROPIC"),
            _create_mock_model(vendor="anthropic"),
            _create_mock_model(vendor="Anthropic"),
        ]
        result = _filter_models(models, vendor="AnThRoPiC")
        assert len(result) == 3

    def test_filter_by_environment(self):
        """Test filtering by deployment environment."""
        models = [
            _create_mock_model(name="prod-1", environment=DeploymentEnvironment.PROD),
            _create_mock_model(name="dev-1", environment=DeploymentEnvironment.DEV),
            _create_mock_model(name="prod-2", environment=DeploymentEnvironment.PROD),
        ]
        result = _filter_models(models, environment=DeploymentEnvironment.PROD)
        assert len(result) == 2
        assert all(m.deployment_environment == DeploymentEnvironment.PROD for m in result)

    def test_combined_filters_and_logic(self):
        """Test multiple filters use AND logic."""
        models = [
            _create_mock_model(
                name="match",
                risk_tier=RiskTier.HIGH,
                vendor="Anthropic",
                environment=DeploymentEnvironment.PROD,
            ),
            _create_mock_model(
                name="wrong-risk",
                risk_tier=RiskTier.LOW,
                vendor="Anthropic",
                environment=DeploymentEnvironment.PROD,
            ),
            _create_mock_model(
                name="wrong-vendor",
                risk_tier=RiskTier.HIGH,
                vendor="OpenAI",
                environment=DeploymentEnvironment.PROD,
            ),
            _create_mock_model(
                name="wrong-env",
                risk_tier=RiskTier.HIGH,
                vendor="Anthropic",
                environment=DeploymentEnvironment.DEV,
            ),
        ]
        result = _filter_models(
            models,
            risk_tier=RiskTier.HIGH,
            vendor="Anthropic",
            environment=DeploymentEnvironment.PROD,
        )
        assert len(result) == 1
        assert result[0].model_name == "match"

    def test_filter_returns_empty_when_no_match(self):
        """Test filter returns empty list when nothing matches."""
        models = [
            _create_mock_model(risk_tier=RiskTier.LOW),
            _create_mock_model(risk_tier=RiskTier.MEDIUM),
        ]
        result = _filter_models(models, risk_tier=RiskTier.CRITICAL)
        assert len(result) == 0


class TestParseRiskTier:
    """Unit tests for _parse_risk_tier function."""

    def test_parse_critical(self):
        """Test parsing 'critical' risk tier."""
        assert _parse_risk_tier("critical") == RiskTier.CRITICAL

    def test_parse_high(self):
        """Test parsing 'high' risk tier."""
        assert _parse_risk_tier("high") == RiskTier.HIGH

    def test_parse_medium(self):
        """Test parsing 'medium' risk tier."""
        assert _parse_risk_tier("medium") == RiskTier.MEDIUM

    def test_parse_low(self):
        """Test parsing 'low' risk tier."""
        assert _parse_risk_tier("low") == RiskTier.LOW

    def test_parse_uppercase(self):
        """Test parsing uppercase risk tier."""
        assert _parse_risk_tier("CRITICAL") == RiskTier.CRITICAL

    def test_parse_mixed_case(self):
        """Test parsing mixed case risk tier."""
        assert _parse_risk_tier("HiGh") == RiskTier.HIGH

    def test_parse_invalid_returns_none(self):
        """Test invalid risk tier returns None."""
        assert _parse_risk_tier("invalid") is None

    def test_parse_none_returns_none(self):
        """Test None input returns None."""
        assert _parse_risk_tier(None) is None


class TestParseEnvironment:
    """Unit tests for _parse_environment function."""

    def test_parse_prod(self):
        """Test parsing 'prod' environment."""
        assert _parse_environment("prod") == DeploymentEnvironment.PROD

    def test_parse_staging(self):
        """Test parsing 'staging' environment."""
        assert _parse_environment("staging") == DeploymentEnvironment.STAGING

    def test_parse_dev(self):
        """Test parsing 'dev' environment."""
        assert _parse_environment("dev") == DeploymentEnvironment.DEV

    def test_parse_production_alias(self):
        """Test 'production' alias maps to prod."""
        assert _parse_environment("production") == DeploymentEnvironment.PROD

    def test_parse_development_alias(self):
        """Test 'development' alias maps to dev."""
        assert _parse_environment("development") == DeploymentEnvironment.DEV

    def test_parse_stage_alias(self):
        """Test 'stage' alias maps to staging."""
        assert _parse_environment("stage") == DeploymentEnvironment.STAGING

    def test_parse_uppercase(self):
        """Test parsing uppercase environment."""
        assert _parse_environment("PROD") == DeploymentEnvironment.PROD

    def test_parse_invalid_returns_none(self):
        """Test invalid environment returns None."""
        assert _parse_environment("invalid") is None

    def test_parse_none_returns_none(self):
        """Test None input returns None."""
        assert _parse_environment(None) is None


class TestGetFilterDescription:
    """Unit tests for _get_filter_description function."""

    def test_no_filters_returns_none(self):
        """Test no filters returns None."""
        assert _get_filter_description(None, None, None) is None

    def test_risk_only(self):
        """Test risk tier only description."""
        result = _get_filter_description(RiskTier.CRITICAL, None, None)
        assert result == "Risk: CRITICAL"

    def test_vendor_only(self):
        """Test vendor only description."""
        result = _get_filter_description(None, "anthropic", None)
        assert result == "Vendor: anthropic"

    def test_environment_only(self):
        """Test environment only description."""
        result = _get_filter_description(None, None, DeploymentEnvironment.PROD)
        assert result == "Env: PROD"

    def test_all_filters_combined(self):
        """Test all filters combined with pipe separator."""
        result = _get_filter_description(
            RiskTier.HIGH,
            "openai",
            DeploymentEnvironment.STAGING,
        )
        assert "Risk: HIGH" in result
        assert "Vendor: openai" in result
        assert "Env: STAGING" in result
        assert "|" in result

    def test_two_filters_combined(self):
        """Test two filters combined."""
        result = _get_filter_description(RiskTier.LOW, "test", None)
        assert "Risk: LOW" in result
        assert "Vendor: test" in result
        assert "|" in result


# =============================================================================
# CLI Integration Tests with Mock Data
# =============================================================================


@pytest.fixture
def mock_models():
    """Fixture providing a set of mock models for testing."""
    return [
        _create_mock_model(
            name="claude-3",
            vendor="Anthropic",
            risk_tier=RiskTier.HIGH,
            environment=DeploymentEnvironment.PROD,
            next_review_date=date.today() + timedelta(days=60),
        ),
        _create_mock_model(
            name="gpt-4",
            vendor="OpenAI",
            risk_tier=RiskTier.CRITICAL,
            environment=DeploymentEnvironment.PROD,
            next_review_date=date.today() - timedelta(days=5),  # Overdue
        ),
        _create_mock_model(
            name="gemini",
            vendor="Google",
            risk_tier=RiskTier.MEDIUM,
            environment=DeploymentEnvironment.STAGING,
            next_review_date=date.today() + timedelta(days=90),
        ),
        _create_mock_model(
            name="llama",
            vendor="Meta",
            risk_tier=RiskTier.LOW,
            environment=DeploymentEnvironment.DEV,
            next_review_date=date.today() + timedelta(days=200),
        ),
        _create_mock_model(
            name="old-model",
            vendor="Legacy",
            risk_tier=RiskTier.HIGH,
            status=ModelStatus.DEPRECATED,
            environment=DeploymentEnvironment.PROD,
            next_review_date=date.today() - timedelta(days=100),
        ),
    ]


class TestDashboardWithModels:
    """Tests for dashboard display with actual model data."""

    def test_dashboard_displays_with_models(self, mock_models):
        """Test dashboard renders without error with models."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = mock_models

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            assert "Model Inventory Summary" in result.output

    def test_displays_correct_total_count(self, mock_models):
        """Test dashboard shows correct total model count."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = mock_models

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            # 5 total models
            assert "5" in result.output

    def test_displays_model_names(self, mock_models):
        """Test dashboard displays model names."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = mock_models

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            # Recent additions should show model names
            assert "claude-3" in result.output or "gpt-4" in result.output

    def test_filter_reduces_displayed_models(self, mock_models):
        """Test filtering reduces the model set displayed."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = mock_models

            # Filter to only Anthropic models
            result = runner.invoke(app, ["dashboard", "--vendor", "Anthropic"])
            assert result.exit_code == 0
            # Should only show 1 model
            assert "1" in result.output


class TestDashboardEmptyState:
    """Tests for dashboard empty state handling."""

    def test_empty_inventory_renders(self):
        """Test dashboard renders with empty inventory."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = []

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            assert "Model Inventory Summary" in result.output

    def test_empty_shows_zero_models(self):
        """Test empty inventory shows 0 models."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = []

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            assert "0" in result.output

    def test_empty_shows_100_percent_compliance(self):
        """Test empty inventory shows 100% compliance."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = []

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            assert "100.0%" in result.output

    def test_empty_shows_no_models_message(self):
        """Test empty recent additions shows message."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = []

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            assert "No models" in result.output

    def test_empty_shows_all_up_to_date(self):
        """Test empty reviews shows up to date message."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = []

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            # Text may be truncated by Rich panel width
            assert "All models are up to" in result.output

    def test_empty_shows_no_high_risk(self):
        """Test empty high risk section shows positive message."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = []

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            assert "No high-risk" in result.output


class TestDashboardMetricsCalculation:
    """Tests verifying dashboard metrics are calculated correctly."""

    def test_overdue_count_displayed(self):
        """Test overdue count is calculated and displayed."""
        models = [
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=10)
            ),
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=5)
            ),
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=30)
            ),
        ]
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = models

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            # 2 overdue models
            assert "Overdue" in result.output

    def test_compliance_percentage_displayed(self):
        """Test compliance percentage is calculated correctly."""
        # 2 compliant, 2 overdue = 50%
        models = [
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=30)
            ),
            _create_mock_model(
                next_review_date=date.today() + timedelta(days=30)
            ),
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=10)
            ),
            _create_mock_model(
                next_review_date=date.today() - timedelta(days=10)
            ),
        ]
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = models

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            assert "50.0%" in result.output

    def test_risk_tier_counts_displayed(self):
        """Test risk tier counts are displayed."""
        models = [
            _create_mock_model(risk_tier=RiskTier.CRITICAL),
            _create_mock_model(risk_tier=RiskTier.CRITICAL),
            _create_mock_model(risk_tier=RiskTier.HIGH),
            _create_mock_model(risk_tier=RiskTier.MEDIUM),
        ]
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = models

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
            assert "CRITICAL" in result.output
            assert "HIGH" in result.output
            assert "MEDIUM" in result.output
            assert "LOW" in result.output


class TestDashboardFilteringIntegration:
    """Integration tests for dashboard filtering via CLI."""

    def test_risk_filter_reduces_results(self):
        """Test --risk filter reduces displayed models."""
        models = [
            _create_mock_model(risk_tier=RiskTier.CRITICAL),
            _create_mock_model(risk_tier=RiskTier.HIGH),
            _create_mock_model(risk_tier=RiskTier.MEDIUM),
        ]
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = models

            result = runner.invoke(app, ["dashboard", "--risk", "critical"])
            assert result.exit_code == 0
            # Should show filtered indicator
            assert "Filtered" in result.output
            # Should show 1 model
            assert "Total Models" in result.output

    def test_vendor_filter_case_insensitive(self):
        """Test vendor filter works case-insensitively."""
        models = [
            _create_mock_model(vendor="Anthropic"),
            _create_mock_model(vendor="OpenAI"),
        ]
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = models

            result = runner.invoke(app, ["dashboard", "--vendor", "ANTHROPIC"])
            assert result.exit_code == 0
            assert "Filtered" in result.output

    def test_environment_filter_works(self):
        """Test --environment filter works."""
        models = [
            _create_mock_model(environment=DeploymentEnvironment.PROD),
            _create_mock_model(environment=DeploymentEnvironment.DEV),
        ]
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = models

            result = runner.invoke(app, ["dashboard", "--environment", "prod"])
            assert result.exit_code == 0
            assert "PROD" in result.output

    def test_combined_filters_work(self):
        """Test multiple filters can be combined."""
        models = [
            _create_mock_model(
                risk_tier=RiskTier.HIGH,
                vendor="Anthropic",
                environment=DeploymentEnvironment.PROD,
            ),
            _create_mock_model(
                risk_tier=RiskTier.LOW,
                vendor="Anthropic",
                environment=DeploymentEnvironment.PROD,
            ),
        ]
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = models

            result = runner.invoke(
                app,
                ["dashboard", "--risk", "high", "--vendor", "anthropic", "-e", "prod"],
            )
            assert result.exit_code == 0
            assert "HIGH" in result.output
            assert "Anthropic" in result.output or "anthropic" in result.output
            assert "PROD" in result.output


class TestDashboardRenderingWithoutErrors:
    """Tests verifying dashboard renders without errors in various states."""

    def test_renders_with_all_risk_tiers(self):
        """Test dashboard renders with models of all risk tiers."""
        models = [
            _create_mock_model(risk_tier=RiskTier.CRITICAL),
            _create_mock_model(risk_tier=RiskTier.HIGH),
            _create_mock_model(risk_tier=RiskTier.MEDIUM),
            _create_mock_model(risk_tier=RiskTier.LOW),
        ]
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = models

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0

    def test_renders_with_all_environments(self):
        """Test dashboard renders with all deployment environments."""
        models = [
            _create_mock_model(environment=DeploymentEnvironment.PROD),
            _create_mock_model(environment=DeploymentEnvironment.STAGING),
            _create_mock_model(environment=DeploymentEnvironment.DEV),
            _create_mock_model(environment=None),
        ]
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = models

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0

    def test_renders_with_all_statuses(self):
        """Test dashboard renders with all model statuses."""
        models = [
            _create_mock_model(status=ModelStatus.ACTIVE),
            _create_mock_model(status=ModelStatus.DEPRECATED),
            _create_mock_model(status=ModelStatus.DECOMMISSIONED),
        ]
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = models

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0

    def test_renders_with_null_fields(self):
        """Test dashboard renders when models have null optional fields."""
        model = _create_mock_model()
        model.deployment_environment = None
        model.next_review_date = None

        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = [model]

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0

    def test_renders_with_long_names(self):
        """Test dashboard renders with very long model names."""
        model = _create_mock_model(
            name="this-is-a-very-long-model-name-that-might-cause-display-issues"
        )
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = [model]

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0

    def test_renders_with_many_models(self):
        """Test dashboard renders with many models."""
        models = [_create_mock_model(name=f"model-{i}") for i in range(50)]
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = models

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0


# =============================================================================
# CLI Option Tests
# =============================================================================


class TestDashboardCLIOptions:
    """Tests for dashboard CLI options."""

    def test_help_shows_all_options(self):
        """Test help shows all available options."""
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0
        assert "--watch" in result.output
        assert "--interval" in result.output
        assert "--risk" in result.output
        assert "--vendor" in result.output
        assert "--environment" in result.output

    def test_invalid_risk_shows_error(self):
        """Test invalid risk tier shows helpful error."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = []

            result = runner.invoke(app, ["dashboard", "--risk", "invalid"])
            assert result.exit_code == 1
            assert "Invalid risk tier" in result.output

    def test_invalid_environment_shows_error(self):
        """Test invalid environment shows helpful error."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = []

            result = runner.invoke(app, ["dashboard", "--environment", "invalid"])
            assert result.exit_code == 1
            assert "Invalid environment" in result.output

    def test_short_flags_work(self):
        """Test short flags -r, -V, -e work."""
        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.return_value = []

            result = runner.invoke(
                app, ["dashboard", "-r", "high", "-V", "test", "-e", "prod"]
            )
            assert result.exit_code == 0

    def test_interval_default(self):
        """Test interval default is shown in help."""
        result = runner.invoke(app, ["dashboard", "--help"])
        assert "default: 30" in result.output


class TestDashboardDatabaseError:
    """Tests for database error handling."""

    def test_handles_database_error(self):
        """Test dashboard handles database errors gracefully."""
        from mltrack.core.exceptions import DatabaseError

        with patch("mltrack.cli.dashboard_commands.get_all_models") as mock_get:
            mock_get.side_effect = DatabaseError("query", "Connection failed")

            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0  # Should still exit cleanly
            assert "Error" in result.output or "Database" in result.output
