# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for the optional pipeline validation stage."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from libs.application.application_context import AppContext
from libs.pipeline.entities.schema import Schema
from libs.pipeline.handlers.logics.evaluate_handler.comparison import (
    ExtractionComparisonData,
)
from libs.pipeline.handlers.logics.evaluate_handler.model import DataExtractionResult
from libs.pipeline.handlers.validate_handler import ValidateHandler


def _evaluated_json(extracted_result: dict) -> str:
    return DataExtractionResult(
        extracted_result=extracted_result,
        confidence={},
        comparison_result=ExtractionComparisonData(items=[]),
        prompt_tokens=0,
        completion_tokens=0,
        execution_time=0,
    ).model_dump_json()


def _rules_yaml(version: str = "1.0.0") -> str:
    return f"""
dsl_version: 1
rule_set_id: generator
name: Generator
version: {version}
status: active
entities:
  - id: maximum_temperature
    name: Maximum temperature
    section: Environment
    source_text_path: maximum_temperature.source_text
    source_page_path: maximum_temperature.source_page
    rules:
      - id: maximum-temperature-minimum
        path: maximum_temperature.value
        operator: minimum
        expected: 40
        required: true
        severity: high
"""


def _handler_and_context(mocker, schema: Schema):
    handler = ValidateHandler.model_construct()
    handler.handler_name = "validate"
    handler.application_context = AppContext()
    handler.application_context.configuration = MagicMock()
    config = handler.application_context.configuration
    config.app_cosmos_connstr = "connection"
    config.app_cosmos_database = "database"
    config.app_cosmos_container_schema = "schemas"
    config.app_storage_blob_url = "https://storage.example.com"
    config.app_cps_configuration = "cps-configuration"
    config.app_cps_processes = "cps-processes"

    context = MagicMock()
    context.data_pipeline.pipeline_status.schema_id = schema.Id
    context.data_pipeline.pipeline_status.process_id = "process-1"
    result_file = MagicMock()
    result_file.name = "validate_output.json"
    result_file.log_entries = []
    context.data_pipeline.add_file.return_value = result_file
    handler._current_message_context = context

    mocker.patch(
        "libs.pipeline.handlers.validate_handler.Schema.get_schema",
        return_value=schema,
    )
    return handler, context, result_file


@pytest.mark.asyncio
async def test_execute_evaluates_schema_rules(mocker):
    schema = Schema(
        Id="schema-1",
        ClassName="Generator",
        Description="Generator",
        FileName="generator.json",
        ContentType="application/json",
        RulesFileName="generator.rules.yaml",
        RulesContentType="application/yaml",
        RulesVersion="1.0.0",
    )
    handler, context, result_file = _handler_and_context(mocker, schema)
    evaluate_output = _evaluated_json(
        {
            "maximum_temperature": {
                "source_text": "Maximum ambient temperature: 35 C",
                "source_page": 8,
                "value": 35,
            }
        }
    )
    mocker.patch(
        "libs.pipeline.handlers.validate_handler."
        "ValidateHandler.download_output_file_to_json_string",
        side_effect=lambda processed_by, artifact_type: (
            evaluate_output if processed_by == "evaluate" else None
        ),
    )
    blob_helper = mocker.patch(
        "libs.pipeline.handlers.validate_handler.StorageBlobHelper"
    )
    blob_helper.return_value.download_text.return_value = _rules_yaml()

    result = await handler.execute(context)

    assert result.result["result"] == "completed"
    stored = json.loads(result_file.upload_json_text.call_args.kwargs["text"])
    assert stored["summary"]["failed"] == 1
    assert stored["entities"][0]["source_page"] == 8
    context.data_pipeline.add_file.assert_called_once()


@pytest.mark.asyncio
async def test_execute_skips_schema_without_rules(mocker):
    schema = Schema(
        Id="schema-1",
        ClassName="Invoice",
        Description="Invoice",
        FileName="invoice.json",
        ContentType="application/json",
    )
    handler, context, result_file = _handler_and_context(mocker, schema)
    download_evaluate = mocker.patch(
        "libs.pipeline.handlers.validate_handler."
        "ValidateHandler.download_output_file_to_json_string",
    )
    blob_helper = mocker.patch(
        "libs.pipeline.handlers.validate_handler.StorageBlobHelper"
    )

    result = await handler.execute(context)

    assert result.result["result"] == "skipped"
    stored = json.loads(result_file.upload_json_text.call_args.kwargs["text"])
    assert stored["status"] == "skipped"
    download_evaluate.assert_not_called()
    blob_helper.assert_not_called()


@pytest.mark.asyncio
async def test_execute_rejects_rule_version_mismatch(mocker):
    schema = Schema(
        Id="schema-1",
        ClassName="Generator",
        Description="Generator",
        FileName="generator.json",
        ContentType="application/json",
        RulesFileName="generator.rules.yaml",
        RulesContentType="application/yaml",
        RulesVersion="2.0.0",
    )
    handler, context, _ = _handler_and_context(mocker, schema)
    mocker.patch(
        "libs.pipeline.handlers.validate_handler."
        "ValidateHandler.download_output_file_to_json_string",
        return_value=_evaluated_json({}),
    )
    blob_helper = mocker.patch(
        "libs.pipeline.handlers.validate_handler.StorageBlobHelper"
    )
    blob_helper.return_value.download_text.return_value = _rules_yaml("1.0.0")

    with pytest.raises(ValueError, match="Rule version mismatch"):
        await handler.execute(context)
