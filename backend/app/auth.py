"""Tenonderã: persistent administrator-managed accounts and secure sessions.

Single Fly Machine deployment: encrypted ext4 volume at Config.UPLOAD_FOLDER.
No public signup. Existing unowned projects remain accessible only to admin.
"""
from __future__ import annotations

import hmac
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import timedelta
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .config import Config

auth_bp = Blueprint("auth", __name__)
ROLES = ("administrator", "analyst", "researcher")
USERNAME = re.compile(r"^[a-zA-Z0-9_.@-]{3,96}$")
SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")


def database_path() -> Path:
    return Path(Config.UPLOAD_FOLDER) / "auth" / "users.sqlite3"


def connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=10000")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize_accounts():
    if not os.environ.get("APP_BASIC_AUTH_PASSWORD"):
        # Never start production in a state where anyone can create an admin.
        raise RuntimeError("APP_BASIC_AUTH_PASSWORD is required for initial admin")
    with connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              username TEXT NOT NULL UNIQUE COLLATE NOCASE,
              name TEXT NOT NULL,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL CHECK (role IN ('administrator','analyst','researcher')),
              active INTEGER NOT NULL DEFAULT 1,
              must_change_password INTEGER NOT NULL DEFAULT 0,
              created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS project_owners (
              project_id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS failed_logins (
              ip_hash TEXT PRIMARY KEY, count INTEGER NOT NULL, window_start INTEGER NOT NULL
            );
        """)
        admin = con.execute("SELECT id FROM users WHERE role='administrator' LIMIT 1").fetchone()
        if not admin:
            con.execute(
                "INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
                (
                    uuid.uuid4().hex,
                    os.environ.get("APP_BASIC_AUTH_USER", "admin").strip().lower(),
                    "Administrador",
                    generate_password_hash(os.environ["APP_BASIC_AUTH_PASSWORD"]),
                    "administrator", 1, 1, int(time.time()),
                ),
            )
        # The auth database must not be world-readable on the mounted volume.
        try:
            os.chmod(database_path(), 0o600)
        except OSError:
            pass


def get_user(user_id: str | None):
    if not user_id:
        return None
    with connect() as con:
        found = con.execute(
            "SELECT id,username,name,role,active,must_change_password FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(found) if found else None


def public_user(user: dict) -> dict:
    return {key: user[key] for key in ("id", "username", "name", "role", "active", "must_change_password")}


def current_user():
    return getattr(g, "tenondera_user", None)


def is_admin():
    user = current_user()
    return bool(user and user["role"] == "administrator")


def project_owner(project_id: str):
    if not project_id or not SAFE_ID.fullmatch(project_id):
        return None
    with connect() as con:
        row = con.execute("SELECT user_id FROM project_owners WHERE project_id=?", (project_id,)).fetchone()
        if row:
            return row["user_id"]
        # A project created before multiuser migration is legacy admin data.
        # The file check avoids treating arbitrary nonexistent ids as owned.
        if not (Path(Config.UPLOAD_FOLDER) / "projects" / project_id / "project.json").is_file():
            return None
        admin = con.execute("SELECT id FROM users WHERE role='administrator' ORDER BY created_at LIMIT 1").fetchone()
        return admin["id"] if admin else None


def set_project_owner(project_id: str, user_id: str):
    if not SAFE_ID.fullmatch(project_id):
        raise ValueError("Invalid project identifier")
    with connect() as con:
        con.execute(
            "INSERT INTO project_owners(project_id,user_id) VALUES (?,?) "
            "ON CONFLICT(project_id) DO NOTHING",
            (project_id, user_id),
        )


def can_access_project(project_id: str):
    user = current_user()
    owner = project_owner(project_id)
    return bool(user and owner and (user["role"] == "administrator" or owner == user["id"]))


def project_for_simulation(simulation_id: str):
    if not isinstance(simulation_id, str) or not SAFE_ID.fullmatch(simulation_id):
        return None
    from .services.simulation_manager import SimulationManager
    sim = SimulationManager().get_simulation(simulation_id)
    return sim.project_id if sim else None


def project_for_graph(graph_id: str):
    if not graph_id or not isinstance(graph_id, str) or len(graph_id) > 160:
        return None
    from .models.project import ProjectManager
    for project in ProjectManager.find_projects_by_graph_id(graph_id):
        if can_access_project(project.project_id):
            return project.project_id
    return None


def project_for_report(report_id: str):
    if not isinstance(report_id, str) or not SAFE_ID.fullmatch(report_id):
        return None
    from .services.report_agent import ReportManager
    report = ReportManager.get_report(report_id)
    if report:
        return project_for_simulation(report.simulation_id)
    # Progress and logs may exist before the report's meta.json is written.
    from .models.task import TaskManager
    for task in TaskManager().list_tasks():
        metadata = getattr(task, "metadata", None) or {}
        if metadata.get("report_id") == report_id:
            return project_for_simulation(metadata.get("simulation_id"))
    return None


def project_for_task(task_id: str):
    from .models.task import TaskManager
    if not isinstance(task_id, str) or not SAFE_ID.fullmatch(task_id):
        return None
    task = TaskManager().get_task(task_id)
    if task is None:
        return None
    meta = getattr(task, "metadata", None) or {}
    if meta.get("project_id"):
        return meta["project_id"]
    if meta.get("simulation_id"):
        return project_for_simulation(meta["simulation_id"])
    return None


def resource_authorized(kind: str, ident: str) -> bool:
    if kind == "project":
        return can_access_project(ident)
    if kind == "simulation":
        project_id = project_for_simulation(ident)
        return bool(project_id and can_access_project(project_id))
    if kind == "graph":
        return project_for_graph(ident) is not None
    if kind == "report":
        project_id = project_for_report(ident)
        return bool(project_id and can_access_project(project_id))
    if kind == "task":
        project_id = project_for_task(ident)
        return bool(project_id and can_access_project(project_id))
    return False


def install_auth(app):
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=not app.config.get("TESTING", False)
        and not app.config.get("DEBUG", False),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    )
    initialize_accounts()
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    @app.before_request
    def authorize():
        if not request.path.startswith("/api/"):
            return None
        if request.path == "/api/auth/login" and request.method == "POST":
            return None
        user = get_user(session.get("tenondera_uid"))
        if not user or not user["active"]:
            return jsonify({"success": False, "error": "Iniciá sesión para continuar."}), 401
        # Password resets invalidate every previously issued session cookie.
        import hashlib
        with connect() as con:
            record = con.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
        credential_tag = hashlib.sha256(record["password_hash"].encode()).hexdigest() if record else ""
        if not hmac.compare_digest(session.get("tenondera_credential_tag", ""), credential_tag):
            session.clear()
            return jsonify({"success": False, "error": "Tu sesión fue revocada. Iniciá sesión nuevamente."}), 401
        g.tenondera_user = user
        if user["must_change_password"] and request.path not in (
            "/api/auth/me", "/api/auth/password", "/api/auth/logout"
        ):
            return jsonify({"success": False, "error": "Actualizá tu contraseña antes de continuar."}), 403
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            token = request.headers.get("X-CSRF-Token", "")
            if not token or not hmac.compare_digest(token, session.get("tenondera_csrf", "")):
                return jsonify({"success": False, "error": "Sesión inválida. Actualizá la página."}), 403
        if request.path.startswith("/api/auth/"):
            return None

        # Backend, not UI, enforces tenant isolation. Unknown object routes
        # cannot silently become cross-user access paths.
        if is_admin():
            return None
        path = request.path.removeprefix("/api/")
        sections = path.split("/")
        refs = []
        if path.startswith("graph/project/") and len(sections) > 2 and sections[2] not in ("list",):
            refs.append(("project", sections[2]))
        elif path.startswith("graph/task/") and len(sections) > 2:
            refs.append(("task", sections[2]))
        elif path.startswith("graph/data/") or path.startswith("graph/delete/"):
            refs.append(("graph", sections[2]))
        elif path.startswith("simulation/entities/") and len(sections) > 2:
            refs.append(("graph", sections[2]))
        elif path.startswith("simulation/sim_"):
            refs.append(("simulation", sections[1]))
        elif path.startswith("report/diagnostic/") or path.startswith("report/by-simulation/") or path.startswith("report/check/"):
            refs.append(("simulation", sections[2]))
        elif path.startswith("report/report_") and len(sections) > 1:
            refs.append(("report", sections[1]))
        # Inspect JSON/form/query for all object identifiers, including
        # nested arrays used by batch interview and graph operations.
        values = dict(request.args)
        if request.is_json:
            body = request.get_json(silent=True)
        else:
            body = request.form.to_dict()
        def walk(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    kind = {"project_id":"project","simulation_id":"simulation",
                            "graph_id":"graph","report_id":"report","task_id":"task"}.get(key)
                    if kind and isinstance(value, str):
                        refs.append((kind, value))
                    if isinstance(value, (dict, list)):
                        walk(value)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)
        walk(values)
        walk(body)
        if any(not resource_authorized(kind, ident) for kind, ident in refs):
            return jsonify({"success": False, "error": "Recurso no disponible para tu usuario."}), 404
        allowed_without_object = {
            "graph/ontology/generate","graph/project/list","simulation/list",
            "simulation/history","report/list","capacity/status",
        }
        if not refs and path not in allowed_without_object:
            # Tasks overview and script internals are administrator-only.
            return jsonify({"success": False, "error": "Acceso restringido."}), 403

    @app.after_request
    def filter_private_lists(response):
        if not request.path.startswith("/api/") or not response.is_json:
            return response
        if not current_user():
            return response
        path = request.path.removeprefix("/api/")
        if path not in ("graph/project/list", "simulation/list", "simulation/history", "report/list"):
            return response
        obj = response.get_json(silent=True)
        if not isinstance(obj, dict) or not isinstance(obj.get("data"), list):
            return response
        if is_admin():
            # Admin overview is the only route exposing owners to other users.
            for item in obj["data"]:
                if isinstance(item, dict) and item.get("project_id"):
                    item["owner_id"] = project_owner(item["project_id"])
            response.set_data(current_app.json.dumps(obj))
            return response
        def allowed(row):
            if not isinstance(row, dict):
                return False
            if row.get("project_id") and can_access_project(row["project_id"]):
                return True
            if row.get("simulation_id") and resource_authorized("simulation", row["simulation_id"]):
                return True
            if row.get("report_id") and resource_authorized("report", row["report_id"]):
                return True
            return False
        obj["data"] = [row for row in obj["data"] if allowed(row)]
        obj["count"] = len(obj["data"])
        response.set_data(current_app.json.dumps(obj))
        response.headers["Content-Length"] = str(len(response.get_data()))
        return response


@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip().lower()
    password = body.get("password")
    if not isinstance(password, str) or len(password) > 2048 or len(username) > 96:
        return jsonify({"success": False, "error": "Credenciales inválidas."}), 401
    import hashlib
    host = (request.remote_addr or "unknown")[:100]
    ip_key = hashlib.sha256(host.encode()).hexdigest()
    now = int(time.time())
    with connect() as con:
        attempt = con.execute(
            "SELECT count,window_start FROM failed_logins WHERE ip_hash=?",
            (ip_key,),
        ).fetchone()
        if attempt and now - attempt["window_start"] < 900 and attempt["count"] >= 8:
            return jsonify({"success": False, "error": "Demasiados intentos. Probá más tarde."}), 429
        row = con.execute(
            "SELECT * FROM users WHERE username=? COLLATE NOCASE", (username,)
        ).fetchone()
        ok = bool(row and row["active"] and check_password_hash(row["password_hash"], password))
        if not ok:
            count = (attempt["count"] + 1) if attempt and now - attempt["window_start"] < 900 else 1
            start = attempt["window_start"] if attempt and now - attempt["window_start"] < 900 else now
            con.execute(
                "INSERT INTO failed_logins VALUES(?,?,?) ON CONFLICT(ip_hash) DO UPDATE "
                "SET count=excluded.count,window_start=excluded.window_start",
                (ip_key, count, start),
            )
            return jsonify({"success": False, "error": "Credenciales inválidas."}), 401
        con.execute("DELETE FROM failed_logins WHERE ip_hash=?", (ip_key,))
    session.clear()
    session.permanent = True
    session["tenondera_uid"] = row["id"]
    session["tenondera_credential_tag"] = hashlib.sha256(row["password_hash"].encode()).hexdigest()
    session["tenondera_csrf"] = secrets.token_urlsafe(32)
    user = get_user(row["id"])
    return jsonify({"success": True, "data": {"user": public_user(user), "csrf": session["tenondera_csrf"]}})


@auth_bp.get("/me")
def me():
    return jsonify({"success": True, "data": {
        "user": public_user(current_user()),
        "csrf": session["tenondera_csrf"],
    }})


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})


@auth_bp.post("/password")
def change_password():
    data = request.get_json(silent=True) or {}
    old, new = data.get("current_password"), data.get("new_password")
    if not isinstance(old, str) or not isinstance(new, str) or len(new) < 12 or len(new) > 200:
        return jsonify({"success": False, "error": "La contraseña nueva debe tener entre 12 y 200 caracteres."}), 400
    with connect() as con:
        row = con.execute("SELECT password_hash FROM users WHERE id=?", (current_user()["id"],)).fetchone()
        if not check_password_hash(row["password_hash"], old):
            return jsonify({"success": False, "error": "Contraseña actual incorrecta."}), 403
        con.execute("UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?",
                    (generate_password_hash(new), current_user()["id"]))
    session.clear()
    return jsonify({"success": True, "message": "Contraseña actualizada. Volvé a iniciar sesión."})


def admin_only():
    if not is_admin():
        return jsonify({"success": False, "error": "Solo el administrador puede gestionar usuarios."}), 403
    return None


@auth_bp.get("/users")
def list_users():
    denied = admin_only()
    if denied: return denied
    with connect() as con:
        rows = con.execute(
            "SELECT id,username,name,role,active,must_change_password,created_at FROM users ORDER BY created_at"
        ).fetchall()
    users = [dict(x) for x in rows]
    from .services.simulation_manager import SimulationManager
    counts = {}
    for sim in SimulationManager().list_simulations():
        owner = project_owner(sim.project_id)
        if owner:
            counts[owner] = counts.get(owner, 0) + 1
    for user in users:
        user["simulation_count"] = counts.get(user["id"], 0)
    return jsonify({"success": True, "data": users})


@auth_bp.post("/users")
def create_user():
    denied = admin_only()
    if denied: return denied
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip().lower()
    name = str(body.get("name", "")).strip()[:120]
    password = body.get("password", "")
    role = body.get("role", "analyst")
    if (not USERNAME.fullmatch(username) or not name or role not in ("analyst", "researcher")
            or not isinstance(password, str) or not 12 <= len(password) <= 200):
        return jsonify({"success": False, "error": "Usuario, nombre, rol o contraseña inválidos (mínimo 12 caracteres)."}), 400
    user_id = uuid.uuid4().hex
    try:
        with connect() as con:
            con.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
                (user_id, username, name, generate_password_hash(password), role, 1, 1, int(time.time())))
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Ese usuario ya existe."}), 409
    return jsonify({"success": True, "data": get_user(user_id)}), 201


@auth_bp.patch("/users/<user_id>")
def update_user(user_id):
    denied = admin_only()
    if denied: return denied
    body = request.get_json(silent=True) or {}
    if user_id == current_user()["id"]:
        return jsonify({"success": False, "error": "No podés modificar tu propio rol o estado."}), 409
    changes = {}
    if "role" in body:
        if body["role"] not in ROLES or body["role"] == "administrator":
            return jsonify({"success": False, "error": "Usá un rol válido: analista o investigador."}), 400
        changes["role"] = body["role"]
    if "active" in body:
        if type(body["active"]) is not bool:
            return jsonify({"success": False, "error": "active debe ser booleano."}), 400
        changes["active"] = int(body["active"])
    if "password" in body:
        if not isinstance(body["password"], str) or not 12 <= len(body["password"]) <= 200:
            return jsonify({"success": False, "error": "La contraseña debe tener entre 12 y 200 caracteres."}), 400
        changes["password_hash"] = generate_password_hash(body["password"])
        changes["must_change_password"] = 1
    if not changes:
        return jsonify({"success": False, "error": "No se especificaron cambios."}), 400
    with connect() as con:
        row = con.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return jsonify({"success": False, "error": "Usuario no encontrado."}), 404
        if row["role"] == "administrator":
            return jsonify({"success": False, "error": "No se permite modificar otra cuenta administradora."}), 403
        con.execute("UPDATE users SET "+",".join(k+"=?" for k in changes)+" WHERE id=?",
                    (*changes.values(), user_id))
    return jsonify({"success": True, "data": get_user(user_id)})
