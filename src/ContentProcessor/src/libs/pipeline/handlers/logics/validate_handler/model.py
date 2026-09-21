# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Typed rule definitions and validation result models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ValidationStatus(StrEnum):
    """Terminal status for a rule or entity validation."""

    PASS = "pass"
    FAIL = "fail"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


class RuleOperator(StrEnum):
    """Operators supported by the generic evaluator."""

    EXISTS = "exists"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    CONTAINS = "contains"
    CONTAINS_ANY = "contains_any"
    CONTAINS_ALL = "contains_all"
    ONE_OF = "one_of"
    REGEX = "regex"


class RuleDefinition(BaseModel):
    """One atomic rule targeting a dotted path in the extracted result."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    operator: RuleOperator
    expected: Any = None
    required: bool = False
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    unit: str | None = None
    exclusive: bool = False
    message: str | None = None


class EntityDefinition(BaseModel):
    """Display metadata and rules for one extracted entity."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    section: str = Field(min_length=1)
    source_text_path: str | None = None
    source_page_path: str | None = None
    rules: list[RuleDefinition] = Field(min_length=1)


class RuleSetDefinition(BaseModel):
    """Versioned external configuration consumed by the evaluator."""

    model_config = ConfigDict(extra="forbid")

    dsl_version: int
    rule_set_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: Literal["draft", "active", "retired"] = "draft"
    description: str | None = None
    entities: list[EntityDefinition] = Field(min_length=1)


class RuleResult(BaseModel):
    """Outcome of evaluating one atomic rule."""

    rule_id: str
    path: str
    operator: RuleOperator
    status: ValidationStatus
    severity: Literal["critical", "high", "medium", "low"]
    expected: Any = None
    actual: Any = None
    unit: str | None = None
    message: str


class EvidencePoint(BaseModel):
    """Normalized point within a source page."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class EvidenceRegion(BaseModel):
    """One source-page polygon supporting an extracted entity."""

    page_number: int = Field(ge=1)
    polygon: list[EvidencePoint] = Field(min_length=3)


class EntityValidationResult(BaseModel):
    """Rolled-up outcome and evidence metadata for one entity."""

    entity_id: str
    name: str
    section: str
    status: ValidationStatus
    source_text: str | None = None
    source_page: int | None = None
    evidence_match_type: Literal["exact", "contains", "fuzzy", "not_found"] = (
        "not_found"
    )
    evidence_match_confidence: float = Field(default=0, ge=0, le=1)
    source_regions: list[EvidenceRegion] = Field(default_factory=list)
    rule_results: list[RuleResult]


class ValidationSummary(BaseModel):
    """Entity counts by validation status."""

    passed: int = 0
    failed: int = 0
    missing: int = 0
    not_applicable: int = 0
    errors: int = 0


class ValidationResult(BaseModel):
    """Complete result produced by evaluating one extracted document."""

    rule_set_id: str
    rule_set_version: str
    summary: ValidationSummary
    entities: list[EntityValidationResult]
