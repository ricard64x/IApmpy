"""Getangiru-native graph API: on-device SQLite engine, tenant-authenticated.

Exposes only bounded graph rebuild/read/delete. Episodes already accepted by
the Getangiru tenant are the sole source, with no remote model call.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from graph_store import GetangiruGraphStore, GraphScopeError


class RebuildInput(BaseModel):
    ontology: dict
    max_episodes: int = Field(default=60, ge=1, le=100)


def create_graph_router(*, require_tenant, valid_space, db, data_dir):
    router = APIRouter(prefix="/v1/graphs", tags=["graph"])
    store = GetangiruGraphStore(data_dir / "getangiru-graphs.sqlite3")

    @router.post("/{space}/rebuild", status_code=201)
    def rebuild(space: str, request: RebuildInput, tenant: str = Depends(require_tenant)):
        space = valid_space(space)
        try:
            with db() as c:
                rows = c.execute("""
                    SELECT id,source_id,content FROM episodes
                    WHERE tenant=? AND space=? ORDER BY created_at DESC LIMIT ?
                """, (tenant, space, request.max_episodes)).fetchall()
            if not rows:
                raise HTTPException(422, "No existe evidencia para construir el grafo")
            chunks = list(reversed(rows))
            content = "\n".join(r["content"] for r in chunks)
            result = store.build(
                tenant=tenant, project_id=space, ontology=request.ontology,
                source_text=content, source_id="getangiru-episodes",
            )
            return {"graph_id": result["graph_id"], "node_count": result["node_count"],
                    "edge_count": result["edge_count"],
                    "schema_relation_count": len(result["schema_relations"]),
                    "asserted_fact_count": 0, "reused": result["reused"],
                    "provider_calls": 0, "backend": "getangiru-local"}
        except GraphScopeError:
            raise HTTPException(422, "Identificador de proyecto inválido")
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @router.get("/{space}")
    def read(space: str, tenant: str = Depends(require_tenant)):
        space = valid_space(space)
        try:
            graph_id = store.graph_id(tenant, space)
            return store.read(graph_id, tenant=tenant, project_id=space)
        except GraphScopeError:
            raise HTTPException(422, "Identificador de proyecto inválido")
        except KeyError:
            raise HTTPException(404, "Grafo no encontrado")

    @router.delete("/{space}")
    def delete(space: str, tenant: str = Depends(require_tenant)):
        space = valid_space(space)
        try:
            graph_id = store.graph_id(tenant, space)
            store.delete(graph_id, tenant=tenant, project_id=space)
            return {"deleted": True, "project": space}
        except GraphScopeError:
            raise HTTPException(422, "Identificador de proyecto inválido")

    return router
