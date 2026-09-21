# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Resolve extracted source quotations to Content Understanding line polygons."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from libs.azure_helper.model.content_understanding import DocumentContent
from libs.pipeline.handlers.logics.evaluate_handler.content_understanding_confidence_evaluator import (
    DIDocumentLine,
    extract_lines,
)

from .model import EntityValidationResult, EvidenceRegion, ValidationResult

_MAX_MATCH_LINES = 8
_FUZZY_MATCH_THRESHOLD = 0.7


@dataclass(frozen=True)
class _EvidenceMatch:
    lines: list[DIDocumentLine]
    match_type: str
    confidence: float


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _score_candidate(source_text: str, candidate_text: str) -> tuple[str, float]:
    if candidate_text == source_text:
        return "exact", 1.0
    if source_text in candidate_text:
        return "contains", round(len(source_text) / len(candidate_text), 3)

    similarity = SequenceMatcher(None, source_text, candidate_text).ratio()
    return "fuzzy", round(similarity, 3)


def _find_best_match(
    source_text: str,
    source_page: int | None,
    document: DocumentContent,
) -> _EvidenceMatch | None:
    normalized_source = _normalize_text(source_text)
    if not normalized_source:
        return None

    lines_by_page: dict[int, list[DIDocumentLine]] = {}
    for line in extract_lines(document):
        if line.page_number is not None:
            lines_by_page.setdefault(line.page_number, []).append(line)

    best: _EvidenceMatch | None = None
    best_rank = (-1.0, False)
    for page_index, page_lines in lines_by_page.items():
        actual_page = document.pages[page_index].pageNumber
        for start in range(len(page_lines)):
            max_size = min(_MAX_MATCH_LINES, len(page_lines) - start)
            for size in range(1, max_size + 1):
                candidate_lines = page_lines[start : start + size]
                candidate_text = _normalize_text(
                    " ".join(line.content for line in candidate_lines)
                )
                match_type, confidence = _score_candidate(
                    normalized_source, candidate_text
                )
                rank = (confidence, source_page == actual_page)
                if rank > best_rank:
                    best = _EvidenceMatch(
                        lines=candidate_lines,
                        match_type=match_type,
                        confidence=confidence,
                    )
                    best_rank = rank

    if best is None or best.confidence < _FUZZY_MATCH_THRESHOLD:
        return None
    return best


def _enrich_entity(
    entity: EntityValidationResult,
    document: DocumentContent,
) -> None:
    if not entity.source_text:
        return

    match = _find_best_match(entity.source_text, entity.source_page, document)
    if match is None:
        return

    regions: list[EvidenceRegion] = []
    for line in match.lines:
        if line.page_number is None or not line.normalized_polygon:
            continue
        regions.append(
            EvidenceRegion(
                page_number=document.pages[line.page_number].pageNumber,
                polygon=line.normalized_polygon,
            )
        )

    if not regions:
        return

    entity.evidence_match_type = match.match_type
    entity.evidence_match_confidence = match.confidence
    entity.source_regions = regions


def resolve_validation_evidence(
    validation: ValidationResult,
    document: DocumentContent,
) -> ValidationResult:
    """Attach source polygons to every validation entity with matching evidence."""

    for entity in validation.entities:
        _enrich_entity(entity, document)
    return validation
