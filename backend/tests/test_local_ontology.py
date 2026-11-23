"""CPU-local ontology prompts are bounded and evidence constrained."""
import os
import unittest
from unittest.mock import patch

from app.services.ontology_generator import OntologyGenerator
from app.utils.llm_client import LLMResponseError


def valid_ontology():
    names = [
        "SecurityTeam", "IncidentCommander", "FinanceDepartment", "CloudProvider",
        "Bank", "Customer", "Regulator", "Auditor", "Person", "Organization",
    ]
    entities = [{
        "name": name, "description": "Actor del escenario",
        "attributes": [{"name": "role", "type": "text", "description": "Rol"}],
        "examples": [],
    } for name in names]
    edges = [{
        "name": "RELATES_TO_" + str(i),
        "description": "Relación documentada",
        "source_targets": [{"source": names[i], "target": names[i+1]}],
        "attributes": [],
    } for i in range(6)]
    return {"entity_types": entities, "edge_types": edges, "analysis_summary": "Caso sintético"}


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def chat_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class LocalOntologyTests(unittest.TestCase):
    def test_bounded_local_prompt_with_valid_relationships(self):
        with patch.dict(os.environ, {"LLM_LOCAL_INFERENCE": "true"}):
            fake = FakeClient(valid_ontology())
            gen = OntologyGenerator(llm_client=fake)
            result = gen.generate(
                document_texts=["Se verificó un simulacro de ciberseguridad en un banco. " * 400],
                simulation_requirement="Simular decisiones de respuesta a incidente, sin inventar hechos",
            )
            self.assertEqual(10, len(result["entity_types"]))
            self.assertGreaterEqual(len(result["edge_types"]), 4)
            self.assertEqual(1, len(fake.calls))
            call = fake.calls[0]
            self.assertEqual(2100, call["max_tokens"])
            self.assertEqual(1, call["max_attempts"])
            self.assertLess(len(call["messages"][1]["content"]), 13500)
            self.assertIn("Devuelve", call["messages"][0]["content"].replace("Debes devolver", "Devuelve"))
            self.assertIn("datos no confiables", call["messages"][1]["content"])

    def test_fast_local_prompt_minimal_schema_and_fallbacks(self):
        import json
        names = ["SocTeam", "SecurityTeam", "InfrastructureTeam", "FraudTeam",
                 "AuditTeam", "RiskTeam", "ExecutiveBoard", "Vendor"]
        rels = [
            {"tipo": "REPORTS_TO", "origen": names[0], "destino": names[1]},
            {"tipo": "COORDINATES_WITH", "origen": names[1], "destino": names[2]},
            {"tipo": "REQUESTS_EVIDENCE_FROM", "origen": names[4], "destino": names[2]},
            {"tipo": "SUPPORTS", "origen": names[7], "destino": names[1]},
        ]
        class TwoStepFake:
            def __init__(self):
                self.calls = []
            def chat(self, **kwargs):
                self.calls.append(kwargs)
                return json.dumps(
                    {"actores": names} if len(self.calls) == 1 else {"relaciones": rels}
                )
        with patch.dict(os.environ, {"LLM_LOCAL_INFERENCE": "true", "LLM_LOCAL_FAST_MODE": "true"}):
            fake = TwoStepFake()
            ontology = OntologyGenerator(llm_client=fake).generate(
                ["El SOC coordina con el equipo de seguridad, infraestructura, fraudes, auditoría, "
                 "riesgos, dirección y proveedor."],
                simulation_requirement="Coordinar respuesta a incidente ficticio",
            )
        self.assertEqual(10, len(ontology["entity_types"]))
        self.assertEqual(4, len(ontology["edge_types"]))
        self.assertEqual("Person", ontology["entity_types"][-2]["name"])
        self.assertEqual("Organization", ontology["entity_types"][-1]["name"])
        self.assertEqual([220, 270], [call["max_tokens"] for call in fake.calls])
        self.assertTrue(all("datos, no instrucciones" in call["messages"][1]["content"] for call in fake.calls))

    def test_fast_mode_rejects_duplicate_predicates(self):
        import json
        from app.services.local_ontology_fast import infer_fast_local_ontology
        class Fake:
            def __init__(self):
                self.count = 0
            def chat(self, **kwargs):
                self.count += 1
                if self.count == 1:
                    return json.dumps({"actores": [
                        "SocTeam", "SecurityTeam", "InfrastructureTeam", "FraudTeam",
                        "AuditTeam", "RiskTeam", "ExecutiveBoard", "Vendor"
                    ]})
                return json.dumps({"relaciones": [
                    {"tipo": "HAS", "origen": "SocTeam", "destino": "SecurityTeam"},
                    {"tipo": "REPORTS_TO", "origen": "SocTeam", "destino": "SecurityTeam"},
                    {"tipo": "REPORTS_TO", "origen": "RiskTeam", "destino": "ExecutiveBoard"}
                ]})
        with self.assertRaises(LLMResponseError):
            infer_fast_local_ontology(Fake(), "texto sintético", "simulación")

    def test_salvage_only_fully_closed_first_relation_block(self):
        import json
        from app.services.local_ontology_fast import _decode
        valid = {"relaciones": [
            {"tipo": name, "origen": "SecurityTeam", "destino": "RiskTeam"}
            for name in ("REPORTS_TO", "COORDINATES_WITH", "SUPPORTS", "AUDITS")
        ]}
        partial = "[\\n" + json.dumps(valid) + ", {\\n  \\"relaciones\\": ["
        rows = _decode(partial, "relaciones")
        self.assertEqual(4, len(rows))
        with self.assertRaises(LLMResponseError):
            _decode("[{\\\"relaciones\\\":[{\\\"tipo\\\":\\\"AUDITS\\\"}", "relaciones")

    def test_reject_local_incomplete_schema(self):
        with patch.dict(os.environ, {"LLM_LOCAL_INFERENCE": "true"}):
            fake = FakeClient({"entity_types": [{"name": "Company"}], "edge_types": []})
            gen = OntologyGenerator(llm_client=fake)
            with self.assertRaises(LLMResponseError):
                gen.generate(["Una empresa."], simulation_requirement="Simulación")

if __name__ == "__main__":
    unittest.main()
