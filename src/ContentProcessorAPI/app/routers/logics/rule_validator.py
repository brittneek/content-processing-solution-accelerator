# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Validation for schema-associated YAML rule sets."""

from __future__ import annotations

from typing import Any

import yaml

_SUPPORTED_OPERATORS = {
    "exists",
    "equals",
    "not_equals",
    "minimum",
    "maximum",
    "contains",
    "contains_any",
    "contains_all",
    "one_of",
    "regex",
}


class RuleValidationError(ValueError):
    """Raised when a YAML rule set does not satisfy the supported contract."""

    def __init__(self, errors: list[str]):
        super().__init__("Invalid validation rules")
        self.errors = errors


def validate_rules_yaml(raw: bytes) -> dict[str, Any]:
    """Parse YAML safely and validate the generic rule-set structure."""

    try:
        document = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise RuleValidationError([f"Invalid YAML: {exc}"]) from exc

    errors: list[str] = []
    if not isinstance(document, dict):
        raise RuleValidationError(["Rule set must contain a YAML object."])

    for field in ("dsl_version", "rule_set_id", "name", "version", "entities"):
        if field not in document:
            errors.append(f"Missing required top-level field '{field}'.")

    entities = document.get("entities")
    if not isinstance(entities, list) or not entities:
        errors.append("'entities' must be a non-empty list.")
    else:
        for entity_index, entity in enumerate(entities):
            _validate_entity(entity, entity_index, errors)

    if errors:
        raise RuleValidationError(errors)
    return document


def _validate_entity(
    entity: Any, entity_index: int, errors: list[str]
) -> None:
    prefix = f"entities[{entity_index}]"
    if not isinstance(entity, dict):
        errors.append(f"{prefix} must be an object.")
        return

    for field in ("id", "name", "section", "rules"):
        if field not in entity:
            errors.append(f"{prefix} is missing '{field}'.")

    rules = entity.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append(f"{prefix}.rules must be a non-empty list.")
        return

    for rule_index, rule in enumerate(rules):
        rule_prefix = f"{prefix}.rules[{rule_index}]"
        if not isinstance(rule, dict):
            errors.append(f"{rule_prefix} must be an object.")
            continue
        for field in ("id", "path", "operator"):
            if field not in rule:
                errors.append(f"{rule_prefix} is missing '{field}'.")
        operator = rule.get("operator")
        if operator is not None and operator not in _SUPPORTED_OPERATORS:
            errors.append(
                f"{rule_prefix}.operator '{operator}' is not supported."
            )
