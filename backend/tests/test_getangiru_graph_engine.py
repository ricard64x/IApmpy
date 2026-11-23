"""Getangiru local graph regression: evidence, SQLite persistence and isolation."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from app.services.getangiru_graph_engine import GetangiruGraphStore, GraphScopeError

ACTORS = ["SocTeam", "SecurityTeam", "InfrastructureTeam", "FraudTeam",
          "AuditTeam", "RiskTeam", "ExecutiveBoard", "Vendor"]
ONTOLOGY = {
    "entity_types": [{"name": name} for name in ACTORS] + [
        {"name": "Person"}, {"name": "Organization"}
    ],
    "edge_types": [
        {"name": "COORDINATES_WITH", "source_targets": [
            {"source": "SocTeam", "target": "SecurityTeam"}]},
        {"name": "SUPPORTS", "source_targets": [
            {"source": "Vendor", "target": "SecurityTeam"}]},
    ]
}
DOC = ("El SOC alerta al equipo de Seguridad y a Infraestructura. "
       "El equipo de Fraudes informa a Auditoría y Riesgos. "
       "La Dirección conversa con el Proveedor para coordinar la revisión. "
       "No hay evidencia de exfiltración ni de relación causal entre los actores.")


class GetangiruLocalGraphTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = GetangiruGraphStore(self.folder.name + "/graphs.sqlite3")
        self.tenant = "tenondera"
        self.project = "proj_0123456789ab"

    def build(self, **changes):
        args = dict(tenant=self.tenant, project_id=self.project,
                    ontology=ONTOLOGY, source_text=DOC)
        args.update(changes)
        return self.store.build(**args)

    def test_evidence_only_no_invented_fact_and_schema_separation(self):
        graph = self.build()
        self.assertEqual(8, graph["node_count"])
        self.assertGreaterEqual(graph["edge_count"], 1)
        self.assertEqual(0, graph["fact_claims"])
        self.assertTrue(all(n["attributes"]["asserted_fact"] is False for n in graph["nodes"]))
        self.assertTrue(all(e["name"] == "CO_MENTIONED" for e in graph["edges"]))
        self.assertTrue(all(e["attributes"]["asserted_fact"] is False for e in graph["edges"]))
        self.assertEqual(2, len(graph["schema_relations"]))
        self.assertTrue(all(e["is_template"] for e in graph["schema_relations"]))
        self.assertFalse(any(e["name"] == "SUPPORTS" for e in graph["edges"]))

    def test_rebuild_is_idempotent_and_persists(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first["graph_id"], second["graph_id"])
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        another = GetangiruGraphStore(self.store.path)
        graph = another.read(first["graph_id"], tenant=self.tenant, project_id=self.project)
        self.assertEqual(first["node_count"], graph["node_count"])

    def test_other_organizations_and_projects_have_no_access(self):
        original = self.build()
        with self.assertRaises(GraphScopeError):
            self.store.read(original["graph_id"], tenant="different", project_id=self.project)
        with self.assertRaises(GraphScopeError):
            self.store.read(original["graph_id"], tenant=self.tenant, project_id="proj_aaaaaaaaaaaa")
        self.assertNotEqual(original["graph_id"],
                            self.store.graph_id("different", self.project))

    def test_document_missing_actor_does_not_create_role_from_ontology(self):
        graph = self.build(source_text="Un banco investiga una falla. No hay más participantes.")
        self.assertEqual(0, graph["node_count"])
        self.assertEqual(0, graph["edge_count"])
        self.assertEqual(0, graph["fact_claims"])

    def test_large_documents_rejected_before_mutation(self):
        with self.assertRaises(ValueError):
            self.build(source_text=DOC + "x" * 251000)
        self.assertFalse(self.store.path.stat().st_size == 0) # DB exists

    def test_signed_memory_source_preserved_and_rebuilds_when_new(self):
        initial = self.build()
        memory = [{"source_id": "memory:episode001",
                   "content": "El SOC y Auditoría reciben nuevos datos; sin evidencia causal."}]
        updated = self.build(extra_sources=memory)
        self.assertFalse(updated["reused"])
        self.assertEqual(initial["graph_id"], updated["graph_id"])
        memory_edges = [e for e in updated["edges"] if
                        e["attributes"]["source_id"] == "memory:episode001"]
        self.assertTrue(memory_edges)
        self.assertTrue(all(e["attributes"]["asserted_fact"] is False for e in memory_edges))
        repeated = self.build(extra_sources=memory)
        self.assertTrue(repeated["reused"])

    def test_invalid_memory_provenance_is_rejected(self):
        with self.assertRaises(ValueError):
            self.build(extra_sources=[{"source_id": "../../bad",
                                      "content": "El SOC revisa registros"}])

    def test_delete_is_tenant_scoped(self):
        first = self.build()
        with self.assertRaises(GraphScopeError):
            self.store.delete(first["graph_id"], tenant="another", project_id=self.project)
        self.store.delete(first["graph_id"], tenant=self.tenant, project_id=self.project)
        with self.assertRaises(KeyError):
            self.store.read(first["graph_id"], tenant=self.tenant, project_id=self.project)

    def test_parallel_duplicate_builds_do_not_increase_counts(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.build(), range(8)))
        self.assertEqual(1, len({x["graph_id"] for x in results}))
        self.assertEqual(1, len({x["node_count"] for x in results}))
        self.assertEqual(1, len({x["edge_count"] for x in results}))


if __name__ == "__main__":
    unittest.main()
