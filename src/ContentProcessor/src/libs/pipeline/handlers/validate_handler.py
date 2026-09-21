# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Validate mapped document entities against schema-associated rules."""

import json

from libs.application.application_context import AppContext
from libs.azure_helper.model.content_understanding import AnalyzedResult
from libs.azure_helper.storage_blob import StorageBlobHelper
from libs.pipeline.entities.pipeline_file import ArtifactType, PipelineLogEntry
from libs.pipeline.entities.pipeline_message_context import MessageContext
from libs.pipeline.entities.pipeline_step_result import StepResult
from libs.pipeline.entities.schema import Schema
from libs.pipeline.handlers.logics.evaluate_handler.model import DataExtractionResult
from libs.pipeline.handlers.logics.validate_handler import (
    RuleEvaluator,
    parse_rule_set,
    resolve_validation_evidence,
)
from libs.pipeline.queue_handler_base import HandlerBase


class ValidateHandler(HandlerBase):
    """Run optional external validation rules for the selected schema."""

    def __init__(self, appContext: AppContext, step_name: str, **data):
        super().__init__(appContext, step_name, **data)

    async def execute(self, context: MessageContext) -> StepResult:
        configuration = self.application_context.configuration
        pipeline_status = context.data_pipeline.pipeline_status
        schema = Schema.get_schema(
            schema_id=pipeline_status.schema_id,
            connection_string=configuration.app_cosmos_connstr,
            database_name=configuration.app_cosmos_database,
            collection_name=configuration.app_cosmos_container_schema,
        )

        if schema is None:
            raise ValueError(f"Schema '{pipeline_status.schema_id}' was not found")

        if schema.RulesFileName:
            evaluated_json = self.download_output_file_to_json_string(
                processed_by="evaluate",
                artifact_type=ArtifactType.ScoreMergedData,
            )
            if not evaluated_json:
                raise ValueError("Evaluate output is required for validation")

            evaluated_result = DataExtractionResult(**json.loads(evaluated_json))
            rules_text = StorageBlobHelper(
                account_url=configuration.app_storage_blob_url,
                container_name=(
                    f"{configuration.app_cps_configuration}/Schemas/{schema.Id}"
                ),
            ).download_text(
                container_name=None,
                blob_name=schema.RulesFileName,
            )
            rule_set = parse_rule_set(rules_text)
            if schema.RulesVersion and rule_set.version != schema.RulesVersion:
                raise ValueError(
                    f"Rule version mismatch for schema '{schema.Id}': "
                    f"metadata={schema.RulesVersion}, file={rule_set.version}"
                )

            validation = RuleEvaluator().evaluate(
                evaluated_result.extracted_result,
                rule_set,
            )
            extracted_json = self.download_output_file_to_json_string(
                processed_by="extract",
                artifact_type=ArtifactType.ExtractedContent,
            )
            if extracted_json:
                analyzed_result = AnalyzedResult(**json.loads(extracted_json))
                resolve_validation_evidence(
                    validation,
                    analyzed_result.result.contents[0],
                )
            output = validation.model_dump(mode="json")
            result_status = "completed"
        else:
            output = {
                "status": "skipped",
                "reason": "The selected schema has no validation rules.",
            }
            result_status = "skipped"

        result_file = context.data_pipeline.add_file(
            file_name="validate_output.json",
            artifact_type=ArtifactType.ValidationData,
        )
        result_file.log_entries.append(
            PipelineLogEntry(
                source=self.handler_name,
                message="Validation result has been added",
            )
        )
        result_file.upload_json_text(
            account_url=configuration.app_storage_blob_url,
            container_name=configuration.app_cps_processes,
            text=json.dumps(output),
        )

        return StepResult(
            process_id=pipeline_status.process_id,
            step_name=self.handler_name,
            result={
                "result": result_status,
                "file_name": result_file.name,
            },
        )
