# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Generic evaluation of extracted values against external rules."""

from __future__ import annotations

import math
import re
from collections.abc import Collection, Mapping
from numbers import Real
from typing import Any

from libs.pipeline.handlers.logics.validate_handler.model import (
    EntityDefinition,
    EntityValidationResult,
    RuleDefinition,
    RuleOperator,
    RuleResult,
    RuleSetDefinition,
    ValidationResult,
    ValidationStatus,
    ValidationSummary,
)

_MISSING = object()


class RuleEvaluator:
    """Evaluate extracted document data without domain-specific logic."""

    def evaluate(
        self, extracted_result: Mapping[str, Any], rule_set: RuleSetDefinition
    ) -> ValidationResult:
        """Evaluate all configured entities and return a status summary."""

        entities = [
            self._evaluate_entity(extracted_result, entity)
            for entity in rule_set.entities
        ]
        summary = ValidationSummary()
        summary_fields = {
            ValidationStatus.PASS: "passed",
            ValidationStatus.FAIL: "failed",
            ValidationStatus.MISSING: "missing",
            ValidationStatus.NOT_APPLICABLE: "not_applicable",
            ValidationStatus.ERROR: "errors",
        }
        for entity in entities:
            field = summary_fields[entity.status]
            setattr(summary, field, getattr(summary, field) + 1)

        return ValidationResult(
            rule_set_id=rule_set.rule_set_id,
            rule_set_version=rule_set.version,
            summary=summary,
            entities=entities,
        )

    def _evaluate_entity(
        self, extracted_result: Mapping[str, Any], entity: EntityDefinition
    ) -> EntityValidationResult:
        rule_results = [
            self._evaluate_rule(extracted_result, rule) for rule in entity.rules
        ]
        return EntityValidationResult(
            entity_id=entity.id,
            name=entity.name,
            section=entity.section,
            status=self._roll_up_status(rule_results),
            source_text=self._optional_value(
                extracted_result, entity.source_text_path, str
            ),
            source_page=self._optional_value(
                extracted_result, entity.source_page_path, int
            ),
            rule_results=rule_results,
        )

    def _evaluate_rule(
        self, extracted_result: Mapping[str, Any], rule: RuleDefinition
    ) -> RuleResult:
        actual = self._resolve_path(extracted_result, rule.path)
        if self._is_missing(actual):
            status = (
                ValidationStatus.MISSING
                if rule.required
                else ValidationStatus.NOT_APPLICABLE
            )
            message = (
                f"Required value '{rule.path}' was not found."
                if rule.required
                else f"Optional value '{rule.path}' was not found."
            )
            return self._result(rule, status, None, message)

        try:
            passed = self._apply_operator(rule, actual)
        except (TypeError, ValueError, re.error) as exc:
            return self._result(
                rule,
                ValidationStatus.ERROR,
                actual,
                f"Could not evaluate '{rule.path}': {exc}",
            )

        status = ValidationStatus.PASS if passed else ValidationStatus.FAIL
        message = rule.message or self._default_message(rule, actual, passed)
        return self._result(rule, status, actual, message)

    def _apply_operator(self, rule: RuleDefinition, actual: Any) -> bool:
        operator = rule.operator
        expected = rule.expected

        if operator is RuleOperator.EXISTS:
            return not self._is_missing(actual)
        if operator is RuleOperator.EQUALS:
            return actual == expected
        if operator is RuleOperator.NOT_EQUALS:
            return actual != expected
        if operator is RuleOperator.MINIMUM:
            actual_number = self._number(actual, "actual")
            expected_number = self._number(expected, "expected")
            return (
                actual_number > expected_number
                if rule.exclusive
                else actual_number >= expected_number
            )
        if operator is RuleOperator.MAXIMUM:
            actual_number = self._number(actual, "actual")
            expected_number = self._number(expected, "expected")
            return (
                actual_number < expected_number
                if rule.exclusive
                else actual_number <= expected_number
            )
        if operator is RuleOperator.CONTAINS:
            return self._contains(actual, expected)
        if operator is RuleOperator.CONTAINS_ANY:
            expected_values = self._collection(expected, "expected")
            return any(self._contains(actual, item) for item in expected_values)
        if operator is RuleOperator.CONTAINS_ALL:
            expected_values = self._collection(expected, "expected")
            return all(self._contains(actual, item) for item in expected_values)
        if operator is RuleOperator.ONE_OF:
            return actual in self._collection(expected, "expected")
        if operator is RuleOperator.REGEX:
            if not isinstance(actual, str) or not isinstance(expected, str):
                raise TypeError("regex requires string actual and expected values")
            return re.search(expected, actual) is not None

        raise ValueError(f"Unsupported operator '{operator}'")

    @staticmethod
    def _resolve_path(data: Mapping[str, Any], path: str) -> Any:
        value: Any = data
        for segment in path.split("."):
            if not isinstance(value, Mapping) or segment not in value:
                return _MISSING
            value = value[segment]
        return value

    @staticmethod
    def _is_missing(value: Any) -> bool:
        return value is _MISSING or value is None or value == "" or value == []

    @staticmethod
    def _number(value: Any, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"{label} value must be numeric")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{label} value must be finite")
        return number

    @staticmethod
    def _collection(value: Any, label: str) -> Collection[Any]:
        if (
            isinstance(value, (str, bytes, bytearray, Mapping))
            or not isinstance(value, Collection)
        ):
            raise TypeError(f"{label} value must be a list-like collection")
        return value

    @classmethod
    def _contains(cls, actual: Any, expected: Any) -> bool:
        if isinstance(actual, str):
            if not isinstance(expected, str):
                raise TypeError("string containment requires a string expected value")
            return expected in actual
        return expected in cls._collection(actual, "actual")

    @classmethod
    def _optional_value(
        cls,
        data: Mapping[str, Any],
        path: str | None,
        expected_type: type,
    ) -> Any:
        if path is None:
            return None
        value = cls._resolve_path(data, path)
        if cls._is_missing(value) or not isinstance(value, expected_type):
            return None
        return value

    @staticmethod
    def _roll_up_status(rule_results: list[RuleResult]) -> ValidationStatus:
        statuses = {result.status for result in rule_results}
        for status in (
            ValidationStatus.ERROR,
            ValidationStatus.FAIL,
            ValidationStatus.MISSING,
            ValidationStatus.PASS,
        ):
            if status in statuses:
                return status
        return ValidationStatus.NOT_APPLICABLE

    @staticmethod
    def _result(
        rule: RuleDefinition,
        status: ValidationStatus,
        actual: Any,
        message: str,
    ) -> RuleResult:
        return RuleResult(
            rule_id=rule.id,
            path=rule.path,
            operator=rule.operator,
            status=status,
            severity=rule.severity,
            expected=rule.expected,
            actual=actual,
            unit=rule.unit,
            message=message,
        )

    @staticmethod
    def _default_message(
        rule: RuleDefinition, actual: Any, passed: bool
    ) -> str:
        outcome = "satisfied" if passed else "did not satisfy"
        return (
            f"Value {actual!r} {outcome} {rule.operator.value} "
            f"requirement {rule.expected!r}."
        )
