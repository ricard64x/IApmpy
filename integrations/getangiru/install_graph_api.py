"""Idempotent installer for the native Getangiru graph module.

Usage: python integrations/getangiru/install_graph_api.py /home/sprite/getangiru
Never modifies tenants, credentials, or existing episode database.
"""
from __future__ import annotations
import os
import shutil
import sys
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "backend/app/services/getangiru_graph_engine.py"
ROUTES = ROOT / "integrations/getangiru/graph_routes.py"
PATCH = """# Authenticated native graph API (no third-party graph provider).
from graph_routes import create_graph_router
app.include_router(create_graph_router(require_tenant=require_tenant, valid_space=valid_space, db=db, data_dir=DATA))
"""

def install(target: Path):
    app = target / "app.py"
    if not app.is_file():
        raise FileNotFoundError("Getangiru app.py not found")
    for source, dest in ((MODULE, target / "graph_store.py"),
                         (ROUTES, target / "graph_routes.py")):
        # Replacing code is intended. Never touch databases or tokens.
        dest.write_bytes(source.read_bytes())
        dest.chmod(0o644)
        py_compile.compile(str(dest), doraise=True)
    content = app.read_text()
    if PATCH not in content:
        if "from graph_routes import create_graph_router" in content:
            raise RuntimeError("An incompatible Getangiru graph route patch exists")
        backup = app.with_name("app.pre-native-getangiru-graph.py")
        if not backup.exists():
            backup.write_text(content)
            backup.chmod(0o644)
        app.write_text(content.rstrip() + "\n\n" + PATCH)
    py_compile.compile(str(app), doraise=True)
    print("Getangiru native graph adapter installed (restart required)")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Expected Getangiru app root as one argument")
    install(Path(sys.argv[1]).resolve())
