"""Getangiru Local Graph: deterministic, provenance-first, tenant-scoped SQLite.

This is the *local graph backend* shared by Tenonderã and Getangiru.
It does NOT assert ontology relation templates as real events, and it never
calls an LLM, a graph SaaS, or external APIs. Source sentences are untrusted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import unicodedata
from contextlib import closing
from pathlib import Path

_PROJECT = re.compile(r"^proj_[a-f0-9]{12}$")
_GRAPH = re.compile(r"^gtg_[a-f0-9]{24}$")
_WORD = re.compile(r"[a-z0-9]+")
# Explicit type -> source aliases. An inferred type is NOT instantiated unless
# actual input text contains an alias with proper word boundaries.
_ALIASES = {
    "SocTeam": ("soc", "centro de operaciones de seguridad"),
    "SecurityTeam": ("equipo de seguridad", "seguridad", "ciberseguridad"),
    "InfrastructureTeam": ("infraestructura", "infrastructure"),
    "FraudTeam": ("fraudes", "fraude", "antifraude"),
    "AuditTeam": ("auditoría", "auditoria", "auditores", "auditor"),
    "RiskTeam": ("riesgos", "riesgo integral", "gestión de riesgos"),
    "ExecutiveBoard": ("dirección", "direccion", "directorio", "gerencia"),
    "Vendor": ("proveedor", "proveedores", "contratista"),
    "Company": ("empresa", "compañía", "compania"),
    "Bank": ("banco", "entidad bancaria"),
    "Customer": ("cliente", "clientes"),
    "Regulator": ("regulador", "reguladora", "supervisor"),
    "University": ("universidad",),
    "Hospital": ("hospital",),
    "Doctor": ("médico", "medico", "doctora", "doctor"),
    "Patient": ("paciente", "pacientes"),
    "Lawyer": ("abogado", "abogada"),
    "Professor": ("profesor", "profesora", "docente"),
    "MediaOutlet": ("periódico", "periodico", "prensa", "medio de comunicación"),
}
MAX_TEXT = 250_000
MAX_SENTENCES = 1600
MAX_NODES = 250
MAX_EDGES = 400


def _normalize(value: str) -> str:
    chars = unicodedata.normalize("NFKD", value.casefold())
    clean = "".join(ch for ch in chars if not unicodedata.combining(ch))
    return " ".join(_WORD.findall(clean))


def _mentions(text: str, term: str) -> bool:
    return bool(re.search(r"(?:^|\s)" + re.escape(_normalize(term)) + r"(?:\s|$)", _normalize(text)))


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class GraphScopeError(ValueError):
    pass


class GetangiruGraphStore:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        c = sqlite3.connect(self.path, timeout=8)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=8000")
        return c

    def _initialize(self):
        with closing(self._connect()) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
            CREATE TABLE IF NOT EXISTS graphs (
              graph_id TEXT PRIMARY KEY,
              tenant TEXT NOT NULL,
              project_id TEXT NOT NULL,
              text_hash TEXT NOT NULL,
              ontology TEXT NOT NULL,
              built_at INTEGER NOT NULL,
              UNIQUE(tenant,project_id)
            );
            CREATE TABLE IF NOT EXISTS nodes (
              uuid TEXT PRIMARY KEY, graph_id TEXT NOT NULL REFERENCES graphs(graph_id) ON DELETE CASCADE,
              name TEXT NOT NULL, labels TEXT NOT NULL, quote TEXT NOT NULL,
              source_id TEXT NOT NULL, source_hash TEXT NOT NULL, attributes TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS edges (
              uuid TEXT PRIMARY KEY, graph_id TEXT NOT NULL REFERENCES graphs(graph_id) ON DELETE CASCADE,
              source_uuid TEXT NOT NULL REFERENCES nodes(uuid),
              target_uuid TEXT NOT NULL REFERENCES nodes(uuid),
              quote TEXT NOT NULL, source_id TEXT NOT NULL,
              attributes TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_graph_scope ON graphs(tenant,project_id);
            CREATE INDEX IF NOT EXISTS idx_node_graph ON nodes(graph_id);
            CREATE INDEX IF NOT EXISTS idx_edge_graph ON edges(graph_id);
            """)
            c.commit()

    @staticmethod
    def graph_id(tenant: str, project_id: str) -> str:
        if not _PROJECT.fullmatch(project_id) or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", tenant):
            raise GraphScopeError("Invalid tenant/project scope")
        return "gtg_" + _hash(tenant + "\0" + project_id)[:24]

    @staticmethod
    def _source_sentences(source: str):
        # Exact original quotes, bounded by sentence count and original size.
        source = source[:MAX_TEXT]
        return [s.strip()[:1500] for s in
                re.split(r"(?<=[.!?\n])\s+|\n+", source)
                if 3 <= len(s.strip())][:MAX_SENTENCES]

    def build(self, *, tenant: str, project_id: str, ontology: dict,
              source_text: str, source_id: str = "project-extracted-text"):
        gid = self.graph_id(tenant, project_id)
        if not isinstance(ontology, dict) or not isinstance(source_text, str):
            raise ValueError("Ontology and extracted text are required")
        if not source_text.strip():
            raise ValueError("Cannot construct graph from empty source")
        if len(source_text) > MAX_TEXT:
            raise ValueError("Document exceeds safe local graph limit")
        classes = ontology.get("entity_types") or []
        if not isinstance(classes, list) or len(classes) > 100:
            raise ValueError("Invalid ontology entity schema")
        digest = _hash(source_text + "\0" + json.dumps(ontology, sort_keys=True, ensure_ascii=False))
        sentences = self._source_sentences(source_text)
        if not sentences:
            raise ValueError("No textual evidence available")
        nodes, edges = [], []
        actors = {}
        for entry in classes:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name", "")
            if not isinstance(name, str) or not re.fullmatch(r"[A-Z][a-zA-Z0-9]{1,63}", name):
                continue
            for alias in _ALIASES.get(name, ()):
                excerpt = next((sentence for sentence in sentences if _mentions(sentence, alias)), None)
                if excerpt:
                    uid = "n_" + _hash(gid + "\0" + name + "\0" + _normalize(alias))[:32]
                    node = {
                        "uuid": uid, "name": alias, "labels": [name, "EvidenceBackedActor"],
                        "summary": "Actor mencionado expresamente en el documento. No implica conducta confirmada.",
                        "attributes": {"entity_type": name, "source_id": source_id,
                                       "evidence": excerpt[:500], "asserted_fact": False},
                        "created_at": None,
                    }
                    nodes.append(node)
                    actors[name] = node
                    break
            if len(nodes) >= MAX_NODES:
                break

        # Each edge means *co-occurrence in an original source sentence*, NOT
        # an inferred social relationship, causal link or ontology assertion.
        for sentence in sentences:
            present = [n for n in nodes if _mentions(sentence, n["name"])]
            if len(present) < 2:
                continue
            for i in range(len(present)):
                for j in range(i + 1, len(present)):
                    a, b = present[i], present[j]
                    key = "e_" + _hash(gid + "\0" + a["uuid"] + "\0" + b["uuid"] + "\0" + sentence)[:32]
                    edges.append({
                        "uuid": key, "name": "CO_MENTIONED",
                        "fact": "Co-mención en una misma oración; no acredita relación ni causalidad.",
                        "fact_type": "CO_MENTIONED",
                        "source_node_uuid": a["uuid"], "target_node_uuid": b["uuid"],
                        "source_node_name": a["name"], "target_node_name": b["name"],
                        "attributes": {"source_id": source_id, "evidence": sentence[:500],
                                       "asserted_fact": False, "relation_kind": "co_occurrence"},
                        "episodes": [], "created_at": None, "valid_at": None,
                        "invalid_at": None, "expired_at": None,
                    })
                    if len(edges) >= MAX_EDGES:
                        break
                if len(edges) >= MAX_EDGES:
                    break
            if len(edges) >= MAX_EDGES:
                break
        seen = set()
        edges = [e for e in edges if not (e["uuid"] in seen or seen.add(e["uuid"]))]
        schema_relations = [
            {"name": e.get("name"), "source_targets": e.get("source_targets") or [],
             "is_template": True, "asserted_fact": False}
            for e in (ontology.get("edge_types") or [])[:30] if isinstance(e, dict)
        ]
        with closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            old = c.execute("SELECT text_hash FROM graphs WHERE graph_id=? AND tenant=? AND project_id=?",
                            (gid, tenant, project_id)).fetchone()
            if old and old["text_hash"] == digest:
                c.rollback()
                return {**self.read(gid, tenant=tenant, project_id=project_id), "reused": True}
            if old:
                c.execute("DELETE FROM edges WHERE graph_id=?", (gid,))
                c.execute("DELETE FROM nodes WHERE graph_id=?", (gid,))
            c.execute("""INSERT INTO graphs(graph_id,tenant,project_id,text_hash,ontology,built_at)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(graph_id) DO UPDATE SET
                    text_hash=excluded.text_hash,ontology=excluded.ontology,built_at=excluded.built_at""",
                    (gid, tenant, project_id, digest, json.dumps(ontology, ensure_ascii=False), int(time.time())))
            for n in nodes:
                c.execute("""INSERT INTO nodes(uuid,graph_id,name,labels,quote,source_id,source_hash,attributes)
                             VALUES(?,?,?,?,?,?,?,?)""",
                          (n["uuid"], gid, n["name"], json.dumps(n["labels"]), n["attributes"]["evidence"],
                           source_id, _hash(n["attributes"]["evidence"]), json.dumps(n["attributes"],ensure_ascii=False)))
            for e in edges:
                c.execute("""INSERT INTO edges(uuid,graph_id,source_uuid,target_uuid,quote,source_id,attributes)
                             VALUES(?,?,?,?,?,?,?)""",
                          (e["uuid"], gid, e["source_node_uuid"], e["target_node_uuid"],
                           e["attributes"]["evidence"], source_id,
                           json.dumps(e["attributes"], ensure_ascii=False)))
            c.commit()
        return {**self.read(gid, tenant=tenant, project_id=project_id), "reused": False}

    def read(self, graph_id: str, *, tenant: str, project_id: str):
        expected = self.graph_id(tenant, project_id)
        if graph_id != expected:
            raise GraphScopeError("Graph does not belong to this project")
        with closing(self._connect()) as c:
            record = c.execute("SELECT ontology FROM graphs WHERE graph_id=? AND tenant=? AND project_id=?",
                               (graph_id, tenant, project_id)).fetchone()
            if not record:
                raise KeyError("Local graph not found")
            ns = c.execute("SELECT * FROM nodes WHERE graph_id=? ORDER BY name", (graph_id,)).fetchall()
            es = c.execute("SELECT * FROM edges WHERE graph_id=? ORDER BY uuid", (graph_id,)).fetchall()
        nodes = [{
            "uuid": n["uuid"], "name": n["name"], "labels": json.loads(n["labels"]),
            "summary": "Actor respaldado por una mención en el documento.",
            "attributes": json.loads(n["attributes"]), "created_at": None,
        } for n in ns]
        lookup = {n["uuid"]: n["name"] for n in nodes}
        edges = [{
            "uuid": e["uuid"], "name": "CO_MENTIONED", "fact_type": "CO_MENTIONED",
            "fact": "Co-mención documentada; no prueba una relación factual.",
            "source_node_uuid": e["source_uuid"], "target_node_uuid": e["target_uuid"],
            "source_node_name": lookup.get(e["source_uuid"], ""),
            "target_node_name": lookup.get(e["target_uuid"], ""),
            "attributes": json.loads(e["attributes"]), "episodes": [],
            "created_at": None, "valid_at": None, "invalid_at": None, "expired_at": None,
        } for e in es]
        ontology = json.loads(record["ontology"])
        return {
            "graph_id": graph_id, "nodes": nodes, "edges": edges,
            "node_count": len(nodes), "edge_count": len(edges),
            "entity_types": [x.get("name") for x in ontology.get("entity_types", []) if isinstance(x, dict)],
            "schema_relations": [{"name": e.get("name"), "source_targets": e.get("source_targets") or [],
                                  "is_template": True, "asserted_fact": False}
                                 for e in ontology.get("edge_types", []) if isinstance(e, dict)],
            "backend": "getangiru-local", "fact_claims": 0,
            "graph_semantics": "Evidence-backed actors and co-mentions, not factual causal relationships",
        }

    def delete(self, graph_id: str, *, tenant: str, project_id: str):
        if graph_id != self.graph_id(tenant, project_id):
            raise GraphScopeError("Graph does not belong to this project")
        with closing(self._connect()) as c:
            c.execute("DELETE FROM graphs WHERE graph_id=? AND tenant=? AND project_id=?",
                      (graph_id, tenant, project_id))
            c.commit()


def default_store(upload_folder: str | Path) -> GetangiruGraphStore:
    return GetangiruGraphStore(Path(upload_folder) / "getangiru" / "graphs.sqlite3")
