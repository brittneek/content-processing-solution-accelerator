# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for validation source-evidence polygon resolution."""

from libs.azure_helper.model.content_understanding import DocumentContent
from libs.pipeline.handlers.logics.validate_handler import (
    RuleEvaluator,
    parse_rule_set,
    resolve_validation_evidence,
)


def _document() -> DocumentContent:
    return DocumentContent(
        markdown="Maximum ambient temperature shall be 35 C.",
        kind="document",
        startPageNumber=1,
        endPageNumber=2,
        unit="inch",
        pages=[
            {
                "pageNumber": 1,
                "width": 10,
                "height": 20,
                "spans": [],
                "words": [],
                "lines": [],
            },
            {
                "pageNumber": 2,
                "width": 10,
                "height": 20,
                "spans": [{"offset": 0, "length": 42}],
                "words": [
                    {
                        "content": "Maximum",
                        "span": {"offset": 0, "length": 7},
                        "confidence": 0.98,
                        "source": "D(2, 1, 2, 3, 2, 3, 3, 1, 3)",
                    },
                    {
                        "content": "ambient",
                        "span": {"offset": 8, "length": 7},
                        "confidence": 0.97,
                        "source": "D(2, 3, 2, 5, 2, 5, 3, 3, 3)",
                    },
                    {
                        "content": "temperature",
                        "span": {"offset": 16, "length": 11},
                        "confidence": 0.96,
                        "source": "D(2, 5, 2, 7, 2, 7, 3, 5, 3)",
                    },
                    {
                        "content": "shall",
                        "span": {"offset": 28, "length": 5},
                        "confidence": 0.95,
                        "source": "D(2, 1, 4, 2, 4, 2, 5, 1, 5)",
                    },
                    {
                        "content": "be 35 C.",
                        "span": {"offset": 34, "length": 8},
                        "confidence": 0.94,
                        "source": "D(2, 2, 4, 4, 4, 4, 5, 2, 5)",
                    },
                ],
                "lines": [
                    {
                        "content": "Maximum ambient temperature",
                        "source": "D(2, 1, 2, 7, 2, 7, 3, 1, 3)",
                        "span": {"offset": 0, "length": 27},
                    },
                    {
                        "content": "shall be 35 C.",
                        "source": "D(2, 1, 4, 4, 4, 4, 5, 1, 5)",
                        "span": {"offset": 28, "length": 14},
                    },
                ],
            },
        ],
        paragraphs=[],
    )


def _validation(source_text: str | None):
    rule_set = parse_rule_set(
        """
dsl_version: 1
rule_set_id: generator
name: Generator
version: 1.0.0
status: active
entities:
  - id: maximum_temperature
    name: Maximum temperature
    section: Environment
    source_text_path: maximum_temperature.source_text
    source_page_path: maximum_temperature.source_page
    rules:
      - id: maximum-temperature
        path: maximum_temperature.value
        operator: minimum
        expected: 40
        required: true
"""
    )
    return RuleEvaluator().evaluate(
        {
            "maximum_temperature": {
                "value": 35,
                "source_text": source_text,
                "source_page": 2,
            }
        },
        rule_set,
    )


def test_resolves_multiline_source_text_to_normalized_polygons():
    result = resolve_validation_evidence(
        _validation("Maximum ambient temperature shall be 35 C."),
        _document(),
    )

    entity = result.entities[0]
    assert entity.evidence_match_type == "exact"
    assert entity.evidence_match_confidence == 1
    assert len(entity.source_regions) == 2
    assert entity.source_regions[0].page_number == 2
    assert entity.source_regions[0].polygon[0].x == 0.1
    assert entity.source_regions[0].polygon[0].y == 0.1


def test_marks_unmatched_source_text_explicitly():
    result = resolve_validation_evidence(
        _validation("Unrelated requirement with no matching source text."),
        _document(),
    )

    entity = result.entities[0]
    assert entity.evidence_match_type == "not_found"
    assert entity.evidence_match_confidence == 0
    assert entity.source_regions == []
