# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Deterministic summary and gap reports for validated document results."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

_STATUS_LABELS = {
    "compliant": "Compliant",
    "partially_compliant": "Partially compliant",
    "noncompliant": "Noncompliant",
    "undetermined": "Undetermined",
    "not_applicable": "Not applicable",
    "review_required": "Review required",
}
_OVERALL_PRIORITY = (
    "review_required",
    "noncompliant",
    "partially_compliant",
    "undetermined",
    "compliant",
    "not_applicable",
)


def validation_documents(
    processed_documents: Iterable[tuple[str, Mapping[str, Any]]],
) -> list[tuple[str, Mapping[str, Any]]]:
    """Return documents containing a structured validation result."""
    return [
        (file_name, processed["validation_result"])
        for file_name, processed in processed_documents
        if isinstance(processed.get("validation_result"), Mapping)
        and isinstance(processed["validation_result"].get("entities"), list)
    ]


def _entities(
    documents: Iterable[tuple[str, Mapping[str, Any]]],
) -> list[tuple[str, Mapping[str, Any]]]:
    return [
        (file_name, entity)
        for file_name, validation in documents
        for entity in validation.get("entities", [])
        if isinstance(entity, Mapping)
    ]


def _overall_status(documents: Iterable[tuple[str, Mapping[str, Any]]]) -> str:
    statuses = {
        str(validation.get("overall_status"))
        for _, validation in documents
        if validation.get("overall_status")
    }
    return next(
        (status for status in _OVERALL_PRIORITY if status in statuses),
        "not_applicable",
    )


def _status_counts(
    entities: Iterable[tuple[str, Mapping[str, Any]]],
) -> dict[str, int]:
    counts = {status: 0 for status in _STATUS_LABELS}
    for _, entity in entities:
        status = str(entity.get("compliance_status") or "undetermined")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _finding_line(file_name: str, entity: Mapping[str, Any]) -> str:
    status = str(entity.get("compliance_status") or "undetermined")
    name = str(entity.get("name") or entity.get("entity_id") or "Requirement")
    justification = str(entity.get("justification") or "No explanation available.")
    page = entity.get("source_page")
    page_text = f" Page {page}." if page is not None else ""
    return (
        f"- [{_STATUS_LABELS.get(status, status)}] {name}: "
        f"{justification}{page_text} Document: {file_name}."
    )


def build_compliance_summary(
    documents: list[tuple[str, Mapping[str, Any]]],
) -> str:
    """Build a concise compliance summary without an insurance-claim prompt."""
    entity_rows = _entities(documents)
    counts = _status_counts(entity_rows)
    overall = _overall_status(documents)
    deviations = [
        item
        for item in entity_rows
        if item[1].get("compliance_status") in {"noncompliant", "partially_compliant"}
    ]
    unresolved = [
        item
        for item in entity_rows
        if item[1].get("compliance_status") in {"undetermined", "review_required"}
    ]

    lines = [
        "Specification Compliance Summary",
        f"Overall status: {_STATUS_LABELS.get(overall, overall)}",
        f"Documents reviewed: {len(documents)}",
        f"Requirements assessed: {len(entity_rows)}",
        (
            "Outcome totals: "
            f"{counts['compliant']} compliant, "
            f"{counts['partially_compliant']} partially compliant, "
            f"{counts['noncompliant']} noncompliant, "
            f"{counts['undetermined']} undetermined, "
            f"{counts['review_required']} review required, "
            f"{counts['not_applicable']} not applicable."
        ),
        "",
        "Known deviations:",
    ]
    lines.extend(
        [_finding_line(file_name, entity) for file_name, entity in deviations[:10]]
        or ["No known deviations were identified."]
    )
    if len(deviations) > 10:
        lines.append(
            f"- {len(deviations) - 10} additional deviations are in the Compliance tab."
        )

    lines.extend(["", "Unresolved requirements:"])
    lines.extend(
        [_finding_line(file_name, entity) for file_name, entity in unresolved[:10]]
        or ["No unresolved requirements were identified."]
    )
    if len(unresolved) > 10:
        lines.append(
            f"- {len(unresolved) - 10} additional unresolved requirements are in the Compliance tab."
        )

    lines.extend(["", "Documents reviewed:"])
    lines.extend(f"- {file_name}" for file_name, _ in documents)
    return "\n".join(lines)


def build_compliance_gap_analysis(
    documents: list[tuple[str, Mapping[str, Any]]],
) -> str:
    """Build deterministic deviations and evidence gaps from validation output."""
    entity_rows = _entities(documents)
    groups = (
        (
            "Noncompliant requirements",
            {"noncompliant"},
            "No noncompliant requirements were identified.",
        ),
        (
            "Partially compliant requirements",
            {"partially_compliant"},
            "No partially compliant requirements were identified.",
        ),
        (
            "Undetermined requirements",
            {"undetermined"},
            "No undetermined requirements were identified.",
        ),
        (
            "Manual review required",
            {"review_required"},
            "No requirements require manual review.",
        ),
    )

    lines = [
        "Specification Compliance Gaps and Exceptions",
        (
            "This report is derived from configured validation rules. "
            "Compliant and not-applicable requirements are not treated as gaps."
        ),
    ]
    for heading, statuses, empty_message in groups:
        matches = [
            item for item in entity_rows if item[1].get("compliance_status") in statuses
        ]
        lines.extend(["", f"{heading} ({len(matches)}):"])
        lines.extend(
            [_finding_line(file_name, entity) for file_name, entity in matches]
            or [empty_message]
        )

    return "\n".join(lines)
