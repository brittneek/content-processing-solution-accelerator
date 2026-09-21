# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Load and validate external YAML rule definitions."""

from pathlib import Path

import yaml
from libs.pipeline.handlers.logics.validate_handler.model import RuleSetDefinition


def parse_rule_set(content: str | bytes) -> RuleSetDefinition:
    """Parse YAML rule content and validate its complete structure."""

    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML rule set: {exc}") from exc

    if not isinstance(parsed, dict):
        raise TypeError("Rule set must contain a YAML object")

    return RuleSetDefinition.model_validate(parsed)


def load_rule_set(path: str | Path) -> RuleSetDefinition:
    """Load a YAML rules file and validate its complete structure."""

    rule_path = Path(path)
    try:
        content = rule_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Unable to read rule set '{rule_path}': {exc}") from exc

    return parse_rule_set(content)
