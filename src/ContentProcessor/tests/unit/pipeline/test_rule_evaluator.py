# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for the configuration-driven validation engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from libs.pipeline.handlers.logics.validate_handler import (
    RuleEvaluator,
    load_rule_set,
    parse_rule_set,
)
from libs.pipeline.handlers.logics.validate_handler.model import (
    ComplianceStatus,
    RuleSetDefinition,
    ValidationStatus,
)


@pytest.fixture
def rule_set() -> RuleSetDefinition:
    return RuleSetDefinition.model_validate(
        {
            "dsl_version": 1,
            "rule_set_id": "test-profile",
            "name": "Test profile",
            "version": "1.0.0",
            "status": "active",
            "entities": [
                {
                    "id": "engine",
                    "name": "Engine",
                    "section": "Engine",
                    "source_text_path": "engine.source_text",
                    "source_page_path": "engine.source_page",
                    "rules": [
                        {
                            "id": "engine-cooling",
                            "path": "engine.cooling_methods",
                            "operator": "contains",
                            "expected": "water_cooled",
                            "required": True,
                            "severity": "high",
                        }
                    ],
                },
                {
                    "id": "temperature",
                    "name": "Maximum temperature",
                    "section": "Environment",
                    "rules": [
                        {
                            "id": "temperature-minimum",
                            "path": "temperature.value",
                            "operator": "minimum",
                            "expected": 40,
                            "required": True,
                            "severity": "high",
                            "unit": "deg_c",
                        }
                    ],
                },
            ],
        }
    )


def test_evaluates_passing_list_and_numeric_rules(rule_set):
    result = RuleEvaluator().evaluate(
        {
            "engine": {
                "source_text": "Four-stroke, water-cooled diesel engine",
                "source_page": 12,
                "cooling_methods": ["water_cooled", "air_cooled"],
            },
            "temperature": {"value": 45},
        },
        rule_set,
    )

    assert result.summary.passed == 2
    assert result.summary.failed == 0
    assert result.entities[0].status is ValidationStatus.PASS
    assert result.entities[0].compliance_status is ComplianceStatus.COMPLIANT
    assert result.entities[0].source_page == 12


def test_reports_failed_rule_without_losing_actual_value(rule_set):
    result = RuleEvaluator().evaluate(
        {
            "engine": {"cooling_methods": ["air_cooled"]},
            "temperature": {"value": 35},
        },
        rule_set,
    )

    assert result.summary.failed == 2
    assert result.summary.noncompliant == 2
    temperature_rule = result.entities[1].rule_results[0]
    assert temperature_rule.status is ValidationStatus.FAIL
    assert temperature_rule.actual == 35
    assert temperature_rule.expected == 40


def test_reports_required_missing_value(rule_set):
    result = RuleEvaluator().evaluate({}, rule_set)

    assert result.summary.missing == 2
    assert result.summary.undetermined == 2
    assert result.entities[0].rule_results[0].status is ValidationStatus.MISSING
    assert (
        result.entities[0].rule_results[0].message
        == "Required value 'Cooling methods' (engine.cooling_methods) was not found."
    )


def test_boolean_rule_message_uses_reviewer_friendly_values():
    rules = RuleSetDefinition.model_validate(
        {
            "dsl_version": 1,
            "rule_set_id": "fuel-level",
            "name": "Fuel level",
            "version": "1.0.0",
            "status": "active",
            "entities": [
                {
                    "id": "fuel_level_monitoring",
                    "name": "Fuel-level monitoring",
                    "section": "Fuel",
                    "rules": [
                        {
                            "id": "fuel-level-transmitter",
                            "path": "fuel_level_monitoring.level_transmitter_provided",
                            "operator": "equals",
                            "expected": True,
                            "required": True,
                            "severity": "high",
                        }
                    ],
                }
            ],
        }
    )

    result = RuleEvaluator().evaluate(
        {"fuel_level_monitoring": {"level_transmitter_provided": True}},
        rules,
    )

    assert (
        result.entities[0].rule_results[0].message
        == "Level transmitter provided is Yes; required value is Yes."
    )


def test_mixed_rule_results_are_partially_compliant():
    rules = RuleSetDefinition.model_validate(
        {
            "dsl_version": 1,
            "rule_set_id": "reviewer",
            "name": "Reviewer",
            "version": "1",
            "entities": [
                {
                    "id": "engine",
                    "name": "Engine",
                    "section": "Engine",
                    "baseline": "The engine must be turbocharged and aftercooled.",
                    "rules": [
                        {
                            "id": "turbo",
                            "path": "engine.turbocharged",
                            "operator": "equals",
                            "expected": True,
                            "required": True,
                        },
                        {
                            "id": "aftercooled",
                            "path": "engine.aftercooled",
                            "operator": "equals",
                            "expected": True,
                            "required": True,
                        },
                    ],
                }
            ],
        }
    )

    result = RuleEvaluator().evaluate(
        {"engine": {"turbocharged": True, "aftercooled": False}},
        rules,
    )

    entity = result.entities[0]
    assert entity.compliance_status is ComplianceStatus.PARTIALLY_COMPLIANT
    assert entity.baseline == "The engine must be turbocharged and aftercooled."
    assert entity.extracted_value == {
        "engine.turbocharged": True,
        "engine.aftercooled": False,
    }
    assert "partially satisfies" in entity.justification


def test_low_confidence_is_undetermined():
    rules = RuleSetDefinition.model_validate(
        {
            "dsl_version": 1,
            "rule_set_id": "reviewer",
            "name": "Reviewer",
            "version": "1",
            "minimum_confidence": 0.6,
            "entities": [
                {
                    "id": "engine",
                    "name": "Engine",
                    "section": "Engine",
                    "baseline": "The engine must be turbocharged.",
                    "rules": [
                        {
                            "id": "turbo",
                            "path": "engine.turbocharged",
                            "operator": "equals",
                            "expected": True,
                            "required": True,
                        }
                    ],
                }
            ],
        }
    )

    result = RuleEvaluator().evaluate(
        {"engine": {"turbocharged": True}},
        rules,
        {"engine": {"turbocharged": {"confidence": 0.42, "value": True}}},
    )

    entity = result.entities[0]
    assert entity.status is ValidationStatus.PASS
    assert entity.compliance_status is ComplianceStatus.UNDETERMINED
    assert entity.confidence == 0.42
    assert "below the configured 60% threshold" in entity.justification


def test_optional_missing_value_is_not_applicable():
    rules = RuleSetDefinition.model_validate(
        {
            "dsl_version": 1,
            "rule_set_id": "optional",
            "name": "Optional",
            "version": "1",
            "entities": [
                {
                    "id": "optional",
                    "name": "Optional",
                    "section": "Test",
                    "rules": [
                        {
                            "id": "optional-rule",
                            "path": "optional.value",
                            "operator": "equals",
                            "expected": True,
                        }
                    ],
                }
            ],
        }
    )

    result = RuleEvaluator().evaluate({}, rules)

    assert result.summary.not_applicable == 1


def test_conditional_rule_applies_when_condition_matches():
    rules = RuleSetDefinition.model_validate(
        {
            "dsl_version": 1,
            "rule_set_id": "conditional",
            "name": "Conditional",
            "version": "1",
            "entities": [
                {
                    "id": "tank",
                    "name": "Tank",
                    "section": "Fuel",
                    "rules": [
                        {
                            "id": "retail-runtime",
                            "path": "tank.runtime_hours",
                            "operator": "minimum",
                            "expected": 30,
                            "required": True,
                            "when": [
                                {
                                    "path": "document.product_line",
                                    "operator": "one_of",
                                    "expected": ["Retail", "Both"],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    result = RuleEvaluator().evaluate(
        {
            "document": {"product_line": "Retail"},
            "tank": {"runtime_hours": 32},
        },
        rules,
    )

    assert result.entities[0].status is ValidationStatus.PASS


def test_conditional_rule_is_not_applicable_when_condition_does_not_match():
    rules = RuleSetDefinition.model_validate(
        {
            "dsl_version": 1,
            "rule_set_id": "conditional",
            "name": "Conditional",
            "version": "1",
            "entities": [
                {
                    "id": "tank",
                    "name": "Tank",
                    "section": "Fuel",
                    "rules": [
                        {
                            "id": "retail-runtime",
                            "path": "tank.runtime_hours",
                            "operator": "minimum",
                            "expected": 30,
                            "required": True,
                            "when": [
                                {
                                    "path": "document.product_line",
                                    "operator": "equals",
                                    "expected": "Retail",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    result = RuleEvaluator().evaluate(
        {
            "document": {"product_line": "xScale"},
            "tank": {"runtime_hours": 20},
        },
        rules,
    )

    assert result.entities[0].status is ValidationStatus.NOT_APPLICABLE


def test_conditional_rule_is_not_applicable_when_condition_value_is_missing():
    rules = RuleSetDefinition.model_validate(
        {
            "dsl_version": 1,
            "rule_set_id": "conditional",
            "name": "Conditional",
            "version": "1",
            "entities": [
                {
                    "id": "tank",
                    "name": "Tank",
                    "section": "Fuel",
                    "rules": [
                        {
                            "id": "runtime",
                            "path": "tank.runtime_hours",
                            "operator": "minimum",
                            "expected": 30,
                            "required": True,
                            "when": [
                                {
                                    "path": "document.product_line",
                                    "operator": "equals",
                                    "expected": "Retail",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    result = RuleEvaluator().evaluate(
        {"tank": {"runtime_hours": 20}},
        rules,
    )

    assert result.entities[0].status is ValidationStatus.NOT_APPLICABLE


def test_invalid_conditional_comparison_returns_error():
    rules = RuleSetDefinition.model_validate(
        {
            "dsl_version": 1,
            "rule_set_id": "conditional",
            "name": "Conditional",
            "version": "1",
            "entities": [
                {
                    "id": "tank",
                    "name": "Tank",
                    "section": "Fuel",
                    "rules": [
                        {
                            "id": "runtime",
                            "path": "tank.runtime_hours",
                            "operator": "minimum",
                            "expected": 30,
                            "required": True,
                            "when": [
                                {
                                    "path": "document.capacity",
                                    "operator": "minimum",
                                    "expected": 100,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    result = RuleEvaluator().evaluate(
        {
            "document": {"capacity": "unknown"},
            "tank": {"runtime_hours": 30},
        },
        rules,
    )

    assert result.entities[0].status is ValidationStatus.ERROR


@pytest.mark.parametrize(
    ("operator", "expected", "actual", "expected_status"),
    [
        ("equals", "diesel", "diesel", ValidationStatus.PASS),
        ("not_equals", "gas", "diesel", ValidationStatus.PASS),
        ("contains_any", ["water", "air"], ["air"], ValidationStatus.PASS),
        ("contains_all", ["four_stroke", "diesel"], ["diesel"], ValidationStatus.FAIL),
        (
            "contains_all",
            [
                {"load_percent": 50, "with_fan": True},
                {"load_percent": 100, "with_fan": True},
            ],
            [
                {"load_percent": 50, "with_fan": True, "value": 10},
                {"load_percent": 100, "with_fan": True, "value": 20},
            ],
            ValidationStatus.PASS,
        ),
        ("one_of", ["diesel", "gas"], "diesel", ValidationStatus.PASS),
        ("regex", r"^Tier [3-5]$", "Tier 3", ValidationStatus.PASS),
        ("maximum", -35, -40, ValidationStatus.PASS),
        ("minimum", 40, 40, ValidationStatus.PASS),
    ],
)
def test_supported_operators(operator, expected, actual, expected_status):
    rules = RuleSetDefinition.model_validate(
        {
            "dsl_version": 1,
            "rule_set_id": "operators",
            "name": "Operators",
            "version": "1",
            "entities": [
                {
                    "id": "value",
                    "name": "Value",
                    "section": "Test",
                    "rules": [
                        {
                            "id": "operator-rule",
                            "path": "value",
                            "operator": operator,
                            "expected": expected,
                            "required": True,
                        }
                    ],
                }
            ],
        }
    )

    result = RuleEvaluator().evaluate({"value": actual}, rules)

    assert result.entities[0].status is expected_status


def test_exclusive_numeric_bound():
    rules = RuleSetDefinition.model_validate(
        {
            "dsl_version": 1,
            "rule_set_id": "exclusive",
            "name": "Exclusive",
            "version": "1",
            "entities": [
                {
                    "id": "efficiency",
                    "name": "Efficiency",
                    "section": "Test",
                    "rules": [
                        {
                            "id": "efficiency-rule",
                            "path": "efficiency",
                            "operator": "minimum",
                            "expected": 90,
                            "exclusive": True,
                            "required": True,
                        }
                    ],
                }
            ],
        }
    )

    result = RuleEvaluator().evaluate({"efficiency": 90}, rules)

    assert result.entities[0].status is ValidationStatus.FAIL


def test_invalid_numeric_type_returns_explicit_error(rule_set):
    result = RuleEvaluator().evaluate(
        {
            "engine": {"cooling_methods": ["water_cooled"]},
            "temperature": {"value": "forty"},
        },
        rule_set,
    )

    assert result.summary.errors == 1
    assert result.entities[1].status is ValidationStatus.ERROR
    assert "must be numeric" in result.entities[1].rule_results[0].message


def test_load_rule_set_validates_yaml(tmp_path: Path):
    path = tmp_path / "rules.yaml"
    path.write_text(
        """
dsl_version: 1
rule_set_id: sample
name: Sample
version: 1.0.0
entities:
  - id: value
    name: Value
    section: Test
    rules:
      - id: value-required
        path: value
        operator: exists
        required: true
""",
        encoding="utf-8",
    )

    loaded = load_rule_set(path)

    assert loaded.rule_set_id == "sample"


def test_load_rule_set_rejects_non_object_yaml(tmp_path: Path):
    path = tmp_path / "rules.yaml"
    path.write_text("- not\n- an\n- object\n", encoding="utf-8")

    with pytest.raises(TypeError, match="must contain a YAML object"):
        load_rule_set(path)


def test_parse_rule_set_accepts_runtime_yaml_bytes():
    loaded = parse_rule_set(
        b"""
dsl_version: 1
rule_set_id: runtime
name: Runtime
version: 1.0.0
entities:
  - id: value
    name: Value
    section: Test
    rules:
      - id: value-required
        path: value
        operator: exists
        required: true
"""
    )

    assert loaded.rule_set_id == "runtime"
