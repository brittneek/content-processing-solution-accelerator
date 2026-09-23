# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Convert a Content Understanding analyzer definition into extraction JSON Schema.

The generated schema intentionally excludes analyzer-produced compliance grades
and narratives. Compliance remains external YAML configuration evaluated by the
generic Validate pipeline stage.

Usage:
    python convert_analyzer_schema.py <ANALYZER_JSON> <OUTPUT_SCHEMA_JSON>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_SKIPPED_FIELDS = {"ComplianceStatus", "Justification"}
_SKIPPED_SECTIONS = {"ComplianceRollup"}


def _snake_case(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()


def _nullable_schema(field: dict[str, Any]) -> dict[str, Any]:
    field_type = field.get("type", "string")
    converted: dict[str, Any] = {
        "description": field.get("description", ""),
    }

    if field_type == "date":
        converted["type"] = ["string", "null"]
        converted["format"] = "date"
    elif field_type == "array":
        converted["anyOf"] = [
            {
                "type": "array",
                "items": _convert_array_item(field.get("items", {})),
            },
            {"type": "null"},
        ]
    elif field_type == "object":
        properties = {
            _snake_case(name): _nullable_schema(spec)
            for name, spec in field.get("properties", {}).items()
            if name not in _SKIPPED_FIELDS
        }
        converted["anyOf"] = [
            {
                "type": "object",
                "properties": properties,
                "required": list(properties),
            },
            {"type": "null"},
        ]
    else:
        converted["type"] = [field_type, "null"]

    enum = field.get("enum")
    if isinstance(enum, list) and enum:
        converted["enum"] = [*enum, None]
    return converted


def _convert_array_item(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("type") != "object":
        return {"type": item.get("type", "string")}

    properties = {
        _snake_case(name): _nullable_schema(spec)
        for name, spec in item.get("properties", {}).items()
        if name not in _SKIPPED_FIELDS
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
    }


def convert_analyzer(analyzer: dict[str, Any]) -> dict[str, Any]:
    field_schema = analyzer["fieldSchema"]
    output_properties: dict[str, Any] = {}

    for section_name, section in field_schema["fields"].items():
        if section_name in _SKIPPED_SECTIONS:
            continue

        if section_name == "DocumentMetadata":
            metadata_properties = {
                _snake_case(name): _nullable_schema(spec)
                for name, spec in section.get("properties", {}).items()
            }
            output_properties["document_metadata"] = {
                "type": "object",
                "description": section.get("description", ""),
                "properties": metadata_properties,
                "required": list(metadata_properties),
            }
            continue

        for entity_name, entity in section.get("properties", {}).items():
            properties: dict[str, Any] = {}
            stated_value = entity.get("properties", {}).get("StatedValue")
            properties["source_text"] = {
                "type": ["string", "null"],
                "description": (
                    stated_value.get("description", "")
                    if isinstance(stated_value, dict)
                    else "Shortest exact source quotation supporting this requirement."
                ),
            }
            properties["source_page"] = {
                "type": ["integer", "null"],
                "description": "One-based PDF page containing source_text.",
            }

            for field_name, field in entity.get("properties", {}).items():
                if field_name == "StatedValue" or field_name in _SKIPPED_FIELDS:
                    continue
                properties[_snake_case(field_name)] = _nullable_schema(field)

            output_properties[_snake_case(entity_name)] = {
                "type": "object",
                "description": entity.get("description", ""),
                "properties": properties,
                "required": list(properties),
            }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "GeneratorSpecComplianceAnalyzer",
        "description": (
            "Comprehensive generator specification extraction translated from "
            "the Content Understanding analyzer definition. Extract normalized "
            "facts and preserve exact source evidence; external YAML rules "
            "determine compliance."
        ),
        "type": "object",
        "properties": output_properties,
        "required": list(output_properties),
    }


def main() -> None:
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} <ANALYZER_JSON> <OUTPUT_SCHEMA_JSON>",
            file=sys.stderr,
        )
        raise SystemExit(1)

    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    analyzer = json.loads(source.read_text(encoding="utf-8-sig"))
    converted = convert_analyzer(analyzer)
    destination.write_text(
        json.dumps(converted, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
