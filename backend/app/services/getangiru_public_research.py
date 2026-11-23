"""Opt-in external public CVE lookup with fixed CISA KEV source only.

No user documents, project identifiers, prompts, account data, or dynamic URLs
are ever sent. There is no arbitrary web browsing or SSRF capability.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
import urllib.request
from pathlib import Path

FEED = "https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"
CVE = re.compile(r"^CVE-(19[9]\d|20\d{2})-\d{4,10}$")
CACHE_SECONDS = 12 * 60 * 60
MAX_FEED_BYTES = 3_000_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _read_feed(cache_path: Path, fetcher=None) -> dict:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.is_file() and time.time()-cache_path.stat().st_mtime < CACHE_SECONDS:
        try:
            data = json.loads(cache_path.read_text())
            if isinstance(data,dict) and isinstance(data.get("vulnerabilities"),list):
                return data
        except (OSError,ValueError):
            pass

    if fetcher is None:
        opener=urllib.request.build_opener(NoRedirect)
        req=urllib.request.Request(FEED, headers={"User-Agent":"Getangiru-CVE-Public-Lookup/1.0"})
        with opener.open(req,timeout=8.0) as response:
            if response.status!=200:
                raise RuntimeError("Fuente pública indisponible")
            raw=response.read(MAX_FEED_BYTES+1)
    else:
        raw=fetcher(FEED)
    if len(raw)>MAX_FEED_BYTES:
        raise ValueError("La fuente pública excede el tamaño permitido")
    data=json.loads(raw)
    if not isinstance(data,dict) or not isinstance(data.get("vulnerabilities"),list):
        raise ValueError("Formato de fuente pública inválido")
    # Atomic cache replacement; never persist private user inputs.
    temp=cache_path.with_suffix(".new")
    with open(temp,"wb") as writer:
        os.chmod(temp,0o600)
        writer.write(raw)
        writer.flush()
        os.fsync(writer.fileno())
    os.replace(temp,cache_path)
    return data


def lookup_public_cves(cves: list[str], cache_path: str | Path, fetcher=None) -> dict:
    if (not isinstance(cves,list) or not 1<=len(cves)<=5
            or any(not isinstance(v,str) or not CVE.fullmatch(v) for v in cves)):
        raise ValueError("Ingresá entre 1 y 5 identificadores CVE válidos")
    ids=list(dict.fromkeys(cves))
    feed=_read_feed(Path(cache_path), fetcher)
    selected={row.get("cveID"):row for row in feed["vulnerabilities"]
              if isinstance(row,dict) and row.get("cveID") in ids}
    entries=[]
    for cve in ids:
        record=selected.get(cve)
        entries.append({
            "cve":cve,"listed_in_kev":bool(record),
            "date_added":record.get("dateAdded") if record else None,
            "vendor":record.get("vendorProject","")[:100] if record else None,
            "product":record.get("product","")[:100] if record else None,
            "remediation_due":record.get("dueDate") if record else None,
        })
    return {
        "source":"CISA KEV (copia oficial publicada por CISAgov)",
        "feed":FEED,
        "catalog_version":feed.get("catalogVersion"),
        "catalog_updated":feed.get("dateReleased"),
        "entries":entries,
        "interpretation":"Ausencia del catálogo no prueba que una vulnerabilidad no sea explotada.",
        "private_documents_sent":0,
        "model_calls":0,
    }
