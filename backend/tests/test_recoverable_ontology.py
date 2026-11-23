"""Regression for durable ontology queue, idempotency and interrupted jobs."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Config
from app.models.project import ProjectManager, ProjectStatus
from app.services import ontology_queue as jobs


class RecoverableOntologyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_upload=Config.UPLOAD_FOLDER
        self.old_projects=ProjectManager.PROJECTS_DIR
        self.old_worker=os.environ.get("TENONDERA_ONTOLOGY_WORKER")
        Config.UPLOAD_FOLDER=self.temp.name
        ProjectManager.PROJECTS_DIR=str(Path(self.temp.name)/"projects")
        os.environ["TENONDERA_ONTOLOGY_WORKER"]="false"
        self.project=ProjectManager.create_project("Ensayo recuperable")
        self.project.simulation_requirement="Evaluar impacto de seguridad"
        ProjectManager.save_project(self.project)
        folder=Path(ProjectManager._get_project_files_dir(self.project.project_id))
        folder.mkdir(parents=True,exist_ok=True)
        (folder/"test.txt").write_text("Evidencia de ensayo",encoding="utf-8")

    def tearDown(self):
        Config.UPLOAD_FOLDER=self.old_upload
        ProjectManager.PROJECTS_DIR=self.old_projects
        if self.old_worker is None:os.environ.pop("TENONDERA_ONTOLOGY_WORKER",None)
        else:os.environ["TENONDERA_ONTOLOGY_WORKER"]=self.old_worker
        self.temp.cleanup()

    def test_queued_job_returns_stable_id_after_refresh(self):
        jobs.submit(self.project.project_id,"owner1","a"*32)
        job=jobs.status(self.project.project_id)
        self.assertEqual(job["state"],"queued")
        self.assertEqual(jobs.find_submission("owner1","a"*32)["project_id"],
                         self.project.project_id)
        self.assertIsNone(jobs.find_submission("owner2","a"*32))
        self.assertEqual(jobs.status(self.project.project_id)["phase"],"Documentos recibidos")

    def test_interrupted_worker_lease_reclaims_without_new_project(self):
        jobs.submit(self.project.project_id,"owner1","b"*32)
        first=jobs.claim()
        self.assertEqual(first[0],self.project.project_id)
        self.assertIsNone(jobs.claim())
        with jobs.connect() as db:
            db.execute("UPDATE ontology_jobs SET lease_until=0 WHERE project_id=?",
                       (self.project.project_id,))
        second=jobs.claim()
        self.assertEqual(second[0],self.project.project_id)
        self.assertNotEqual(first[1],second[1])
        jobs.finish(*first,success=True)
        self.assertEqual(jobs.status(self.project.project_id)["state"],"running")
        jobs.finish(*second,success=True)
        self.assertEqual(jobs.status(self.project.project_id)["state"],"completed")

    def test_failed_job_can_retry_with_original_documents(self):
        jobs.submit(self.project.project_id,"owner1","c"*32)
        project_id,owner=jobs.claim()
        jobs.finish(project_id,owner,success=False,error="Error recuperable")
        self.assertEqual(jobs.status(project_id)["state"],"failed")
        resumed=jobs.retry(project_id)
        self.assertEqual(resumed["state"],"queued")
        self.assertEqual(len(ProjectManager.get_project_files(project_id)),1)
        self.assertEqual(ProjectManager.get_project(project_id).status,ProjectStatus.CREATED)
        self.assertIsNone(jobs.retry(project_id))

    def test_project_is_not_cleared_when_worker_reports_failure(self):
        jobs.submit(self.project.project_id,"owner1","d"*32)
        old=jobs.claim()
        jobs.finish(*old,success=False,error="Verificá el modelo")
        self.assertTrue(Path(ProjectManager._get_project_files_dir(self.project.project_id),"test.txt").exists())
        self.assertEqual(jobs.status(self.project.project_id)["error"],"Verificá el modelo")


if __name__=="__main__":
    unittest.main()
