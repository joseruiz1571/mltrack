"""Tests for CLI commands."""

from typer.testing import CliRunner

from mltrack.cli.main import app

runner = CliRunner()


class TestCLI:
    """Tests for CLI entry points."""

    def test_app_help(self):
        """Test that --help works."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Model Lineage Tracker" in result.output

    def test_version(self):
        """Test that --version works."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_model_help(self):
        """Test model subcommand help."""
        result = runner.invoke(app, ["model", "--help"])
        assert result.exit_code == 0
        assert "add" in result.output
        assert "list" in result.output

    def test_report_help(self):
        """Test report subcommand help."""
        result = runner.invoke(app, ["report", "--help"])
        assert result.exit_code == 0
        assert "overdue" in result.output
        assert "gaps" in result.output
