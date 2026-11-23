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
import urllib.parse
from pathlib import Path

HOME = Path("/home/sprite/getangiru")
DATA = Path(os.environ.get("GETANGIRU_DATA_DIR", str(HOME / "data")))
SOURCE = DATA / "metadata.sqlite3"
STATE = DATA / "tenondera-sync.sqlite3"
SECRET = DATA / "tenondera-push-secret"
TARGET = (DATA / "tenondera-sync-target").read_text().strip() if (DATA / "tenondera-sync-target").exists() else "https://iapmpy.fly.dev"
PROJECT_RE = re.compile(r"^proj_[0-9a-f]{12}$")
TENANT = "tenondera"


def key() -> bytes:
    if not SECRET.is_file() or SECRET.stat().st_mode & 0o077:
        raise RuntimeError("Missing private push secret or unsafe permissions")
    value = SECRET.read_text(encoding="utf-8").strip().encode("utf-8")
    if len(value) < 32:
        raise RuntimeError("Weak push secret")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_target():
    parts=urllib.parse.urlsplit(TARGET)
    host=(parts.hostname or "").lower()
    approved=host=="iapmpy.fly.dev" or bool(re.fullmatch(r"[a-z0-9-]+\.trycloudflare\.com",host))
    if (not approved or parts.scheme!="https" or parts.username or parts.password
            or parts.port or parts.path not in ("", "/") or parts.query or parts.fragment):
        raise ValueError("Target is not an approved HTTPS integration endpoint")


def send(endpoint: str, payload: dict) -> tuple[int, dict]:
    validate_target()
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
        with urllib.request.build_opener(NoRedirect).open(req, timeout=7) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        # No private response bodies in logs or traces.
        return exc.code, {"success": False}


def state_db():
    con = sqlite3.connect(STATE, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS synced (id TEXT PRIMARY KEY, synced_at INTEGER NOT NULL)")
    return con


def sync_once() -> tuple[int, int, int]:
    """Select unsynced episodes across both durable SQLite files.

    Join avoids the original first-100 starvation once older episodes were
    already synchronized. Failed rows receive bounded retry backoff.
    """
    if not SOURCE.is_file():
        raise RuntimeError("Getangiru metadata database is missing")
    attempted=succeeded=skipped=0
    con=state_db()
    try:
        con.row_factory=sqlite3.Row
        con.execute("""CREATE TABLE IF NOT EXISTS retry (
            id TEXT PRIMARY KEY, failures INTEGER NOT NULL, next_attempt INTEGER NOT NULL
        )""")
        con.execute("ATTACH DATABASE ? AS source", (str(SOURCE),))
        now=int(time.time())
        rows=con.execute("""SELECT e.id,e.space,e.content,e.source_id,e.status
           FROM source.episodes e
           LEFT JOIN synced s ON s.id=e.id
           LEFT JOIN retry r ON r.id=e.id
           WHERE e.tenant=? AND e.status IN ('pending_llm','queued','indexed')
             AND s.id IS NULL AND (r.id IS NULL OR r.next_attempt<=?)
           ORDER BY e.created_at,e.id LIMIT 100""",(TENANT,now)).fetchall()
        for row in rows:
            ep=dict(row)
            if not PROJECT_RE.fullmatch(ep["space"]):
                skipped+=1
                # Unscoped records never leave this process.
                con.execute("INSERT OR REPLACE INTO retry VALUES(?,?,?)",(ep["id"],99,now+86400))
                con.commit()
                continue
            attempted+=1
            try:
                status,resp=send("/__getangiru/ingest", {
                    "project_id":ep["space"],"space":ep["space"],"episode_id":ep["id"],
                    "source_id":ep["source_id"],"content":ep["content"],"status":ep["status"],
                })
            except (OSError,ValueError,RuntimeError) as exc:
                print("sync_failed:",type(exc).__name__,file=sys.stderr)
                status=503
                resp={}
            if status in (200,201) and resp.get("success") is True:
                con.execute("INSERT OR IGNORE INTO synced(id,synced_at) VALUES(?,?)",(ep["id"],now))
                con.execute("DELETE FROM retry WHERE id=?",(ep["id"],))
                con.commit()
                succeeded+=1
            else:
                prior=con.execute("SELECT failures FROM retry WHERE id=?",(ep["id"],)).fetchone()
                failures=min(12,(prior["failures"] if prior else 0)+1)
                delay=min(3600,30*(2**min(failures,7)))
                if status in (401,403,530,502,503):
                    delay=max(delay,120)
                con.execute("INSERT OR REPLACE INTO retry VALUES(?,?,?)",(ep["id"],failures,now+delay))
                con.commit()
                print("not_synced: status",status,"episode_id_prefix",ep["id"][:8],file=sys.stderr)
                if status in (401,403,429,502,503,530):
                    break
        return attempted,succeeded,skipped
    finally:
        con.close()


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
