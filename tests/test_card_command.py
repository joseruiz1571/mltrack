"""Tests for `mltrack card export` / `mltrack card validate` and card_service.

Where validation correctness matters, these tests use the real ``jsonschema``
library as ground truth (not the project's own checker) so a green test proves
the card conforms to the actual Governance Card Stack contract.
"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from mltrack.cli.main import app
from mltrack.core.exceptions import ModelNotFoundError
from mltrack.models.ai_model import (
    AIModel,
    DataClassification,
    DeploymentEnvironment,
    ModelStatus,
    RiskTier,
)
from mltrack.services import card_service
from mltrack.services.card_service import load_schema, model_to_card, validate_card

runner = CliRunner()

VALID_UUID4 = "f47ac10b-58cc-4372-a567-0e02b2c3d479"


def _make_model(**overrides) -> AIModel:
    """A MagicMock standing in for a fully populated AIModel row."""
    model = MagicMock(spec=AIModel)
    model.id = overrides.get("id", VALID_UUID4)
    model.model_name = overrides.get("model_name", "fraud-detector")
    model.vendor = overrides.get("vendor", "In-house")
    model.risk_tier = overrides.get("risk_tier", RiskTier.CRITICAL)
    model.use_case = overrides.get("use_case", "Real-time fraud detection for payments")
    model.business_owner = overrides.get("business_owner", "Risk Team")
    model.technical_owner = overrides.get("technical_owner", "ML Platform")
    model.deployment_date = overrides.get("deployment_date", date(2026, 1, 15))
    model.model_version = overrides.get("model_version", "2.1.0")
    model.deployment_environment = overrides.get(
        "deployment_environment", DeploymentEnvironment.PROD
    )
    model.api_endpoint = overrides.get("api_endpoint", "https://api.internal/fraud")
    model.last_review_date = overrides.get("last_review_date", date(2026, 2, 1))
    model.next_review_date = overrides.get("next_review_date", date(2026, 3, 3))
    model.data_classification = overrides.get(
        "data_classification", DataClassification.CONFIDENTIAL
    )
    model.status = overrides.get("status", ModelStatus.ACTIVE)
    model.notes = overrides.get("notes", None)
    return model


# --------------------------------------------------------------------------- #
# Service: AIModel -> Model Card mapping
# --------------------------------------------------------------------------- #


def test_model_to_card_required_fields():
    card = model_to_card(_make_model())
    assert card["spec_version"] == "0.1.0"
    assert card["card_type"] == "model"
    assert card["metadata"]["uuid"] == VALID_UUID4
    assert card["metadata"]["name"] == "fraud-detector"
    assert card["metadata"]["version"] == "2.1.0"
    assert card["model"]["provider"] == "In-house"
    assert card["model"]["intended_use"].startswith("Real-time fraud")


def test_model_to_card_lifecycle_mapping():
    def status_of(s):
        return model_to_card(_make_model(status=s))["metadata"]["lifecycle_status"]

    assert status_of(ModelStatus.ACTIVE) == "active"
    assert status_of(ModelStatus.DEPRECATED) == "deprecated"
    assert status_of(ModelStatus.DECOMMISSIONED) == "retired"


def test_model_to_card_version_defaults_when_missing():
    card = model_to_card(_make_model(model_version=None))
    assert card["metadata"]["version"] == "unversioned"
    assert "version" not in card["model"]  # omitted from model block when absent


def test_model_to_card_owners_carry_business_and_technical():
    owners = model_to_card(_make_model())["metadata"]["owners"]
    assert {"name": "Risk Team", "role": "business"} in owners
    assert {"name": "ML Platform", "role": "technical"} in owners


def test_model_to_card_optional_classification_omitted():
    card = model_to_card(
        _make_model(data_classification=None, deployment_environment=None)
    )
    assert "data_classification" not in card["classification"]
    assert "environment" not in card["classification"]
    assert card["classification"]["risk_tier"] == "critical"


def test_model_to_card_governance_block():
    gov = model_to_card(_make_model())["governance"]
    assert gov["review_cycle_days"] == 30  # CRITICAL -> 30 days
    assert gov["last_review"] == "2026-02-01"
    assert gov["next_review_due"] == "2026-03-03"


# --------------------------------------------------------------------------- #
# Ground truth: validate against the real jsonschema library
# --------------------------------------------------------------------------- #


def test_exported_card_validates_under_real_jsonschema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = load_schema()
    card = model_to_card(_make_model())
    # Raises ValidationError if the card does not conform.
    jsonschema.Draft202012Validator(schema).validate(card)


def test_minimal_model_validates_under_real_jsonschema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = load_schema()
    # A model with all optional fields absent must still produce a valid card.
    card = model_to_card(
        _make_model(
            model_version=None,
            deployment_environment=None,
            api_endpoint=None,
            last_review_date=None,
            next_review_date=None,
            data_classification=None,
            notes=None,
        )
    )
    jsonschema.Draft202012Validator(schema).validate(card)


# --------------------------------------------------------------------------- #
# validate_card() behavior
# --------------------------------------------------------------------------- #


def test_validate_card_accepts_valid_card():
    assert validate_card(model_to_card(_make_model())) == []


def test_validate_card_rejects_missing_required_uuid():
    card = model_to_card(_make_model())
    del card["metadata"]["uuid"]
    assert any("uuid" in e for e in validate_card(card))


def test_validate_card_rejects_wrong_card_type():
    card = model_to_card(_make_model())
    card["card_type"] = "agent"
    assert validate_card(card)


def test_validate_card_rejects_additional_top_level_property():
    card = model_to_card(_make_model())
    card["bogus"] = True
    assert any("bogus" in e for e in validate_card(card))


def test_validate_card_rejects_bad_uuid_pattern():
    card = model_to_card(_make_model(id="not-a-uuid"))
    assert validate_card(card)


# --------------------------------------------------------------------------- #
# Minimal fallback validator (the zero-dependency path)
# --------------------------------------------------------------------------- #


def test_minimal_validator_passes_valid_card():
    from mltrack.services.card_service import _minimal_validate

    assert _minimal_validate(model_to_card(_make_model()), load_schema()) == []


def test_minimal_validator_catches_missing_required():
    from mltrack.services.card_service import _minimal_validate

    card = model_to_card(_make_model())
    del card["model"]["provider"]
    assert any("provider" in e for e in _minimal_validate(card, load_schema()))


def test_validate_card_falls_back_without_jsonschema(monkeypatch):
    """When jsonschema cannot be imported, validate_card uses the minimal checker."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "jsonschema" or name.startswith("jsonschema."):
            raise ImportError("simulated missing jsonschema")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert validate_card(model_to_card(_make_model())) == []
    bad = model_to_card(_make_model())
    bad["card_type"] = "not-a-model"
    assert validate_card(bad)


# --------------------------------------------------------------------------- #
# CLI: card export
# --------------------------------------------------------------------------- #


def test_cli_export_to_stdout():
    with patch("mltrack.cli.card_command.get_model", return_value=_make_model()):
        result = runner.invoke(app, ["card", "export", "fraud-detector"])
    assert result.exit_code == 0
    card = json.loads(result.stdout)
    assert card["card_type"] == "model"
    assert card["metadata"]["name"] == "fraud-detector"


def test_cli_export_to_file(tmp_path):
    out = tmp_path / "card.json"
    with patch("mltrack.cli.card_command.get_model", return_value=_make_model()):
        result = runner.invoke(app, ["card", "export", "fraud-detector", "-o", str(out)])
    assert result.exit_code == 0
    assert out.is_file()
    assert json.loads(out.read_text())["metadata"]["uuid"] == VALID_UUID4


def test_cli_export_model_not_found_exits_1():
    with patch(
        "mltrack.cli.card_command.get_model",
        side_effect=ModelNotFoundError("nope"),
    ), patch("mltrack.cli.card_command.get_all_models", return_value=[]):
        result = runner.invoke(app, ["card", "export", "nope"])
    assert result.exit_code == 1


# --------------------------------------------------------------------------- #
# CLI: card validate
# --------------------------------------------------------------------------- #


def test_cli_validate_valid_file(tmp_path):
    out = tmp_path / "card.json"
    with patch("mltrack.cli.card_command.get_model", return_value=_make_model()):
        runner.invoke(app, ["card", "export", "fraud-detector", "-o", str(out)])
    result = runner.invoke(app, ["card", "validate", str(out)])
    assert result.exit_code == 0


def test_cli_validate_invalid_card_exits_1(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"card_type": "model"}))  # missing required fields
    result = runner.invoke(app, ["card", "validate", str(bad)])
    assert result.exit_code == 1


def test_cli_validate_missing_file_exits_1(tmp_path):
    result = runner.invoke(app, ["card", "validate", str(tmp_path / "nope.json")])
    assert result.exit_code == 1


def test_cli_validate_malformed_json_exits_1(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    result = runner.invoke(app, ["card", "validate", str(bad)])
    assert result.exit_code == 1


def test_cli_validate_quiet_suppresses_output(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"card_type": "model"}))
    result = runner.invoke(app, ["card", "validate", str(bad), "--quiet"])
    assert result.exit_code == 1
    assert result.stdout.strip() == ""


# --------------------------------------------------------------------------- #
# Round trip + drift guard
# --------------------------------------------------------------------------- #


def test_export_then_validate_round_trip(tmp_path):
    out = tmp_path / "card.json"
    with patch("mltrack.cli.card_command.get_model", return_value=_make_model()):
        export = runner.invoke(app, ["card", "export", "fraud-detector", "-o", str(out)])
    validate = runner.invoke(app, ["card", "validate", str(out)])
    assert export.exit_code == 0
    assert validate.exit_code == 0


def test_bundled_schema_matches_source_of_truth():
    """The bundled schema copy must not drift from the governance-card-stack source."""
    source = (
        Path(__file__).resolve().parents[2]
        / "governance-card-stack"
        / "schemas"
        / "model-card.schema.json"
    )
    if not source.is_file():
        pytest.skip("governance-card-stack source schema not present alongside this repo")
    bundled_path = (
        Path(card_service.__file__).resolve().parent.parent
        / "schemas"
        / "model-card.schema.json"
    )
    assert json.loads(bundled_path.read_text()) == json.loads(source.read_text()), (
        "bundled model-card schema has drifted from the governance-card-stack source"
    )
