"""Production WSGI entry point. Fail fast on missing API credentials."""

from app.config import Config

missing = Config.validate()
if missing:
    raise RuntimeError("Missing required deployment configuration: " + "; ".join(missing))

from app import create_app

app = create_app()
