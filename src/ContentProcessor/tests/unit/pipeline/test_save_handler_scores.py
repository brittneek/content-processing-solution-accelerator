# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for ``SaveHandler._derive_aggregate_scores``.

Covers the score-derivation contract:
- probabilistic confidence flows through verbatim when available
- structural completeness fallback fires for Completed runs without logprobs
  (e.g. reasoning models / image-only flow) instead of emitting a misleading 0%
- a genuine zero is preserved as ``0.0``
- failed/empty runs return ``0.0``
"""

from __future__ import annotations

from libs.models.content_process import ContentProcess
from libs.pipeline.handlers.logics.evaluate_handler.comparison import (
    ExtractionComparisonData,
    ExtractionComparisonItem,
)
from libs.pipeline.handlers.logics.evaluate_handler.model import DataExtractionResult
from libs.pipeline.handlers.save_handler import SaveHandler


def _make_result(
    *,
    items: list[ExtractionComparisonItem],
    confidence: dict,
) -> DataExtractionResult:
    return DataExtractionResult(
        extracted_result={},
        confidence=confidence,
        comparison_result=ExtractionComparisonData(items=items),
        prompt_tokens=0,
        completion_tokens=0,
        execution_time=0,
    )


class TestProbabilisticPath:
    def test_valid_scores_flow_through(self):
        """A normal evaluate-step result must produce numeric scores."""
        items = [
            ExtractionComparisonItem(
                Field="a", Extracted="x", Confidence="90.00%", IsAboveThreshold="True"
            ),
            ExtractionComparisonItem(
                Field="b", Extracted="y", Confidence="80.00%", IsAboveThreshold="True"
            ),
            ExtractionComparisonItem(
                Field="c", Extracted="z", Confidence="0.00%", IsAboveThreshold="False"
            ),
        ]
        confidence = {
            "total_evaluated_fields_count": 3,
            "overall_confidence": 0.567,
            "min_extracted_field_confidence": 0.0,
            "zero_confidence_fields_count": 1,
        }
        entity, schema, min_score = SaveHandler._derive_aggregate_scores(
            _make_result(items=items, confidence=confidence)
        )
        assert entity == 0.567
        # 2 of 3 fields above threshold → 0.667
        assert schema == round(2 / 3, 3)
        assert min_score == 0.0

    def test_all_fields_above_threshold(self):
        items = [
            ExtractionComparisonItem(
                Field="a", Extracted="x", Confidence="95.00%", IsAboveThreshold="True"
            ),
            ExtractionComparisonItem(
                Field="b", Extracted="y", Confidence="90.00%", IsAboveThreshold="True"
            ),
        ]
        confidence = {
            "total_evaluated_fields_count": 2,
            "overall_confidence": 0.925,
            "min_extracted_field_confidence": 0.9,
            "zero_confidence_fields_count": 0,
        }
        entity, schema, min_score = SaveHandler._derive_aggregate_scores(
            _make_result(items=items, confidence=confidence)
        )
        assert entity == 0.925
        assert schema == 1.0
        assert min_score == 0.9


class TestStructuralFallback:
    """When logprobs are unavailable (reasoning model / image-only) but
    extraction succeeded, the Completed file must still get a meaningful
    numeric score based on schema completeness."""

    def test_all_fields_filled_yields_one(self):
        items = [
            ExtractionComparisonItem(
                Field="a", Extracted="x", Confidence="0.00%", IsAboveThreshold="False"
            ),
            ExtractionComparisonItem(
                Field="b", Extracted="y", Confidence="0.00%", IsAboveThreshold="False"
            ),
            ExtractionComparisonItem(
                Field="c", Extracted=42, Confidence="0.00%", IsAboveThreshold="False"
            ),
        ]
        # No probabilistic signal: total_evaluated_fields_count == 0
        confidence = {
            "total_evaluated_fields_count": 0,
            "overall_confidence": 0.0,
            "min_extracted_field_confidence": 0.0,
            "zero_confidence_fields_count": 0,
        }
        entity, schema, min_score = SaveHandler._derive_aggregate_scores(
            _make_result(items=items, confidence=confidence)
        )
        assert entity == 1.0
        assert schema == 1.0
        assert min_score == 1.0

    def test_partial_fill_yields_ratio(self):
        items = [
            ExtractionComparisonItem(
                Field="a", Extracted="x", Confidence="0.00%", IsAboveThreshold="False"
            ),
            ExtractionComparisonItem(
                Field="b", Extracted=None, Confidence="0.00%", IsAboveThreshold="False"
            ),
            ExtractionComparisonItem(
                Field="c", Extracted="", Confidence="0.00%", IsAboveThreshold="False"
            ),
            ExtractionComparisonItem(
                Field="d", Extracted="z", Confidence="0.00%", IsAboveThreshold="False"
            ),
        ]
        confidence = {"total_evaluated_fields_count": 0}
        entity, schema, min_score = SaveHandler._derive_aggregate_scores(
            _make_result(items=items, confidence=confidence)
        )
        # 2 of 4 fields actually filled → 0.5
        assert entity == 0.5
        assert schema == 0.5
        assert min_score == 0.5

    def test_all_fields_empty_yields_zero(self):
        """Genuine-empty extraction: structural fallback collapses to ``0.0``."""
        items = [
            ExtractionComparisonItem(
                Field="a", Extracted=None, Confidence="0.00%", IsAboveThreshold="False"
            ),
            ExtractionComparisonItem(
                Field="b", Extracted="", Confidence="0.00%", IsAboveThreshold="False"
            ),
            ExtractionComparisonItem(
                Field="c", Extracted="   ", Confidence="0.00%", IsAboveThreshold="False"
            ),
        ]
        confidence = {"total_evaluated_fields_count": 0}
        entity, schema, min_score = SaveHandler._derive_aggregate_scores(
            _make_result(items=items, confidence=confidence)
        )
        assert entity == 0.0
        assert schema == 0.0
        assert min_score == 0.0


class TestZeroPath:
    def test_no_comparison_items_returns_zero(self):
        """No extraction data at all (failed pipeline) → ``0.0``."""
        confidence = {
            "total_evaluated_fields_count": 0,
            "overall_confidence": 0.0,
            "min_extracted_field_confidence": 0.0,
            "zero_confidence_fields_count": 0,
        }
        entity, schema, min_score = SaveHandler._derive_aggregate_scores(
            _make_result(items=[], confidence=confidence)
        )
        assert entity == 0.0
        assert schema == 0.0
        assert min_score == 0.0

    def test_genuine_zero_probabilistic_score_preserved(self):
        """A real ``0`` confidence (every field below threshold) must NOT be
        replaced by the structural fallback — it's genuinely 0%."""
        items = [
            ExtractionComparisonItem(
                Field="a", Extracted="x", Confidence="0.00%", IsAboveThreshold="False"
            ),
        ]
        confidence = {
            "total_evaluated_fields_count": 1,
            "overall_confidence": 0.0,
            "min_extracted_field_confidence": 0.0,
            "zero_confidence_fields_count": 1,
        }
        entity, schema, min_score = SaveHandler._derive_aggregate_scores(
            _make_result(items=items, confidence=confidence)
        )
        assert entity == 0.0
        assert schema == 0.0
        assert min_score == 0.0


class TestIsFilledValue:
    """Coverage for the ``_is_filled_value`` helper used by the structural fallback."""

    def test_none_is_empty(self):
        assert SaveHandler._is_filled_value(None) is False

    def test_empty_string_is_empty(self):
        assert SaveHandler._is_filled_value("") is False
        assert SaveHandler._is_filled_value("   ") is False

    def test_non_empty_string_is_filled(self):
        assert SaveHandler._is_filled_value("x") is True

    def test_zero_int_is_filled(self):
        # A literal ``0`` is a valid extracted value (e.g. count fields).
        assert SaveHandler._is_filled_value(0) is True

    def test_bool_is_filled(self):
        assert SaveHandler._is_filled_value(False) is True
        assert SaveHandler._is_filled_value(True) is True

    def test_empty_container_is_empty(self):
        assert SaveHandler._is_filled_value([]) is False
        assert SaveHandler._is_filled_value({}) is False

    def test_nested_all_null_is_empty(self):
        assert SaveHandler._is_filled_value({"a": None, "b": ""}) is False
        assert SaveHandler._is_filled_value([None, "", {"c": None}]) is False

    def test_nested_with_value_is_filled(self):
        assert SaveHandler._is_filled_value({"a": None, "b": "x"}) is True
        assert SaveHandler._is_filled_value([None, "x"]) is True


class TestCosmosCompaction:
    def test_small_result_is_preserved(self):
        process = ContentProcess(
            process_id="small",
            status="Completed",
            result={"field": "value"},
            confidence={"field": {"confidence": 0.9, "value": "value"}},
        )

        compacted = SaveHandler._compact_for_cosmos(process)

        assert compacted.model_dump() == process.model_dump()
        assert compacted is not process

    def test_redundant_large_values_are_removed_without_mutating_full_result(self):
        repeated_value = "x" * 700_000
        process = ContentProcess(
            process_id="large",
            status="Completed",
            result={"field": repeated_value},
            confidence={
                "field": {"confidence": 0.9, "value": repeated_value},
                "overall_confidence": 0.9,
            },
            extracted_comparison_data=ExtractionComparisonData(
                items=[
                    ExtractionComparisonItem(
                        Field="field",
                        Extracted=repeated_value,
                        Confidence="90.00%",
                        IsAboveThreshold=True,
                    )
                ]
            ),
        )

        compacted = SaveHandler._compact_for_cosmos(process)

        assert SaveHandler._serialized_size_bytes(compacted) <= (
            SaveHandler.COSMOS_SAFE_DOCUMENT_SIZE_BYTES
        )
        assert compacted.result == process.result
        assert compacted.confidence == {
            "field": {"confidence": 0.9},
            "overall_confidence": 0.9,
        }
        assert process.confidence["field"]["value"] == repeated_value
        assert process.extracted_comparison_data.items[0].Extracted == repeated_value

    def test_irreducible_result_is_externalized_but_validation_is_retained(self):
        repeated_value = "x" * 1_900_000
        process = ContentProcess(
            process_id="externalized",
            status="Completed",
            result={"field": repeated_value},
            validation_result={
                "rule_set_id": "rules",
                "rule_set_version": "1",
                "summary": {},
                "entities": [
                    {
                        "entity_id": "field",
                        "name": "Field",
                        "section": "Test",
                        "status": "pass",
                        "extracted_value": "present",
                        "rule_results": [],
                    }
                ],
            },
        )

        compacted = SaveHandler._compact_for_cosmos(process)

        assert compacted.result is None
        assert compacted.validation_result["rule_set_id"] == "rules"
        assert compacted.validation_result["entities"][0]["status"] == "pass"
        assert (
            compacted.validation_result["entities"][0]["extracted_value"] == "present"
        )
        assert compacted.comment == SaveHandler.EXTERNALIZED_RESULT_COMMENT
        assert process.result == {"field": repeated_value}

    def test_large_validation_evidence_is_bounded_but_assessment_is_retained(self):
        repeated_value = "evidence " * 400_000
        process = ContentProcess(
            process_id="large-validation",
            status="Completed",
            result={"field": "present"},
            validation_result={
                "rule_set_id": "rules",
                "rule_set_version": "1",
                "overall_status": "compliant",
                "summary": {"compliant": 1},
                "entities": [
                    {
                        "entity_id": "field",
                        "name": "Field",
                        "section": "Test",
                        "status": "pass",
                        "compliance_status": "compliant",
                        "baseline": "Field must be present.",
                        "extracted_value": repeated_value,
                        "confidence": 0.9,
                        "minimum_confidence": 0.6,
                        "justification": "Evidence satisfies the baseline.",
                        "source_text": repeated_value,
                        "source_page": 2,
                        "source_regions": [
                            {
                                "page_number": 2,
                                "polygon": [
                                    {"x": 0.1, "y": 0.1},
                                    {"x": 0.2, "y": 0.1},
                                    {"x": 0.2, "y": 0.2},
                                ],
                            }
                        ],
                        "rule_results": [
                            {
                                "rule_id": "field.exists",
                                "path": "field",
                                "operator": "exists",
                                "status": "pass",
                                "severity": "high",
                                "expected": repeated_value,
                                "actual": repeated_value,
                                "message": "Field is present.",
                            }
                        ],
                    }
                ],
            },
        )

        compacted = SaveHandler._compact_for_cosmos(process)
        entity = compacted.validation_result["entities"][0]

        assert SaveHandler._serialized_size_bytes(compacted) <= (
            SaveHandler.COSMOS_SAFE_DOCUMENT_SIZE_BYTES
        )
        assert entity["compliance_status"] == "compliant"
        assert entity["baseline"] == "Field must be present."
        assert entity["justification"] == "Evidence satisfies the baseline."
        assert entity["source_page"] == 2
        assert entity["source_regions"] == []
        assert len(entity["source_text"]) < 3_000
        assert "full value stored in Blob Storage" in entity["extracted_value"]
        assert (
            "full value stored in Blob Storage" in (entity["rule_results"][0]["actual"])
        )
        assert process.validation_result["entities"][0]["source_text"] == repeated_value
