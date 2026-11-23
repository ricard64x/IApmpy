"""Durable, independently polled ontology generation.

Uploading returns a project id before any LLM call. SQLite leases let a single
Gunicorn worker recover tasks after a restart without replaying completed work.
All state lives on the existing encrypted Fly volume; no private data sent to
external services except the configured ontology provider as before.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from ..config import Config

POLL_SECONDS=2
LEASE_SECONDS=100
MAX_ATTEMPTS=2
_queue_lock=threading.Lock()
_worker_started=False
_PROJECT_PATTERN=__import__("re").compile(r"^proj_[a-f0-9]{12}$")

def db_path():
    return Path(Config.UPLOAD_FOLDER)/"ontology_jobs"/"jobs.sqlite3"

@contextmanager
def connect():
    path=db_path()
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    connection=sqlite3.connect(path,timeout=10)
    connection.row_factory=sqlite3.Row
    connection.execute("PRAGMA busy_timeout=10000")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""CREATE TABLE IF NOT EXISTS ontology_jobs(
      project_id TEXT PRIMARY KEY,
      owner_id TEXT NOT NULL,
      submission_key TEXT NOT NULL,
      state TEXT NOT NULL CHECK(state IN ('queued','running','completed','failed')),
      phase TEXT NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 0,
      lease_until INTEGER NOT NULL DEFAULT 0,
      lease_owner TEXT,
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      error TEXT,
      UNIQUE(owner_id,submission_key)
    )""")
    connection.execute("CREATE INDEX IF NOT EXISTS ontology_pending ON ontology_jobs(state,lease_until)")
    os.chmod(path,0o600)
    try:
        with connection:
            yield connection
    finally:
        connection.close()

def find_submission(owner_id,key):
    with connect() as db:
        row=db.execute("SELECT project_id,state FROM ontology_jobs WHERE owner_id=? AND submission_key=?",
                       (owner_id,key)).fetchone()
        return dict(row) if row else None

def submit(project_id,owner_id,key):
    now=int(time.time())
    with connect() as db:
        db.execute("""INSERT INTO ontology_jobs
          (project_id,owner_id,submission_key,state,phase,created_at,updated_at)
          VALUES(?,?,?,'queued','Documentos recibidos',?,?)""",
          (project_id,owner_id,key,now,now))
    start_worker()

def status(project_id):
    if not _PROJECT_PATTERN.fullmatch(str(project_id)):
        return None
    with connect() as db:
        row=db.execute("""SELECT project_id,state,phase,attempts,created_at,updated_at,error
                          FROM ontology_jobs WHERE project_id=?""",(project_id,)).fetchone()
        return dict(row) if row else None

def claim():
    now=int(time.time())
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("""SELECT project_id,attempts FROM ontology_jobs
            WHERE state='queued' OR (state='running' AND lease_until < ?)
            ORDER BY created_at LIMIT 1""",(now,)).fetchone()
        if not row:
            db.commit()
            return None
        if row["attempts"]>=MAX_ATTEMPTS:
            db.execute("""UPDATE ontology_jobs SET state='failed',
              error='El procesamiento se interrumpió repetidamente. Podés reintentar desde el proyecto.',
              phase='Revisión requerida', updated_at=? WHERE project_id=?""",(now,row["project_id"]))
            db.commit()
            return None
        owner=uuid.uuid4().hex
        db.execute("""UPDATE ontology_jobs SET state='running',phase='Analizando documentos',
          attempts=attempts+1,lease_until=?,lease_owner=?,updated_at=? WHERE project_id=?""",
          (now+LEASE_SECONDS,owner,now,row["project_id"]))
        db.commit()
        return row["project_id"],owner

def heartbeat(project_id,owner,stopped):
    while not stopped.wait(LEASE_SECONDS/3):
        with connect() as db:
            changed=db.execute("""UPDATE ontology_jobs SET lease_until=?,updated_at=?
              WHERE project_id=? AND state='running' AND lease_owner=?""",
              (int(time.time())+LEASE_SECONDS,int(time.time()),project_id,owner))
            if changed.rowcount!=1:
                return

def finish(project_id,owner,success,error=None):
    state="completed" if success else "failed"
    with connect() as db:
        db.execute("""UPDATE ontology_jobs SET state=?,phase=?,error=?,lease_until=0,
          lease_owner=NULL,updated_at=? WHERE project_id=? AND lease_owner=?""",
          (state,"Ontología generada" if success else "Revisión requerida",
           error,int(time.time()),project_id,owner))

def execute(project_id,owner):
    from ..models.project import ProjectManager,ProjectStatus
    from ..utils.file_parser import FileParser
    from .text_processor import TextProcessor
    from .ontology_generator import OntologyGenerator
    from ..utils.logger import get_logger
    log=get_logger("tenondera.ontology_queue")
    project=ProjectManager.get_project(project_id)
    if project is None:
        finish(project_id,owner,False,"Proyecto no encontrado")
        return
    if project.ontology:
        # The worker may have died after persisting output but before finishing.
        finish(project_id,owner,True)
        return
    stopped=threading.Event()
    pulse=threading.Thread(target=heartbeat,args=(project_id,owner,stopped),
                           daemon=True,name="ontology-lease-heartbeat")
    pulse.start()
    try:
        source_files=ProjectManager.get_project_files(project_id)
        if not source_files:
            raise ValueError("No se encontraron documentos guardados")
        texts=[]
        combined=[]
        for source in source_files:
            text=TextProcessor.preprocess_text(FileParser.extract_text(source))
            if text.strip():
                texts.append(text)
                combined.append(f"\n\n=== {Path(source).name} ===\n{text}")
        if not texts:
            raise ValueError("Los documentos no contienen texto utilizable")
        joined="".join(combined)
        project.total_text_length=len(joined)
        ProjectManager.save_extracted_text(project_id,joined)
        with connect() as db:
            db.execute("UPDATE ontology_jobs SET phase='Generando ontología con IA',updated_at=? WHERE project_id=? AND lease_owner=?",
                       (int(time.time()),project_id,owner))
        ontology=OntologyGenerator().generate(document_texts=texts,
                       simulation_requirement=project.simulation_requirement,
                       additional_context=None)
        project.ontology={"entity_types":ontology.get("entity_types",[]),
                          "edge_types":ontology.get("edge_types",[])}
        project.analysis_summary=ontology.get("analysis_summary","")
        project.status=ProjectStatus.ONTOLOGY_GENERATED
        project.error=None
        ProjectManager.save_project(project)
        finish(project_id,owner,True)
    except Exception as error:
        # Never return provider exception bodies: they can include confidential prompts.
        log.error("Ontology job failed project=%s type=%s",project_id,type(error).__name__)
        project.status=ProjectStatus.FAILED
        project.error="No se pudo generar la ontología. Tus documentos siguen guardados."
        try:ProjectManager.save_project(project)
        except (OSError,ValueError):log.exception("Failed to persist project status")
        finish(project_id,owner,False,project.error)
    finally:
        stopped.set()
        pulse.join(timeout=2)


def retry(project_id):
    """Queue a failed job again without replacing its uploaded evidence."""
    from ..models.project import ProjectManager,ProjectStatus
    project=ProjectManager.get_project(project_id)
    if not project or project.ontology or not ProjectManager.get_project_files(project_id):
        return None
    now=int(time.time())
    with connect() as db:
        changed=db.execute("""UPDATE ontology_jobs SET state='queued',
          attempts=0,lease_until=0,lease_owner=NULL,phase='Reintento solicitado',
          error=NULL,updated_at=? WHERE project_id=? AND state='failed'""",
          (now,project_id))
        if changed.rowcount!=1:
            return None
    project.status=ProjectStatus.CREATED
    project.error=None
    ProjectManager.save_project(project)
    start_worker()
    return status(project_id)

def worker_loop():
    while True:
        try:
            job=claim()
            if job:execute(*job)
            else:time.sleep(POLL_SECONDS)
        except Exception:
            # Keep worker alive after a transient DB/FS issue, without logging private files.
            from ..utils.logger import get_logger
            get_logger("tenondera.ontology_queue").exception("Ontology worker cycle failed")
            time.sleep(5)

def start_worker():
    global _worker_started
    if os.environ.get("TENONDERA_ONTOLOGY_WORKER","true").lower()!="true":
        return
    with _queue_lock:
        if _worker_started:return
        _worker_started=True
        threading.Thread(target=worker_loop,name="ontology-durable-worker",daemon=True).start()
