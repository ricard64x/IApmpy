"""Regression checks for opt-in, synthetic GPT runner without API credentials."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "backend" / "scripts" / "run_lightweight_simulation.py"
SPEC = importlib.util.spec_from_file_location("lightweight_simulation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def read_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


class LightweightSimulationTests(unittest.TestCase):
    def _scenario(self, directory, profiles=60):
        base = Path(directory)
        records = [{
            "user_id": 1000+i,
            "name": f"Participante sintético {i+1}",
            "persona": f"Perfil sintético {i+1}: considera confianza, fraude y disponibilidad."
        } for i in range(profiles)]
        (base / "reddit_profiles.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        config = {
            "simulation_id": "sim_mock",
            "time_config": {"total_simulation_hours": 5, "minutes_per_round": 30},
            "event_config": {"description":"Escenario ficticio de pagos y confianza."},
            "agent_configs": [{"agent_id": p["user_id"]} for p in records],
        }
        file = base / "simulation_config.json"
        file.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return file

    def test_sixty_profiles_ten_rounds_minimal_calls(self):
        calls = []
        def mock(system, prompt):
            self.assertIn("ESCENARIO FICTICIO", system)
            data = json.loads(prompt)
            calls.append(data)
            return {"actions":[
                {"agent_id": actor["id"], "content": (
                    f"Yo {actor['nombre']} considero importante verificar las operaciones "
                    f"y contar con explicaciones claras antes de utilizar el servicio ficticio."
                )}
                for actor in data["participantes"]
            ]}
        with tempfile.TemporaryDirectory() as root:
            result = MODULE.execute(self._scenario(root), "parallel", 10, mock)
            self.assertEqual((result["profiles"], result["actions"], result["rounds"]), (60,60,10))
            self.assertLessEqual(len(calls), 20)
            both = []
            per_platform = {}
            for name in ("twitter","reddit"):
                data = read_jsonl(Path(root) / name / "actions.jsonl")
                self.assertEqual(sum(r.get("event_type") == "round_end" for r in data),10)
                self.assertEqual(sum(r.get("event_type") == "simulation_end" for r in data),1)
                actions = [row for row in data if row.get("action_type") == "CREATE_POST"]
                self.assertEqual(data[-1]["total_actions"],len(actions))
                self.assertTrue(all(row.get("source_mode") == "sintetico_gpt_liviano" for row in actions))
                self.assertTrue(all(row["action_args"]["content"] for row in actions))
                both.extend(a["agent_id"] for a in actions)
                per_platform[name] = len(actions)
            self.assertEqual(len(both),60)
            self.assertEqual(len(set(both)),60)
            self.assertGreater(per_platform["twitter"],0)
            self.assertGreater(per_platform["reddit"],0)
            self.assertLess(result["peak_rss_kib"],512*1024)
            self.assertTrue((Path(root)/"lightweight_metrics.jsonl").exists())

    def test_invalid_llm_response_never_generates_fabricated_actions_or_completion(self):
        with tempfile.TemporaryDirectory() as root:
            config=self._scenario(root,8)
            def incomplete(system,prompt):
                actor=json.loads(prompt)["participantes"][0]
                return {"actions":[{"agent_id":actor["id"],"content":"Respuesta que omite personas del lote"}]}
            with self.assertRaisesRegex(ValueError,"Faltan acciones"):
                MODULE.execute(config,"twitter",1,incomplete)
            data=read_jsonl(Path(root)/"twitter"/"actions.jsonl")
            self.assertFalse(any(x.get("event_type") == "simulation_end" for x in data))
            self.assertFalse(any(x.get("action_type") == "CREATE_POST" for x in data))

    def test_resume_requires_controlled_restart_and_keeps_previous_logs(self):
        with tempfile.TemporaryDirectory() as root:
            config=self._scenario(root,1)
            def mock(system,prompt):
                person=json.loads(prompt)["participantes"][0]
                return {"actions":[{"agent_id":person["id"],"content":"Respuesta sintética adecuada con contexto de prueba de seguridad."}]}
            MODULE.execute(config,"twitter",1,mock)
            original=(Path(root)/"twitter"/"actions.jsonl").read_bytes()
            with self.assertRaisesRegex(RuntimeError,"eventos anteriores"):
                MODULE.execute(config,"twitter",1,mock)
            self.assertEqual(original,(Path(root)/"twitter"/"actions.jsonl").read_bytes())

    def test_invalid_profile_ids_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            config=self._scenario(root,2)
            records=json.loads((Path(root)/"reddit_profiles.json").read_text())
            records[1]["user_id"]=records[0]["user_id"]
            (Path(root)/"reddit_profiles.json").write_text(json.dumps(records))
            with self.assertRaisesRegex(ValueError,"duplicados"):
                MODULE.execute(config,"twitter",1,lambda *args:{"actions":[]})


if __name__=="__main__":
    unittest.main()
