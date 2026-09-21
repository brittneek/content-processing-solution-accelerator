# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for the ContentProcess domain model persistence methods."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.routers.models.contentprocessor.content_process import (
    ContentProcess,
    ExtractionComparisonData,
    ExtractionComparisonItem,
    PaginatedResponse,
    SkippedValidationResult,
    Step_Outputs,
    ValidationResult,
)

CONN = "mongodb://localhost:27017"
DB = "test_db"
COL = "test_col"
BLOB_URL = "https://example.blob.core.windows.net"


@pytest.fixture
def sample_process():
    return ContentProcess(process_id="p1", status="processing")


# ---------------------------------------------------------------------------
# Pydantic validators
# ---------------------------------------------------------------------------


class TestContentProcessValidators:
    def test_id_defaults_to_process_id(self):
        p = ContentProcess(process_id="abc")
        assert p.id == "abc"

    def test_id_from_dict_defaults(self):
        p = ContentProcess(**{"process_id": "xyz"})
        assert p.id == "xyz"

    def test_explicit_id_preserved(self):
        p = ContentProcess(process_id="xyz", id="custom")
        assert p.id == "custom"

    def test_non_string_id_coerced(self):
        p = ContentProcess(**{"process_id": "abc", "id": 123})
        assert p.id == "abc"  # non-string → fallback

    def test_completed_validation_result_is_typed(self):
        process = ContentProcess(
            process_id="abc",
            validation_result={
                "rule_set_id": "generator-global",
                "rule_set_version": "0.1.0",
                "summary": {
                    "passed": 1,
                    "failed": 0,
                    "missing": 0,
                    "not_applicable": 0,
                    "errors": 0,
                },
                "entities": [
                    {
                        "entity_id": "engine_type",
                        "name": "Engine type",
                        "section": "Engine",
                        "status": "pass",
                        "source_text": "Four-cycle diesel engine",
                        "source_page": 4,
                        "evidence_match_type": "exact",
                        "evidence_match_confidence": 1,
                        "source_regions": [
                            {
                                "page_number": 4,
                                "polygon": [
                                    {"x": 0.1, "y": 0.2},
                                    {"x": 0.5, "y": 0.2},
                                    {"x": 0.5, "y": 0.25},
                                    {"x": 0.1, "y": 0.25},
                                ],
                            }
                        ],
                        "rule_results": [
                            {
                                "rule_id": "engine-cycle",
                                "path": "engine_type.cycles",
                                "operator": "contains",
                                "status": "pass",
                                "severity": "high",
                                "expected": "four_cycle",
                                "actual": ["four_cycle"],
                                "message": "Required value is present.",
                            }
                        ],
                    }
                ],
            },
        )

        assert isinstance(process.validation_result, ValidationResult)
        assert process.validation_result.entities[0].source_page == 4
        assert process.validation_result.entities[0].source_regions[0].polygon[0].x == 0.1

    def test_skipped_validation_result_is_typed(self):
        process = ContentProcess(
            process_id="abc",
            validation_result={
                "status": "skipped",
                "reason": "The selected schema has no validation rules.",
            },
        )

        assert isinstance(process.validation_result, SkippedValidationResult)


# ---------------------------------------------------------------------------
# ExtractionComparison helpers
# ---------------------------------------------------------------------------


class TestExtractionComparison:
    def test_item_to_dict(self):
        item = ExtractionComparisonItem(
            Field="Name", Extracted="John", Confidence="High", IsAboveThreshold=True
        )
        d = item.to_dict()
        assert d["Field"] == "Name"

    def test_item_to_json(self):
        item = ExtractionComparisonItem(
            Field="Amount", Extracted=100, Confidence="Low", IsAboveThreshold=False
        )
        j = item.to_json()
        assert '"Amount"' in j

    def test_data_to_dict(self):
        data = ExtractionComparisonData(
            items=[
                ExtractionComparisonItem(
                    Field="A", Extracted="B", Confidence="Med", IsAboveThreshold=True
                )
            ]
        )
        assert len(data.to_dict()["items"]) == 1

    def test_data_to_json(self):
        data = ExtractionComparisonData(items=[])
        j = data.to_json()
        assert "items" in j


# ---------------------------------------------------------------------------
# Cosmos DB persistence methods
# ---------------------------------------------------------------------------


class TestUpdateProcessStatusToCosmos:
    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_inserts_when_not_existing(self, MockHelper, sample_process):
        mock_helper = MockHelper.return_value
        mock_helper.find_document.return_value = []

        sample_process.update_process_status_to_cosmos(CONN, DB, COL)
        mock_helper.insert_document.assert_called_once()

    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_updates_when_existing(self, MockHelper, sample_process):
        mock_helper = MockHelper.return_value
        mock_helper.find_document.return_value = [{"process_id": "p1"}]

        sample_process.update_process_status_to_cosmos(CONN, DB, COL)
        mock_helper.update_document_by_query.assert_called_once()


class TestUpdateStatusToCosmos:
    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_inserts_when_not_existing(self, MockHelper, sample_process):
        mock_helper = MockHelper.return_value
        mock_helper.find_document.return_value = []

        sample_process.update_status_to_cosmos(CONN, DB, COL)
        mock_helper.insert_document.assert_called_once()

    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_updates_when_existing(self, MockHelper, sample_process):
        mock_helper = MockHelper.return_value
        mock_helper.find_document.return_value = [{"process_id": "p1"}]

        sample_process.update_status_to_cosmos(CONN, DB, COL)
        mock_helper.update_document_by_query.assert_called_once()


class TestGetStatusFromBlob:
    @patch("app.routers.models.contentprocessor.content_process.StorageBlobHelper")
    def test_returns_step_outputs(self, MockBlobHelper, sample_process):
        step_data = [{"step_name": "extract", "step_result": {"key": "val"}}]
        mock_helper = MockBlobHelper.return_value
        mock_helper.download_blob.return_value = json.dumps(step_data).encode()

        result = sample_process.get_status_from_blob(BLOB_URL, "container", "blob.json")
        assert len(result) == 1
        assert isinstance(result[0], Step_Outputs)
        assert result[0].step_name == "extract"

    @patch("app.routers.models.contentprocessor.content_process.StorageBlobHelper")
    def test_returns_empty_on_blob_not_found(self, MockBlobHelper, sample_process):
        mock_helper = MockBlobHelper.return_value
        mock_helper.download_blob.side_effect = Exception("Not found")

        result = sample_process.get_status_from_blob(BLOB_URL, "container", "blob.json")
        assert result == []


class TestGetStatusFromCosmos:
    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_returns_process_when_found(self, MockHelper, sample_process):
        mock_helper = MockHelper.return_value
        mock_helper.find_document.return_value = [
            {"process_id": "p1", "status": "Completed"}
        ]

        result = sample_process.get_status_from_cosmos(CONN, DB, COL)
        assert isinstance(result, ContentProcess)
        assert result.status == "Completed"

    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_returns_none_when_not_found(self, MockHelper, sample_process):
        mock_helper = MockHelper.return_value
        mock_helper.find_document.return_value = []

        result = sample_process.get_status_from_cosmos(CONN, DB, COL)
        assert result is None


class TestDeleteProcessedFile:
    @patch("app.routers.models.contentprocessor.content_process.StorageBlobHelper")
    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_deletes_and_returns_process(self, MockMongo, MockBlob, sample_process):
        mock_mongo = MockMongo.return_value
        mock_mongo.find_document.return_value = [
            {"process_id": "p1", "status": "Completed"}
        ]
        mock_blob = MockBlob.return_value

        result = sample_process.delete_processed_file(CONN, DB, COL, BLOB_URL, "ctr")
        mock_blob.delete_folder.assert_called_once_with(folder_name="p1")
        mock_mongo.delete_document.assert_called_once()
        assert isinstance(result, ContentProcess)

    @patch("app.routers.models.contentprocessor.content_process.StorageBlobHelper")
    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_returns_none_when_not_found(self, MockMongo, MockBlob, sample_process):
        mock_mongo = MockMongo.return_value
        mock_mongo.find_document.return_value = []
        MockBlob.return_value

        result = sample_process.delete_processed_file(CONN, DB, COL, BLOB_URL, "ctr")
        assert result is None


class TestUpdateProcessResult:
    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_updates_when_found(self, MockHelper, sample_process):
        mock_helper = MockHelper.return_value
        mock_helper.find_document.return_value = [{"process_id": "p1"}]
        mock_helper.update_document_by_query.return_value = MagicMock()

        result = sample_process.update_process_result(CONN, DB, COL, {"key": "val"})
        assert result is not None

    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_returns_none_when_not_found(self, MockHelper, sample_process):
        mock_helper = MockHelper.return_value
        mock_helper.find_document.return_value = []

        result = sample_process.update_process_result(CONN, DB, COL, {"key": "val"})
        assert result is None


class TestUpdateProcessComment:
    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_updates_when_found(self, MockHelper, sample_process):
        mock_helper = MockHelper.return_value
        mock_helper.find_document.return_value = [{"process_id": "p1"}]
        mock_helper.update_document_by_query.return_value = MagicMock()

        result = sample_process.update_process_comment(CONN, DB, COL, "note")
        assert result is not None

    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_returns_none_when_not_found(self, MockHelper, sample_process):
        mock_helper = MockHelper.return_value
        mock_helper.find_document.return_value = []

        result = sample_process.update_process_comment(CONN, DB, COL, "note")
        assert result is None


class TestGetAllProcessesFromCosmos:
    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_returns_paginated_items(self, MockHelper):
        mock_helper = MockHelper.return_value
        mock_helper.count_documents.return_value = 2
        mock_helper.find_document.return_value = [
            {"process_id": "p1"},
            {"process_id": "p2"},
        ]

        result = ContentProcess.get_all_processes_from_cosmos(
            CONN, DB, COL, page_size=10, page_number=1
        )
        assert isinstance(result, PaginatedResponse)
        assert result.total_count == 2
        assert len(result.items) == 2

    @patch("app.routers.models.contentprocessor.content_process.CosmosMongDBHelper")
    def test_returns_empty_paginated_response(self, MockHelper):
        mock_helper = MockHelper.return_value
        mock_helper.count_documents.return_value = 0
        mock_helper.find_document.return_value = []

        result = ContentProcess.get_all_processes_from_cosmos(
            CONN, DB, COL, page_size=10, page_number=1
        )
        assert result.total_count == 0
        assert result.items == []


class TestGetFileBytesFromBlob:
    @patch("app.routers.models.contentprocessor.content_process.StorageBlobHelper")
    def test_returns_bytes(self, MockBlobHelper, sample_process):
        mock_helper = MockBlobHelper.return_value
        mock_helper.download_blob.return_value = b"binary data"

        result = sample_process.get_file_bytes_from_blob(BLOB_URL, "ctr", "file.pdf")
        assert result == b"binary data"
