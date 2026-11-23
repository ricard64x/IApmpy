"""Inbound, authenticated Getangiru memory mirror.

Getangiru remains a separate service. It PUSHES selected, project-scoped
memories over HTTPS to this endpoint. Tenonderã never reaches into its DB,
shares its Zep/LLM credentials, or treats retrieved text as instructions.

Configuration: GETANGIRU_MIRROR_ENABLED=true, GETANGIRU_PUSH_SECRET (secret).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from contextlib import contextmanager

from flask import Blueprint, jsonify, request

from ..config import Config

getangiru_bp = Blueprint("getangiru", __name__)
_PROJECT = re.compile(r"^proj_[a-f0-9]{12}$")
_SIGNED_WINDOW = 120
_MAX_BYTES = 6200


def _db_path() -> Path:
    path = Path(Config.UPLOAD_FOLDER) / "getangiru" / "mirror.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    return path


@contextmanager
def _db():
    path = _db_path()
    connection = sqlite3.connect(str(path), timeout=10)
    os.chmod(path, 0o600)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=10000")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""CREATE TABLE IF NOT EXISTS received (
      project_id TEXT NOT NULL, episode_id TEXT NOT NULL,
      source_id TEXT, content TEXT NOT NULL, status TEXT NOT NULL,
      inserted_at INTEGER NOT NULL,
      PRIMARY KEY(project_id, episode_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS nonces (
      nonce TEXT PRIMARY KEY, timestamp INTEGER NOT NULL
    )""")
    connection.execute("CREATE INDEX IF NOT EXISTS ix_received_project ON received(project_id,inserted_at)")
    try:
        yield connection
    finally:
        connection.close()


def _enabled() -> bool:
    return os.getenv("GETANGIRU_MIRROR_ENABLED", "false").lower() == "true"


def _check_signature(raw: bytes):
    """Verify before parsing JSON, then reject replays durably."""
    if not _enabled():
        return jsonify({"success": False, "error": "Integración deshabilitada"}), 503
    secret = os.getenv("GETANGIRU_PUSH_SECRET", "")
    if len(secret) < 32:
        return jsonify({"success": False, "error": "Integración sin credenciales"}), 503
    if len(raw) > _MAX_BYTES:
        return jsonify({"success": False, "error": "Solicitud excede límite"}), 413
    ts = request.headers.get("X-Getangiru-Timestamp", "")
    nonce = request.headers.get("X-Getangiru-Nonce", "")
    signature = request.headers.get("X-Getangiru-Signature", "")
    if not ts.isascii() or not ts.isdecimal() or len(ts) > 12 or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        return jsonify({"success": False, "error": "Autenticación inválida"}), 401
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
        return jsonify({"success": False, "error": "Autenticación inválida"}), 401
    if abs(int(time.time()) - int(ts)) > _SIGNED_WINDOW:
        return jsonify({"success": False, "error": "Firma vencida"}), 401
    expected = hmac.new(secret.encode("utf-8"), ts.encode() + b"." + nonce.encode() + b"." + raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return jsonify({"success": False, "error": "Autenticación inválida"}), 401
    # Authenticated requests reserve nonce before mutation. A repeated body
    # with the same nonce is a replay; idempotent duplicates need a fresh nonce.
    with _db() as conn:
        with conn:
            conn.execute("DELETE FROM nonces WHERE timestamp < ?", (int(time.time()) - 300,))
            try:
                conn.execute("INSERT INTO nonces(nonce,timestamp) VALUES(?,?)", (nonce, int(ts)))
            except sqlite3.IntegrityError:
                return jsonify({"success": False, "error": "Solicitud repetida"}), 409
    return None


@getangiru_bp.post("/__getangiru/ingest")
def ingest():
    raw = request.get_data(cache=False)
    error = _check_signature(raw)
    if error is not None:
        return error
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return jsonify({"success": False, "error": "JSON inválido"}), 400
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "Formato inválido"}), 400
    project = payload.get("project_id")
    episode = payload.get("episode_id")
    space = payload.get("space")
    content = payload.get("content")
    status = payload.get("status")
    source = payload.get("source_id")
    if not isinstance(project, str) or not _PROJECT.fullmatch(project) or space != project:
        return jsonify({"success": False, "error": "Proyecto/espacio inválido"}), 422
    try:
        uuid.UUID(str(episode))
    except (TypeError, ValueError, AttributeError):
        return jsonify({"success": False, "error": "Episodio inválido"}), 422
    if not isinstance(content, str) or not (1 <= len(content) <= 4000):
        return jsonify({"success": False, "error": "Contenido inválido"}), 422
    if status not in ("pending_llm", "queued", "indexed"):
        return jsonify({"success": False, "error": "Estado inválido"}), 422
    if source is not None and (not isinstance(source, str) or len(source) > 128):
        return jsonify({"success": False, "error": "Fuente inválida"}), 422
    # A signed sender cannot create arbitrary project IDs. User ownership is
    # checked separately on every read.
    if not (Path(Config.UPLOAD_FOLDER) / "projects" / project / "project.json").is_file():
        return jsonify({"success": False, "error": "Proyecto inexistente"}), 404
    with _db() as conn:
        with conn:
            old = conn.execute(
                "SELECT content FROM received WHERE project_id=? AND episode_id=?",
                (project, str(episode)),
            ).fetchone()
            if old:
                if old["content"] != content:
                    return jsonify({"success": False, "error": "Episodio modificado"}), 409
                return jsonify({"success": True, "duplicate": True, "episode_id": str(episode)})
            conn.execute(
                "INSERT INTO received(project_id,episode_id,source_id,content,status,inserted_at) VALUES(?,?,?,?,?,?)",
                (project, str(episode), source, content, status, int(time.time())),
            )
    return jsonify({"success": True, "stored": True, "episode_id": str(episode)}), 201


@getangiru_bp.post("/__getangiru/ping")
def integration_ping():
    """Prove transport/auth with no private data or persistent source mutation."""
    error = _check_signature(request.get_data(cache=False))
    if error is not None:
        return error
    return jsonify({"success": True, "service": "tenondera", "bridge": "getangiru-v1"})


@getangiru_bp.get("/api/getangiru/project/<project_id>/search")
def local_search(project_id):
    from ..auth import can_access_project
    if not _enabled():
        return jsonify({"success": False, "error": "Integración deshabilitada"}), 503
    if not _PROJECT.fullmatch(project_id) or not can_access_project(project_id):
        return jsonify({"success": False, "error": "Proyecto no disponible"}), 404
    query = request.args.get("q", "")
    if not 2 <= len(query) <= 256:
        return jsonify({"success": False, "error": "Consulta entre 2 y 256 caracteres"}), 422
    limit = request.args.get("limit", "8")
    if not limit.isdigit() or not 1 <= int(limit) <= 25:
        return jsonify({"success": False, "error": "Límite inválido"}), 422
    term = "%" + query.replace("~", "~~").replace("%", "~%").replace("_", "~_") + "%"
    with _db() as conn:
        rows = conn.execute(
            """SELECT episode_id,source_id,substr(content,1,2000) AS content,status
               FROM received WHERE project_id=? AND content LIKE ? ESCAPE '~'
               ORDER BY inserted_at DESC LIMIT ?""",
            (project_id, term, int(limit)),
        ).fetchall()
    return jsonify({"success": True, "mode": "local_text", "items": [dict(row) for row in rows],
                    "provider_calls": 0})

# A second, public-only namespace. No research content is ever inserted into
# private project memory without an explicit user workflow.
_PUBLIC_TOPICS = {"fraude","vulnerabilidad","ia","paraguay","social"}
_SOURCE_HOSTS = {"www.cisa.gov","news.google.com","mastodon.social"}

@getangiru_bp.post("/__getangiru/public-source")
def ingest_public_source():
    """Signed, bounded and idempotent public citations sent by Getangiru."""
    from urllib.parse import urlsplit
    raw=request.get_data(cache=False)
    error=_check_signature(raw)
    if error is not None:
        return error
    try:
        payload=json.loads(raw)
    except (ValueError,UnicodeDecodeError):
        return jsonify({"success":False,"error":"JSON inválido"}),400
    if not isinstance(payload,dict) or set(payload)!={"items"}:
        return jsonify({"success":False,"error":"Formato inválido"}),422
    rows=payload["items"]
    if not isinstance(rows,list) or not 1<=len(rows)<=6:
        return jsonify({"success":False,"error":"Lote público inválido"}),422
    clean=[]
    for entry in rows:
        if not isinstance(entry,dict) or set(entry)!={"id","source","url","title","summary","published","topic"}:
            return jsonify({"success":False,"error":"Campos públicos inválidos"}),422
        url=entry["url"]
        if not isinstance(url,str) or len(url)>850:
            return jsonify({"success":False,"error":"URL inválida"}),422
        parts=urlsplit(url)
        if (parts.scheme!="https" or parts.hostname not in _SOURCE_HOSTS or parts.username
            or parts.password or parts.port or parts.fragment):
            return jsonify({"success":False,"error":"Origen no autorizado"}),422
        identifier=hashlib.sha256(url.encode()).hexdigest()
        if entry["id"]!=identifier:
            return jsonify({"success":False,"error":"ID de origen inválido"}),422
        if entry["topic"] not in _PUBLIC_TOPICS:
            return jsonify({"success":False,"error":"Tema inválido"}),422
        if any(not isinstance(entry[k],str) for k in ("source","title","summary","published")):
            return jsonify({"success":False,"error":"Campos de texto inválidos"}),422
        if not (8<=len(entry["title"])<=240 and len(entry["summary"])<=480 and len(entry["published"])<=100 and len(entry["source"])<=50):
            return jsonify({"success":False,"error":"Límite de texto excedido"}),422
        clean.append((identifier,entry["source"],url,entry["title"],entry["summary"],
                      entry["published"],entry["topic"],int(time.time())))
    path=Path(Config.UPLOAD_FOLDER)/"getangiru"/"public-context.sqlite3"
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with sqlite3.connect(str(path),timeout=10) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS public_sources(
          id TEXT PRIMARY KEY,source TEXT,url TEXT,title TEXT,summary TEXT,
          published TEXT,topic TEXT,received_at INTEGER)""")
        conn.executemany("""INSERT INTO public_sources VALUES(?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO NOTHING""",clean)
        conn.execute("DELETE FROM public_sources WHERE received_at<?",(int(time.time())-90*86400,))
        conn.commit()
    os.chmod(path,0o600)
    return jsonify({"success":True,"received":len(clean)}),201
