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

    def test_reject_local_incomplete_schema(self):
        with patch.dict(os.environ, {"LLM_LOCAL_INFERENCE": "true"}):
            fake = FakeClient({"entity_types": [{"name": "Company"}], "edge_types": []})
            gen = OntologyGenerator(llm_client=fake)
            with self.assertRaises(LLMResponseError):
                gen.generate(["Una empresa."], simulation_requirement="Simulación")

if __name__ == "__main__":
    unittest.main()
