"""Getangiru -> Tenonderã: outbound-only HTTPS project memory synchronization.

Run INSIDE the Getangiru Sprite; never run it on Tenonderã.
Only the dedicated 'tenondera' Getangiru tenant is eligible.
No external LLM, graph or embedding requests are made here.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path("/home/sprite/getangiru")
DATA = Path(os.environ.get("GETANGIRU_DATA_DIR", str(HOME / "data")))
SOURCE = DATA / "metadata.sqlite3"
STATE = DATA / "tenondera-sync.sqlite3"
SECRET = DATA / "tenondera-push-secret"
TARGET = "https://iapmpy.fly.dev"
PROJECT_RE = re.compile(r"^proj_[0-9a-f]{12}$")
TENANT = "tenondera"


def key() -> bytes:
    if not SECRET.is_file() or SECRET.stat().st_mode & 0o077:
        raise RuntimeError("Missing private push secret or unsafe permissions")
    value = SECRET.read_text(encoding="utf-8").strip().encode("utf-8")
    if len(value) < 32:
        raise RuntimeError("Weak push secret")
    return value


def send(endpoint: str, payload: dict) -> tuple[int, dict]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(body) > 6200:
        raise ValueError("Payload too large")
    ts, nonce = str(int(time.time())), secrets.token_hex(16)
    signature = hmac.new(key(), ts.encode() + b"." + nonce.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        TARGET + endpoint, data=body,
        headers={
            "Content-Type": "application/json",
            "X-Getangiru-Timestamp": ts,
            "X-Getangiru-Nonce": nonce,
            "X-Getangiru-Signature": signature,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=7) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        # No private response bodies in logs or traces.
        return exc.code, {"success": False}


def state_db():
    con = sqlite3.connect(STATE, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS synced (id TEXT PRIMARY KEY, synced_at INTEGER NOT NULL)")
    return con


def sync_once() -> tuple[int, int, int]:
    if not SOURCE.exists():
        raise RuntimeError("Getangiru metadata database is missing")
    with sqlite3.connect(SOURCE) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """SELECT id,space,content,source_id,status FROM episodes
               WHERE tenant=? AND status IN ('pending_llm','queued','indexed')
               ORDER BY created_at LIMIT 100""",
            (TENANT,),
        ).fetchall()
    attempted = succeeded = skipped = 0
    with state_db() as con:
        for row in rows:
            episode = dict(row)
            if not PROJECT_RE.fullmatch(episode["space"]):
                skipped += 1
                continue
            if con.execute("SELECT 1 FROM synced WHERE id=?", (episode["id"],)).fetchone():
                skipped += 1
                continue
            attempted += 1
            try:
                status, resp = send("/__getangiru/ingest", {
                    "project_id": episode["space"],
                    "space": episode["space"],
                    "episode_id": episode["id"],
                    "source_id": episode["source_id"],
                    "content": episode["content"],
                    "status": episode["status"],
                })
            except (OSError, ValueError, RuntimeError) as exc:
                print("sync_failed:", type(exc).__name__, file=sys.stderr)
                break
            if status in (200, 201) and resp.get("success") is True:
                con.execute("INSERT OR IGNORE INTO synced(id,synced_at) VALUES (?,?)", (episode["id"], int(time.time())))
                con.commit()
                succeeded += 1
            else:
                # Unavailable/nonexistent projects must not block other project spaces.
                print("not_synced: status", status, "episode_id_prefix", episode["id"][:8], file=sys.stderr)
        return attempted, succeeded, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ping", action="store_true", help="Authenticated no-data transport check")
    parser.add_argument("--once", action="store_true", help="Sync at most 100 pending items")
    parser.add_argument("--daemon", action="store_true", help="Periodic low-overhead synchronization")
    args = parser.parse_args()
    if args.ping:
        status, result = send("/__getangiru/ping", {"test": "getangiru-transport-v1"})
        print(json.dumps({"http": status, "authenticated": result.get("success") is True}))
        return 0 if status == 200 and result.get("success") else 1
    if not args.once and not args.daemon:
        parser.error("Choose --ping, --once or --daemon")
    while True:
        try:
            attempted, succeeded, skipped = sync_once()
            print(json.dumps({"attempted": attempted, "succeeded": succeeded, "skipped": skipped}), flush=True)
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
            print("sync_cycle_failed:", type(exc).__name__, file=sys.stderr, flush=True)
            if args.once:
                return 2
        if not args.daemon:
            break
        time.sleep(30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
