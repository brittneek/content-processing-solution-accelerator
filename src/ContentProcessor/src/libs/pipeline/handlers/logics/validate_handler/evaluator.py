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
    ComplianceStatus,
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
        self,
        extracted_result: Mapping[str, Any],
        rule_set: RuleSetDefinition,
        confidence_result: Mapping[str, Any] | None = None,
    ) -> ValidationResult:
        """Evaluate all configured entities and return a status summary."""

        entities = [
            self._evaluate_entity(
                extracted_result,
                confidence_result or {},
                entity,
                rule_set.minimum_confidence,
            )
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
            compliance_fields = {
                ComplianceStatus.COMPLIANT: "compliant",
                ComplianceStatus.PARTIALLY_COMPLIANT: "partially_compliant",
                ComplianceStatus.NONCOMPLIANT: "noncompliant",
                ComplianceStatus.UNDETERMINED: "undetermined",
                ComplianceStatus.NOT_APPLICABLE: "compliance_not_applicable",
                ComplianceStatus.REVIEW_REQUIRED: "review_required",
            }
            compliance_field = compliance_fields[entity.compliance_status]
            setattr(
                summary,
                compliance_field,
                getattr(summary, compliance_field) + 1,
            )

        return ValidationResult(
            rule_set_id=rule_set.rule_set_id,
            rule_set_version=rule_set.version,
            overall_status=self._overall_status(entities),
            summary=summary,
            entities=entities,
        )

    def _evaluate_entity(
        self,
        extracted_result: Mapping[str, Any],
        confidence_result: Mapping[str, Any],
        entity: EntityDefinition,
        rule_set_minimum_confidence: float | None,
    ) -> EntityValidationResult:
        rule_results = [
            self._evaluate_rule(extracted_result, rule) for rule in entity.rules
        ]
        raw_status = self._roll_up_status(rule_results)
        confidence = self._entity_confidence(confidence_result, entity)
        minimum_confidence = (
            entity.minimum_confidence
            if entity.minimum_confidence is not None
            else rule_set_minimum_confidence
        )
        compliance_status = self._compliance_status(
            rule_results,
            confidence,
            minimum_confidence,
        )
        baseline = entity.baseline or entity.name
        return EntityValidationResult(
            entity_id=entity.id,
            name=entity.name,
            section=entity.section,
            status=raw_status,
            compliance_status=compliance_status,
            baseline=baseline,
            extracted_value=self._extracted_value(rule_results),
            confidence=confidence,
            minimum_confidence=minimum_confidence,
            justification=self._justification(
                baseline,
                compliance_status,
                rule_results,
                confidence,
                minimum_confidence,
            ),
            source_text=self._optional_value(
                extracted_result, entity.source_text_path, str
            ),
            source_page=self._optional_value(
                extracted_result, entity.source_page_path, int
            ),
            rule_results=rule_results,
        )

    @classmethod
    def _entity_confidence(
        cls,
        confidence_result: Mapping[str, Any],
        entity: EntityDefinition,
    ) -> float | None:
        paths = [rule.path for rule in entity.rules]
        if entity.source_text_path:
            paths.append(entity.source_text_path)
        values = [
            value
            for path in paths
            if (value := cls._confidence_for_path(confidence_result, path)) is not None
        ]
        return min(values) if values else None

    @classmethod
    def _confidence_for_path(
        cls,
        confidence_result: Mapping[str, Any],
        path: str,
    ) -> float | None:
        node: Any = confidence_result
        for segment in path.split("."):
            if not isinstance(node, Mapping) or segment not in node:
                return None
            node = node[segment]
        if isinstance(node, Mapping):
            confidence = node.get("confidence")
            if (
                isinstance(confidence, Real)
                and not isinstance(confidence, bool)
                and math.isfinite(float(confidence))
                and float(confidence) > 0
            ):
                return max(0.0, min(1.0, float(confidence)))
            nested = cls._collect_confidence(node)
            return min(nested) if nested else None
        return None

    @classmethod
    def _collect_confidence(cls, node: Any) -> list[float]:
        values: list[float] = []
        if isinstance(node, Mapping):
            confidence = node.get("confidence")
            if (
                isinstance(confidence, Real)
                and not isinstance(confidence, bool)
                and math.isfinite(float(confidence))
                and float(confidence) > 0
            ):
                values.append(max(0.0, min(1.0, float(confidence))))
            for value in node.values():
                if isinstance(value, (Mapping, list)):
                    values.extend(cls._collect_confidence(value))
        elif isinstance(node, list):
            for value in node:
                values.extend(cls._collect_confidence(value))
        return values

    @staticmethod
    def _compliance_status(
        rule_results: list[RuleResult],
        confidence: float | None,
        minimum_confidence: float | None,
    ) -> ComplianceStatus:
        statuses = [result.status for result in rule_results]
        applicable = [
            status
            for status in statuses
            if status is not ValidationStatus.NOT_APPLICABLE
        ]
        if not applicable:
            return ComplianceStatus.NOT_APPLICABLE
        if ValidationStatus.ERROR in applicable:
            return ComplianceStatus.REVIEW_REQUIRED
        if (
            confidence is not None
            and minimum_confidence is not None
            and confidence < minimum_confidence
        ):
            return ComplianceStatus.UNDETERMINED

        has_pass = ValidationStatus.PASS in applicable
        has_fail = ValidationStatus.FAIL in applicable
        has_missing = ValidationStatus.MISSING in applicable
        if has_pass and has_fail:
            return ComplianceStatus.PARTIALLY_COMPLIANT
        if has_fail:
            return ComplianceStatus.NONCOMPLIANT
        if has_missing:
            return ComplianceStatus.UNDETERMINED
        return ComplianceStatus.COMPLIANT

    @staticmethod
    def _extracted_value(rule_results: list[RuleResult]) -> Any:
        applicable = [
            result
            for result in rule_results
            if result.status is not ValidationStatus.NOT_APPLICABLE
        ]
        if len(applicable) == 1:
            return applicable[0].actual
        return {
            result.path: result.actual
            for result in applicable
            if result.actual is not None
        }

    @staticmethod
    def _justification(
        baseline: str,
        status: ComplianceStatus,
        rule_results: list[RuleResult],
        confidence: float | None,
        minimum_confidence: float | None,
    ) -> str:
        if (
            confidence is not None
            and minimum_confidence is not None
            and confidence < minimum_confidence
        ):
            return (
                f"Unable to determine compliance with '{baseline}' because "
                f"extraction confidence {confidence:.0%} is below the configured "
                f"{minimum_confidence:.0%} threshold."
            )

        messages = [
            result.message
            for result in rule_results
            if result.status
            in {
                ValidationStatus.FAIL,
                ValidationStatus.MISSING,
                ValidationStatus.ERROR,
            }
        ]
        if status is ComplianceStatus.COMPLIANT:
            return f"Extracted evidence satisfies the baseline: {baseline}"
        if status is ComplianceStatus.PARTIALLY_COMPLIANT:
            return (
                f"Extracted evidence only partially satisfies '{baseline}' "
                + " ".join(messages)
            )
        if status is ComplianceStatus.NONCOMPLIANT:
            return (
                f"Extracted evidence conflicts with the baseline '{baseline}' "
                + " ".join(messages)
            )
        if status is ComplianceStatus.UNDETERMINED:
            return f"Compliance with '{baseline}' could not be determined. " + " ".join(
                messages
            )
        if status is ComplianceStatus.REVIEW_REQUIRED:
            return f"Compliance with '{baseline}' requires manual review. " + " ".join(
                messages
            )
        return f"The baseline does not apply: {baseline}"

    @staticmethod
    def _overall_status(
        entities: list[EntityValidationResult],
    ) -> ComplianceStatus:
        statuses = {entity.compliance_status for entity in entities}
        for status in (
            ComplianceStatus.REVIEW_REQUIRED,
            ComplianceStatus.NONCOMPLIANT,
            ComplianceStatus.PARTIALLY_COMPLIANT,
            ComplianceStatus.UNDETERMINED,
            ComplianceStatus.COMPLIANT,
        ):
            if status in statuses:
                return status
        return ComplianceStatus.NOT_APPLICABLE

    def _evaluate_rule(
        self, extracted_result: Mapping[str, Any], rule: RuleDefinition
    ) -> RuleResult:
        condition_result = self._conditions_apply(extracted_result, rule)
        if condition_result is not None:
            return condition_result

        actual = self._resolve_path(extracted_result, rule.path)
        if self._is_missing(actual):
            field_name = self._field_name(rule.path)
            status = (
                ValidationStatus.MISSING
                if rule.required
                else ValidationStatus.NOT_APPLICABLE
            )
            message = (
                f"Required value '{field_name}' ({rule.path}) was not found."
                if rule.required
                else f"Optional value '{field_name}' ({rule.path}) was not found."
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

    def _conditions_apply(
        self,
        extracted_result: Mapping[str, Any],
        rule: RuleDefinition,
    ) -> RuleResult | None:
        for condition in rule.when:
            actual = self._resolve_path(extracted_result, condition.path)
            if self._is_missing(actual):
                return self._result(
                    rule,
                    ValidationStatus.NOT_APPLICABLE,
                    None,
                    f"Rule does not apply because '{condition.path}' was not found.",
                )
            try:
                applies = self._apply_operator_values(
                    condition.operator,
                    actual,
                    condition.expected,
                    condition.exclusive,
                )
            except (TypeError, ValueError, re.error) as exc:
                return self._result(
                    rule,
                    ValidationStatus.ERROR,
                    actual,
                    f"Could not evaluate condition '{condition.path}': {exc}",
                )
            if not applies:
                return self._result(
                    rule,
                    ValidationStatus.NOT_APPLICABLE,
                    actual,
                    "Rule does not apply because condition "
                    f"'{condition.path}' was not satisfied.",
                )
        return None

    def _apply_operator(self, rule: RuleDefinition, actual: Any) -> bool:
        return self._apply_operator_values(
            rule.operator,
            actual,
            rule.expected,
            rule.exclusive,
        )

    def _apply_operator_values(
        self,
        operator: RuleOperator,
        actual: Any,
        expected: Any,
        exclusive: bool = False,
    ) -> bool:
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
                if exclusive
                else actual_number >= expected_number
            )
        if operator is RuleOperator.MAXIMUM:
            actual_number = self._number(actual, "actual")
            expected_number = self._number(expected, "expected")
            return (
                actual_number < expected_number
                if exclusive
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
        if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
            value, Collection
        ):
            raise TypeError(f"{label} value must be a list-like collection")
        return value

    @classmethod
    def _contains(cls, actual: Any, expected: Any) -> bool:
        if isinstance(actual, str):
            if not isinstance(expected, str):
                raise TypeError("string containment requires a string expected value")
            return expected in actual
        collection = cls._collection(actual, "actual")
        if isinstance(expected, Mapping):
            return any(
                isinstance(item, Mapping)
                and all(
                    item.get(key, _MISSING) == value for key, value in expected.items()
                )
                for item in collection
            )
        return expected in collection

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
    def _default_message(rule: RuleDefinition, actual: Any, passed: bool) -> str:
        field_name = RuleEvaluator._field_name(rule.path)
        actual_value = RuleEvaluator._display_value(actual, rule.unit)
        expected_value = RuleEvaluator._display_value(rule.expected, rule.unit)

        if rule.operator is RuleOperator.EQUALS:
            return (
                f"{field_name} is {actual_value}; required value is {expected_value}."
            )
        if rule.operator is RuleOperator.MINIMUM:
            return (
                f"{field_name} is {actual_value}; minimum required is {expected_value}."
            )
        if rule.operator is RuleOperator.MAXIMUM:
            return (
                f"{field_name} is {actual_value}; maximum allowed is {expected_value}."
            )
        if rule.operator is RuleOperator.EXISTS:
            return (
                f"{field_name} is provided."
                if passed
                else f"{field_name} was not provided."
            )

        outcome = "satisfies" if passed else "does not satisfy"
        return (
            f"{field_name} ({actual_value}) {outcome} the "
            f"{rule.operator.value.replace('_', ' ')} requirement "
            f"({expected_value})."
        )

    @staticmethod
    def _field_name(path: str) -> str:
        return path.rsplit(".", 1)[-1].replace("_", " ").capitalize()

    @staticmethod
    def _display_value(value: Any, unit: str | None = None) -> str:
        if isinstance(value, bool):
            formatted = "Yes" if value else "No"
        elif value is None:
            formatted = "not provided"
        else:
            formatted = str(value)
        return f"{formatted} {unit}" if unit else formatted
