"""Regression tests for low-cost, restart-safe graph ingestion."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from app.api import graph_bp
from app.models.project import Project, ProjectStatus
from app.services.text_processor import TextProcessor
from app.services.graph_builder import GraphBuilderService


class GraphOptimizationTests(unittest.TestCase):
    def test_new_project_defaults_and_legacy_saved_project_compatibility(self):
        new = Project(
            project_id="proj_new", name="Prueba", status=ProjectStatus.CREATED,
            created_at="2026", updated_at="2026",
        )
        self.assertEqual((new.chunk_size, new.chunk_overlap, new.ingestion_mode),
                         (3000, 150, "optimized_v1"))
        old = Project.from_dict({
            "project_id": "proj_saved", "name": "Guardado",
            "status": "graph_building", "created_at": "2026",
            "updated_at": "2026", "chunk_size": 500, "chunk_overlap": 50,
        })
        self.assertEqual((old.chunk_size, old.chunk_overlap, old.ingestion_mode),
                         (500, 50, "legacy_v0"))
        self.assertEqual(new.to_dict()["ingestion_mode"], "optimized_v1")

    def test_dedupe_is_stable_and_preserves_frequency(self):
        with patch.object(TextProcessor, "split_text",
                          return_value=["A", "B", "A", "C", "B", "A"]):
            unique, counts, original = TextProcessor.prepare_graph_chunks(
                "original intact", 3000, 150, deduplicate=True
            )
            self.assertEqual(unique, ["A", "B", "C"])
            self.assertEqual(counts, [3, 2, 1])
            self.assertEqual(original, 6)
            old, old_counts, old_original = TextProcessor.prepare_graph_chunks(
                "original intact", 500, 50, deduplicate=False
            )
            self.assertEqual(old, ["A", "B", "A", "C", "B", "A"])
            self.assertEqual(old_counts, [1] * 6)
            self.assertEqual(old_original, 6)
            self.assertNotEqual(
                GraphBuilderService.build_operation_id("test_graph", unique),
                GraphBuilderService.build_operation_id("test_graph", old),
            )

    def test_graph_batch_carries_repeated_source_counts(self):
        calls = []
        class FakeBatch:
            def create(self, **kw):
                calls.append(("create", kw))
                return SimpleNamespace(batch_id="test-batch")
            def add(self, **kw):
                calls.append(("add", kw))
                return [
                    SimpleNamespace(episode_uuid="episode-" + str(i))
                    for i in range(len(kw["items"]))
                ]
            def process(self, **kw):
                calls.append(("process", kw))
                return SimpleNamespace(status="queued")
        service = object.__new__(GraphBuilderService)
        service.client = SimpleNamespace(batch=FakeBatch())
        operation = service.add_text_batches(
            "test_graph", ["fragment A", "fragment B"],
            occurrence_counts=[3, 2], original_chunk_count=5
        )
        self.assertEqual(operation.item_count, 2)
        metadata = calls[0][1]["metadata"]
        self.assertEqual(metadata["original_chunk_count"], 5)
        self.assertEqual(metadata["duplicate_chunks_omitted"], 3)
        items = calls[1][1]["items"]
        self.assertEqual([item.metadata["occurrences_in_source"] for item in items], [3, 2])
        self.assertEqual([name for name, _ in calls], ["create", "add", "process"])

    def test_invalid_occurrence_count_never_mutates_cloud(self):
        class NeverMutate:
            def create(self, **_kw):
                raise AssertionError("Cloud must not be called")
        service = object.__new__(GraphBuilderService)
        service.client = SimpleNamespace(batch=NeverMutate())
        for counts, original in [([1], 2), ([0, 2], 2), ([1, 2], 4)]:
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                service.add_text_batches(
                    "test_graph", ["one", "two"],
                    occurrence_counts=counts, original_chunk_count=original,
                )

    def test_durable_status_reads_cloud_without_resubmitting(self):
        from app.api import graph as graph_routes
        p = SimpleNamespace(
            project_id="proj_teststatus", status=ProjectStatus.GRAPH_BUILDING,
            graph_build_task_id="old-ephemeral", zep_batch_id="batch-saved"
        )
        progress = SimpleNamespace(total_items=1431, succeeded_items=80,
                                   processing_items=20, failed_items=0)
        summary = SimpleNamespace(status="processing", progress=progress)
        fake_builder = SimpleNamespace(get_batch_summary=lambda _id: summary)
        app = Flask(__name__)
        app.register_blueprint(graph_bp, url_prefix="/api/graph")
        with patch.object(graph_routes.ProjectManager, "get_project", return_value=p), \
             patch.object(graph_routes, "_project_has_active_build", return_value=False), \
             patch.object(graph_routes, "GraphBuilderService", return_value=fake_builder):
            response = app.test_client().get("/api/graph/project/proj_teststatus/build-status")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["data"]
        self.assertEqual((payload["processed"], payload["total"], payload["processing"]),
                         (80, 1431, 20))
        self.assertAlmostEqual(payload["percent"], 5.6, places=1)
        self.assertFalse(payload["needs_recovery"])


if __name__ == "__main__":
    unittest.main()
