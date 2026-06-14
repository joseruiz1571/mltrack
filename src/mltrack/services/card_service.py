"""Governance Model Card export and validation.

Maps an mltrack ``AIModel`` inventory record onto the Governance Card Stack
Model Card schema (``governance-card-stack/schemas/model-card.schema.json``),
producing a portable, schema-valid governance artifact. This is the bridge from
mltrack (the inventory layer) to the card stack (the spec layer).

Validation prefers the ``jsonschema`` library when it is importable (the
authoritative JSON Schema validator) and falls back to a minimal built-in
checker that enforces this schema's required / type / const / enum / pattern /
additionalProperties constraints, so ``mltrack card validate`` works with zero
extra runtime dependencies. Install the authoritative validator with the
optional extra: ``pip install 'mltrack[card]'``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mltrack.models.ai_model import AIModel, ModelStatus, RiskTier

# Pinned to the Governance Card Stack model-card schema this maps onto.
CARD_SPEC_VERSION = "0.1.0"

# mltrack lifecycle status -> Model Card lifecycle_status enum.
_LIFECYCLE_MAP = {
    ModelStatus.ACTIVE: "active",
    ModelStatus.DEPRECATED: "deprecated",
    ModelStatus.DECOMMISSIONED: "retired",
}

# Review cadence (days) by risk tier — surfaced in the card's governance block.
_REVIEW_DAYS = {
    RiskTier.CRITICAL: 30,
    RiskTier.HIGH: 90,
    RiskTier.MEDIUM: 180,
    RiskTier.LOW: 365,
}

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "model-card.schema.json"


class CardValidationError(Exception):
    """Raised when a card fails schema validation.

    ``errors`` holds the list of human-readable validation messages.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def load_schema() -> dict[str, Any]:
    """Load the bundled Governance Model Card schema."""
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def model_to_card(model: AIModel) -> dict[str, Any]:
    """Build a schema-valid Governance Model Card dict from an ``AIModel``."""
    metadata: dict[str, Any] = {
        # AIModel.id is generated as a uuid4 string -> satisfies the schema's v4 pattern.
        "uuid": model.id,
        "name": model.model_name,
        "version": model.model_version or "unversioned",
        "description": model.use_case,
        "owners": [
            {"name": model.business_owner, "role": "business"},
            {"name": model.technical_owner, "role": "technical"},
        ],
        "lifecycle_status": _LIFECYCLE_MAP.get(model.status, "active"),
    }

    classification: dict[str, Any] = {"risk_tier": model.risk_tier.value}
    if model.data_classification is not None:
        classification["data_classification"] = model.data_classification.value
    if model.deployment_environment is not None:
        classification["environment"] = model.deployment_environment.value

    model_block: dict[str, Any] = {
        "provider": model.vendor,
        "name": model.model_name,
        "intended_use": model.use_case,
    }
    if model.model_version:
        model_block["version"] = model.model_version

    governance: dict[str, Any] = {
        "review_cycle_days": _REVIEW_DAYS[model.risk_tier],
        "last_review": model.last_review_date.isoformat() if model.last_review_date else None,
        "next_review_due": model.next_review_date.isoformat() if model.next_review_date else None,
        "deployment_date": model.deployment_date.isoformat() if model.deployment_date else None,
    }
    if model.api_endpoint:
        governance["api_endpoint"] = model.api_endpoint
    if model.notes:
        governance["notes"] = model.notes

    return {
        "spec_version": CARD_SPEC_VERSION,
        "card_type": "model",
        "metadata": metadata,
        "classification": classification,
        "model": model_block,
        "governance": governance,
        # mltrack is the inventory layer; the evidence[] slot is populated by the
        # assurance layer (mlassure). Present-but-empty marks the contract.
        "evidence": [],
    }


def validate_card(card: Any) -> list[str]:
    """Validate a card against the Model Card schema.

    Returns a list of human-readable error strings (empty list == valid).
    Uses ``jsonschema`` when importable, else a minimal built-in checker.
    """
    schema = load_schema()
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return _minimal_validate(card, schema)

    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in err.path) or '(root)'}: {err.message}"
        for err in sorted(validator.iter_errors(card), key=lambda e: list(e.path))
    ]


_TYPE_MAP: dict[str, Any] = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def _minimal_validate(instance: Any, schema: dict[str, Any], path: str = "") -> list[str]:
    """A minimal JSON-Schema-subset validator faithful to the Model Card schema.

    Enforces type, required, const, enum, pattern, additionalProperties, and
    recurses through properties/items. Not a full JSON Schema implementation;
    the ``jsonschema`` library is the authoritative path when available.
    """
    errors: list[str] = []
    loc = path or "(root)"

    expected = schema.get("type")
    if expected is not None:
        if expected == "integer" and isinstance(instance, bool):
            errors.append(f"{loc}: expected integer, got boolean")
        else:
            py = _TYPE_MAP.get(expected)
            # Guard: bool is a subclass of int; reject bools where number expected.
            if expected == "number" and isinstance(instance, bool):
                errors.append(f"{loc}: expected number, got boolean")
            elif py is not None and not isinstance(instance, py):
                errors.append(f"{loc}: expected {expected}, got {type(instance).__name__}")
                return errors

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{loc}: must equal {schema['const']!r}")

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{loc}: {instance!r} is not one of {schema['enum']}")

    if "pattern" in schema and isinstance(instance, str):
        if re.search(schema["pattern"], instance) is None:
            errors.append(f"{loc}: {instance!r} does not match pattern {schema['pattern']}")

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{loc}: missing required property '{req}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{loc}: additional property '{key}' is not allowed")
        for key, subschema in props.items():
            if key in instance and isinstance(subschema, dict):
                child = f"{path}/{key}" if path else key
                errors.extend(_minimal_validate(instance[key], subschema, child))

    if isinstance(instance, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for idx, element in enumerate(instance):
                errors.extend(_minimal_validate(element, items, f"{loc}[{idx}]"))

    return errors
