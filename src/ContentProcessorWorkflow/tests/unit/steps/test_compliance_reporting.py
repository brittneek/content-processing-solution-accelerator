# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for deterministic compliance summary and gap reporting."""

from steps.compliance_reporting import (
    build_compliance_gap_analysis,
    build_compliance_summary,
    validation_documents,
)


def _processed_result():
    return {
        "validation_result": {
            "overall_status": "noncompliant",
            "entities": [
                {
                    "entity_id": "fuel_level",
                    "name": "Fuel-level monitoring",
                    "compliance_status": "partially_compliant",
                    "justification": "High alarm is 93 percent; 90 percent is required.",
                    "source_page": 26,
                },
                {
                    "entity_id": "humidity",
                    "name": "Relative humidity",
                    "compliance_status": "undetermined",
                    "justification": "Minimum relative humidity was not found.",
                },
                {
                    "entity_id": "turbo",
                    "name": "Turbocharged engine",
                    "compliance_status": "compliant",
                    "justification": "The engine is turbocharged.",
                },
            ],
        }
    }


def test_validation_documents_filters_non_validation_results():
    documents = validation_documents(
        [
            ("generator.pdf", _processed_result()),
            ("other.pdf", {"result": {}}),
        ]
    )

    assert len(documents) == 1
    assert documents[0][0] == "generator.pdf"


def test_compliance_summary_uses_validation_results_not_claim_language():
    report = build_compliance_summary(
        validation_documents([("generator.pdf", _processed_result())])
    )

    assert "Specification Compliance Summary" in report
    assert "Overall status: Noncompliant" in report
    assert "1 partially compliant" in report
    assert "1 undetermined" in report
    assert "Fuel-level monitoring" in report
    assert "insurance" not in report.lower()
    assert "claimant" not in report.lower()


def test_gap_analysis_separates_deviations_and_unknowns():
    report = build_compliance_gap_analysis(
        validation_documents([("generator.pdf", _processed_result())])
    )

    assert "Partially compliant requirements (1)" in report
    assert "Undetermined requirements (1)" in report
    assert "Fuel-level monitoring" in report
    assert "Relative humidity" in report
    assert "Turbocharged engine" not in report
