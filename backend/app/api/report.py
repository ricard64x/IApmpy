"""
Report API路由
提供模拟报告生成、获取、对话等接口
"""

import os
import traceback
import threading
from flask import request, jsonify, send_file

from . import report_bp
from ..config import Config
from ..services.report_agent import ReportAgent, ReportManager, ReportStatus
from ..services.simulation_manager import SimulationManager
from ..services.simulation_runner import SimulationRunner, RunnerStatus
from ..services.zep_graph_memory_updater import ZepGraphMemoryManager
from ..models.project import ProjectManager, ProjectStatus
from ..models.task import TaskManager, TaskStatus
from ..utils.logger import get_logger
from ..utils.locale import t, get_locale, set_locale
from ..utils.zep_lifecycle import (
    graph_lifecycle_lock,
    register_graph_reader,
    unregister_graph_reader,
)

logger = get_logger('mirofish.api.report')


def _synthetic_gpt_evidence(simulation_id: str) -> str:
    """Read only persisted action events, never profile/prompt secrets.

    Explicitly flag methodological limits; the normal report agent primarily
    queries the original knowledge graph, so synthetic actions MUST be given
    as separate evidence rather than implicitly treating the source graph
    as a record of simulated deliberations.
    """
    import json
    import re
    from pathlib import Path
    if not re.fullmatch(r"sim_[A-Za-z0-9_-]{1,90}", simulation_id):
        raise ValueError("Identificador inválido.")
    directory = Path(Config.UPLOAD_FOLDER) / "simulations" / simulation_id
    evidence = []
    for platform, name in (("twitter", "Plaza"), ("reddit", "Comunidad")):
        path = directory / platform / "actions.jsonl"
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if len(evidence) >= 120:
                break
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("source_mode") not in ("sintetico_gpt_liviano", "sintetico_gpt_dialogo"):
                continue
            if event.get("action_type") not in ("CREATE_POST", "CREATE_COMMENT"):
                continue
            args = event.get("action_args")
            if not isinstance(args, dict):
                continue
            message = args.get("content", "")
            if not isinstance(message, str) or not message.strip():
                continue
            evidence.append(
                f"- Ronda {int(event.get('round') or 0)}, {name}, "
                f"participante ficticio {event.get('agent_id')}" +
                (f" responde explícitamente a {args.get('target_agent_id')}" if
                 event.get("action_type") == "CREATE_COMMENT" and
                 args.get("target_agent_id") is not None else " publica") +
                f": {message[:320]}"
            )
    if not evidence:
        raise ValueError("No hay acciones sintéticas válidas; no corresponde generar informe.")
    return (
        "\n\n## DATOS SINTÉTICOS DE ESTA EJECUCIÓN\n"
        "Estas intervenciones fueron generadas por un modelo GPT para un "
        "escenario hipotético. NO son encuestas, hechos reales, evidencia "
        "forense ni una corrida de OASIS completa. No atribuyas porcentajes "
        "de opinión pública real ni inferencias estadísticas válidas. "
        "Fundamentá cualquier conclusión solo en los textos enumerados "
        "y diferenciá estrictamente de la información documental original.\n"
        + "\n".join(evidence)
    )




@report_bp.route('/diagnostic/<simulation_id>', methods=['GET'])
def download_failed_simulation_diagnostic(simulation_id: str):
    """Download a factual technical summary, not a simulated opinion report."""
    import io
    import re
    from datetime import datetime, timezone

    # Validate before passing the ID to managers that construct filesystem paths.
    if not re.fullmatch(r'sim_[a-zA-Z0-9_-]{1,64}', simulation_id):
        return jsonify({"success": False, "error": "Invalid simulation ID"}), 400

    simulation = SimulationManager().get_simulation(simulation_id)
    if simulation is None:
        return jsonify({"success": False, "error": t('api.simulationNotFound', id=simulation_id)}), 404

    run = SimulationRunner.get_run_state(simulation_id)
    if run is None or run.runner_status != RunnerStatus.FAILED:
        return jsonify({
            "success": False,
            "error": "A failed simulation is required to download a diagnostic report."
        }), 409

    # Only expose structured, non-sensitive metrics. Never copy logs, generated
    # personas, prompt bodies, or raw exception messages into this download.
    reason = str(run.error or "")
    sigkill = "-9" in reason or "sigkill" in reason.lower()
    error_label = (
        "Proceso terminado por SIGKILL (-9). Revisar contadores OOM y memoria."
        if sigkill else
        "Error de ejecución. Revisar los registros protegidos del servidor."
    )
    def field(value):
        return str(value) if value is not None else "No disponible"

    md = chr(10).join([
        "# Informe técnico de ejecución fallida",
        "",
        "**Advertencia:** Este archivo NO es un informe de resultados ni una"
        " predicción de opinión pública. La simulación no finalizó correctamente.",
        "",
        f"- Simulación: `{simulation_id}`",
        f"- Proyecto: `{simulation.project_id}`",
        "- Estado: FALLIDA",
        f"- Inicio: {field(run.started_at)}",
        f"- Finalización: {field(run.completed_at)}",
        f"- Rondas registradas: {field(run.current_round)} de {field(run.total_rounds)}",
        f"- Rondas Twitter: {field(run.twitter_current_round)}",
        f"- Rondas Reddit: {field(run.reddit_current_round)}",
        f"- Acciones Twitter registradas: {field(run.twitter_actions_count)}",
        f"- Acciones Reddit registradas: {field(run.reddit_actions_count)}",
        f"- Total de acciones registradas: {field(run.total_actions_count)}",
        f"- Tipo de incidente: {error_label}",
        "",
        "## Interpretación",
        "No se deben inferir tendencias, porcentajes de opinión ni conclusiones"
        " demográficas de una ejecución fallida.",
        "Las acciones iniciales, si existen, no constituyen resultados de"
        " interacción ni evidencia de opinión pública.",
        "",
        "## Próximos pasos",
        "1. Conservar la evidencia y los respaldos existentes.",
        "2. Revisar uso de memoria, límites de recursos y registros del motor OASIS.",
        "3. Corregir la causa de la falla y ejecutar una nueva simulación controlada.",
        "4. Generar el informe de opinión pública únicamente cuando una ejecución"
        " haya terminado correctamente o se haya detenido de forma válida.",
        "",
        f"_Generado: {datetime.now(timezone.utc).isoformat()}_",
        "",
    ])
    return send_file(
        io.BytesIO(md.encode("utf-8")),
        mimetype="text/markdown; charset=utf-8",
        as_attachment=True,
        download_name=f"diagnostico_{simulation_id}.md",
    )


# ============== 报告生成接口 ==============

@report_bp.route('/generate', methods=['POST'])
def generate_report():
    """
    生成模拟分析报告（异步任务）
    
    这是一个耗时操作，接口会立即返回task_id，
    使用 GET /api/report/generate/status 查询进度
    
    请求（JSON）：
        {
            "simulation_id": "sim_xxxx",    // 必填，模拟ID
            "force_regenerate": false        // 可选，强制重新生成
        }
    
    返回：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",
                "status": "generating",
                "message": "报告生成任务已启动"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        force_regenerate = data.get('force_regenerate', False)
        if not isinstance(force_regenerate, bool):
            return jsonify({
                "success": False,
                "error": "force_regenerate must be a JSON boolean",
            }), 400
        
        # 获取模拟信息
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404

        run_state = SimulationRunner.get_run_state(simulation_id)
        updater = ZepGraphMemoryManager.get_updater(simulation_id)
        active_statuses = {
            RunnerStatus.STARTING,
            RunnerStatus.RUNNING,
            RunnerStatus.PAUSED,
            RunnerStatus.STOPPING,
        }
        if updater is not None or (
            run_state is not None and run_state.runner_status in active_statuses
        ):
            return jsonify({
                "success": False,
                "error": (
                    "Simulation or Zep graph ingestion is still active; "
                    "wait for a terminal run status before generating a report"
                ),
                "ingestion_pending": updater is not None,
            }), 409
        successful_terminal_statuses = {
            RunnerStatus.COMPLETED,
            RunnerStatus.STOPPED,
        }
        if (
            run_state is None
            or run_state.runner_status not in successful_terminal_statuses
        ):
            return jsonify({
                "success": False,
                "error": t('api.reportRequiresCompletedSimulation'),
                "diagnostic_available": bool(run_state and run_state.runner_status == RunnerStatus.FAILED),
            }), 409

        # 获取项目信息
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=state.project_id)
            }), 404
        
        if project.status != ProjectStatus.GRAPH_COMPLETED:
            return jsonify({
                "success": False,
                "error": "The project graph must be completely built before reporting",
            }), 409

        graph_id = project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.missingGraphIdEnsure')
            }), 400
        if state.graph_id and state.graph_id != graph_id:
            return jsonify({
                "success": False,
                "error": (
                    "The simulation references an older graph; prepare it "
                    "again before generating a report"
                ),
            }), 409
        
        simulation_requirement = project.simulation_requirement
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": t('api.missingSimRequirement')
            }), 400
        
        # 提前生成 report_id，以便立即返回给前端
        import uuid
        report_id = f"report_{uuid.uuid4().hex[:12]}"
        
        # Register the background report as a graph reader under the same lock
        # used by graph deletion and updater startup. A lock itself cannot be
        # acquired in this request thread and released by the worker, so the
        # durable reader registration is the cross-thread lease.
        with graph_lifecycle_lock(graph_id):
            refreshed_state = manager.get_simulation(simulation_id)
            refreshed_project = (
                ProjectManager.get_project(refreshed_state.project_id)
                if refreshed_state
                else None
            )
            refreshed_run_state = SimulationRunner.get_run_state(simulation_id)
            refreshed_updater = ZepGraphMemoryManager.get_updater(simulation_id)
            if (
                refreshed_state is None
                or refreshed_project is None
                or refreshed_project.graph_id != graph_id
                or refreshed_project.status != ProjectStatus.GRAPH_COMPLETED
                or (
                    refreshed_state.graph_id
                    and refreshed_state.graph_id != graph_id
                )
            ):
                return jsonify({
                    "success": False,
                    "error": "The project graph changed while reporting was starting",
                }), 409
            if refreshed_updater is not None or (
                refreshed_run_state is not None
                and refreshed_run_state.runner_status in active_statuses
            ):
                return jsonify({
                    "success": False,
                    "error": (
                        "Simulation or Zep graph ingestion became active; "
                        "retry after it reaches a terminal state"
                    ),
                    "ingestion_pending": refreshed_updater is not None,
                }), 409
            if (
                refreshed_run_state is None
                or refreshed_run_state.runner_status
                not in successful_terminal_statuses
            ):
                return jsonify({
                    "success": False,
                    "error": t('api.reportRequiresCompletedSimulation'),
                    "diagnostic_available": bool(refreshed_run_state and refreshed_run_state.runner_status == RunnerStatus.FAILED),
                }), 409

            # Cached-report reuse is now part of the same atomic barrier, so a
            # concurrent rerun cannot make the returned report stale between
            # the status check and response.
            if not force_regenerate:
                existing_report = ReportManager.get_report_by_simulation(
                    simulation_id
                )
                if (
                    existing_report
                    and existing_report.status == ReportStatus.COMPLETED
                ):
                    return jsonify({
                        "success": True,
                        "data": {
                            "simulation_id": simulation_id,
                            "report_id": existing_report.report_id,
                            "status": "completed",
                            "message": t('api.reportAlreadyExists'),
                            "already_generated": True
                        }
                    })

            task_manager = TaskManager()
            task_id = task_manager.create_task(
                task_type="report_generate",
                metadata={
                    "simulation_id": simulation_id,
                    "graph_id": graph_id,
                    "report_id": report_id
                }
            )
            current_locale = get_locale()
            register_graph_reader(graph_id, report_id)

            def run_generate():
                set_locale(current_locale)
                try:
                    task_manager.update_task(
                        task_id,
                        status=TaskStatus.PROCESSING,
                        progress=0,
                        message=t('api.initReportAgent')
                    )

                    is_lite = getattr(refreshed_run_state, "engine_mode", "oasis") == "lightweight"
                    report_context = simulation_requirement
                    if is_lite:
                        report_context += _synthetic_gpt_evidence(simulation_id)
                    agent = ReportAgent(
                        graph_id=graph_id,
                        simulation_id=simulation_id,
                        simulation_requirement=report_context
                    )

                    def progress_callback(stage, progress, message):
                        task_manager.update_task(
                            task_id,
                            progress=progress,
                            message=f"[{stage}] {message}"
                        )

                    report = agent.generate_report(
                        progress_callback=progress_callback,
                        report_id=report_id
                    )
                    if report.status == ReportStatus.COMPLETED:
                        from ..services.simulation_metrics import legacy_metrics
                        measured = legacy_metrics(simulation_id,
                            os.path.join(SimulationRunner.RUN_STATE_DIR,simulation_id))
                        quality = measured["interaction_quality"]
                        warnings = []
                        if quality["status"] not in ("acceptable", "good"):
                            warnings.append(
                                "**ADVERTENCIA — CALIDAD DE INTERACCIÓN NO VALIDADA:** "
                                + quality["label"] + ". " +
                                " ".join(quality["issues"]) +
                                " No corresponde tratarlo como un diálogo multiagente válido."
                            )
                        if is_lite:
                            warnings.append(
                                "**NOTA METODOLÓGICA:** Informe de simulación "
                                "SINTÉTICA mediante GPT. No representa personas reales, "
                                "encuestas ni la dinámica social completa de OASIS."
                            )
                        if warnings:
                            report.markdown_content = "\n\n".join(warnings) + "\n\n" + (report.markdown_content or "")
                            markdown_path = ReportManager._get_report_markdown_path(report_id)
                            with open(markdown_path, "w", encoding="utf-8") as handle:
                                handle.write(report.markdown_content)
                    ReportManager.save_report(report)

                    if report.status == ReportStatus.COMPLETED:
                        task_manager.complete_task(
                            task_id,
                            result={
                                "report_id": report.report_id,
                                "simulation_id": simulation_id,
                                "status": "completed"
                            }
                        )
                    else:
                        task_manager.fail_task(
                            task_id,
                            report.error or t('api.reportGenerateFailed')
                        )
                except Exception as e:
                    logger.error(f"报告生成失败: {str(e)}")
                    task_manager.fail_task(task_id, str(e))
                finally:
                    unregister_graph_reader(graph_id, report_id)

            try:
                thread = threading.Thread(target=run_generate, daemon=True)
                thread.start()
            except Exception:
                unregister_graph_reader(graph_id, report_id)
                raise
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "report_id": report_id,
                "task_id": task_id,
                "status": "generating",
                "message": t('api.reportGenerateStarted'),
                "already_generated": False
            }
        })
        
    except Exception as e:
        logger.error(f"启动报告生成任务失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/generate/status', methods=['POST'])
def get_generate_status():
    """
    查询报告生成任务进度
    
    请求（JSON）：
        {
            "task_id": "task_xxxx",         // 可选，generate返回的task_id
            "simulation_id": "sim_xxxx"     // 可选，模拟ID
        }
    
    返回：
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|failed",
                "progress": 45,
                "message": "..."
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        
        # 如果提供了simulation_id，先检查是否已有完成的报告
        if simulation_id:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "progress": 100,
                        "message": t('api.reportGenerated'),
                        "already_completed": True
                    }
                })
        
        if not task_id:
            return jsonify({
                "success": False,
                "error": t('api.requireTaskOrSimId')
            }), 400
        
        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            return jsonify({
                "success": False,
                "error": t('api.taskNotFound', id=task_id)
            }), 404
        
        return jsonify({
            "success": True,
            "data": task.to_dict()
        })
        
    except Exception as e:
        logger.error(f"查询任务状态失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== 报告获取接口 ==============

@report_bp.route('/<report_id>/metrics', methods=['GET'])
def report_simulation_metrics(report_id: str):
    """Structured visualizations derived from this saved report's execution."""
    from ..services.simulation_metrics import legacy_metrics
    report = ReportManager.get_report(report_id)
    if report is None:
        return jsonify({"success":False,"error":"Informe no disponible"}),404
    simulation_id = report.simulation_id
    if SimulationManager().get_simulation(simulation_id) is None:
        return jsonify({"success":False,"error":"Simulación no disponible"}),404
    base = os.path.join(SimulationRunner.RUN_STATE_DIR,simulation_id)
    from ..services.simulation_metrics import followup_metrics
    data=legacy_metrics(simulation_id,base)
    data["followups"]=followup_metrics(
        os.path.join(ReportManager.REPORTS_DIR,report_id,"interacciones.jsonl"),
        simulation_id)
    return jsonify({"success":True,"data":data})


@report_bp.route('/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """
    获取报告详情
    
    返回：
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "simulation_id": "sim_xxxx",
                "status": "completed",
                "outline": {...},
                "markdown_content": "...",
                "created_at": "...",
                "completed_at": "..."
            }
        }
    """
    try:
        report = ReportManager.get_report(report_id)
        
        if not report:
            return jsonify({
                "success": False,
                "error": t('api.reportNotFound', id=report_id)
            }), 404
        
        return jsonify({
            "success": True,
            "data": report.to_dict()
        })
        
    except Exception as e:
        logger.error(f"获取报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/by-simulation/<simulation_id>', methods=['GET'])
def get_report_by_simulation(simulation_id: str):
    """
    根据模拟ID获取报告
    
    返回：
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                ...
            }
        }
    """
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)
        
        if not report:
            return jsonify({
                "success": False,
                "error": t('api.noReportForSim', id=simulation_id),
                "has_report": False
            }), 404
        
        return jsonify({
            "success": True,
            "data": report.to_dict(),
            "has_report": True
        })
        
    except Exception as e:
        logger.error(f"获取报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/list', methods=['GET'])
def list_reports():
    """
    列出所有报告
    
    Query参数：
        simulation_id: 按模拟ID过滤（可选）
        limit: 返回数量限制（默认50）
    
    返回：
        {
            "success": true,
            "data": [...],
            "count": 10
        }
    """
    try:
        simulation_id = request.args.get('simulation_id')
        limit = request.args.get('limit', 50, type=int)
        
        reports = ReportManager.list_reports(
            simulation_id=simulation_id,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in reports],
            "count": len(reports)
        })
        
    except Exception as e:
        logger.error(f"列出报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/download', methods=['GET'])
def download_report(report_id: str):
    """
    下载报告（Markdown格式）
    
    返回Markdown文件
    """
    try:
        report = ReportManager.get_report(report_id)
        
        if not report:
            return jsonify({
                "success": False,
                "error": t('api.reportNotFound', id=report_id)
            }), 404
        
        md_path = ReportManager._get_report_markdown_path(report_id)
        
        if not os.path.exists(md_path):
            # 如果MD文件不存在，生成一个临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(report.markdown_content)
                temp_path = f.name
            
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{report_id}.md"
            )
        
        return send_file(
            md_path,
            as_attachment=True,
            download_name=f"{report_id}.md"
        )
        
    except Exception as e:
        logger.error(f"下载报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>', methods=['DELETE'])
def delete_report(report_id: str):
    """删除报告"""
    try:
        success = ReportManager.delete_report(report_id)
        
        if not success:
            return jsonify({
                "success": False,
                "error": t('api.reportNotFound', id=report_id)
            }), 404
        
        return jsonify({
            "success": True,
            "message": t('api.reportDeleted', id=report_id)
        })
        
    except Exception as e:
        logger.error(f"删除报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Report Agent对话接口 ==============

@report_bp.route('/chat', methods=['POST'])
def chat_with_report_agent():
    """
    与Report Agent对话
    
    Report Agent可以在对话中自主调用检索工具来回答问题
    
    请求（JSON）：
        {
            "simulation_id": "sim_xxxx",        // 必填，模拟ID
            "message": "请解释一下舆情走向",    // 必填，用户消息
            "chat_history": [                   // 可选，对话历史
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }
    
    返回：
        {
            "success": true,
            "data": {
                "response": "Agent回复...",
                "tool_calls": [调用的工具列表],
                "sources": [信息来源]
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        message = data.get('message')
        chat_history = data.get('chat_history', [])
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        if not message:
            return jsonify({
                "success": False,
                "error": t('api.requireMessage')
            }), 400
        
        # 获取模拟和项目信息
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404

        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=state.project_id)
            }), 404
        
        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.missingGraphId')
            }), 400
        
        simulation_requirement = project.simulation_requirement or ""
        
        # 创建Agent并进行对话
        agent = ReportAgent(
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement
        )
        
        result = agent.chat(message=message, chat_history=chat_history)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"对话失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500



# ============== Consultas y encuestas posteriores al informe ==============

@report_bp.route('/interactions', methods=['GET', 'POST'])
def report_interactions():
    """Store and replay private, explicitly synthetic post-simulation interactions."""
    from ..services.report_interactions import (
        BusyInteraction, get_report_context, history_for_report, interact,
    )

    if request.method == 'GET':
        report_id = request.args.get('report_id', '')
        simulation_id = request.args.get('simulation_id', '')
        try:
            if not report_id or not simulation_id:
                raise ValueError("Se requieren el informe y la simulación.")
            records = history_for_report(report_id, simulation_id)
        except ValueError as error:
            return jsonify({"success": False, "error": str(error)}), 400
        return jsonify({"success": True, "data": {"records": records}})

    data = request.get_json(silent=True) or {}
    try:
        result = interact(
            report_id=data.get('report_id'),
            simulation_id=data.get('simulation_id'),
            kind=data.get('kind', ''),
            message=data.get('message', ''),
            target=data.get('target', 'report'),
            agent_id=data.get('agent_id'),
            agent_ids=data.get('agent_ids'),
            platform=data.get('platform'),
            history=data.get('chat_history'),
        )
        return jsonify({"success": True, "data": result})
    except BusyInteraction as error:
        return jsonify({"success": False, "error": str(error)}), 429
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        logger.exception("Error al procesar interacción guardada: %s", type(error).__name__)
        return jsonify({
            "success": False,
            "error": "No se pudo generar la respuesta. Verificá la conexión del modelo y volvé a intentarlo.",
        }), 502


@report_bp.route('/<report_id>/export', methods=['GET'])
def export_persisted_report(report_id: str):
    """Download an existing report without spawning a model or a simulation."""
    import html
    import io
    import json
    import re
    try:
        if not re.fullmatch(r"report_[A-Za-z0-9_-]{1,64}", report_id):
            return jsonify({"success": False, "error": "Informe inválido."}), 400
        report = ReportManager.get_report(report_id)
        if not report:
            return jsonify({"success": False, "error": "Informe no encontrado."}), 404
        if report.status != ReportStatus.COMPLETED:
            return jsonify({"success": False, "error": "El informe todavía no terminó."}), 409
        fmt = request.args.get('format', 'md').lower()
        markdown = report.markdown_content or ""
        if request.args.get("locale") == "es":
            from ..services.report_localization import localized_markdown
            from ..services.report_localization import _CJK
            if _CJK.search(markdown):
                localized = localized_markdown(report_id)
                if localized is None:
                    return jsonify({
                        "success": False,
                        "error": "Para exportar en español, primero traducí todos los capítulos desde el informe.",
                    }), 409
                markdown = localized
        # Enrich exports on demand; never mutate the original saved report.
        from ..services.simulation_metrics import legacy_metrics, followup_metrics
        metrics = legacy_metrics(report.simulation_id,
            os.path.join(SimulationRunner.RUN_STATE_DIR,report.simulation_id))
        metrics["followups"]=followup_metrics(
            os.path.join(ReportManager.REPORTS_DIR,report_id,"interacciones.jsonl"),
            report.simulation_id)
        quality = metrics["interaction_quality"]
        quality_warning = (quality["status"] not in ("acceptable","good"))
        if quality_warning:
            markdown = (
                "**ADVERTENCIA — INTERACCIÓN INSUFICIENTE O NO VERIFICABLE:** "
                + quality["label"] + ". " + " ".join(quality["issues"])
                + " Este informe no acredita una conversación multiagente válida.\n\n"
                + markdown
            )
        metrics_lines = [
            "", "## Estadísticas de interacciones y actividad simulada", "",
            "**Alcance:** eventos sintéticos guardados; fechas de ejecución, no fechas del escenario.",
            f"- Agentes participantes: {metrics['active_participants']}",
            f"- Acciones: {metrics['total_actions']}",
            f"- Publicaciones/comentarios registrados: {metrics['message_actions']}",
            f"- Relaciones con destinatario explícito: {metrics['recorded_interaction_pairs']}",
            f"- Respuestas entre participantes: {metrics['cross_agent_messages']}",
            f"- Calidad de interacción: {quality['label']}",
            f"- Concentración máxima en un participante: {quality['maximum_action_share_percent']}%",
            f"- Primer evento: {metrics['first_event'] or 'No registrado'}",
            f"- Último evento: {metrics['last_event'] or 'No registrado'}", "",
            "### Actividad por día",
            "| Fecha | Acciones |", "|---|---:|",
        ] + [f"| {r['date']} | {r['count']} |" for r in metrics["by_day"]] + [
            "", "### Actividad por hora", "| Hora | Acciones |", "|---|---:|",
        ] + [f"| {r['hour']}:00 | {r['count']} |" for r in metrics["by_hour"]] + [
            "", "### Acciones por ronda", "| Ronda | Acciones |", "|---|---:|",
        ] + [f"| {r['round']} | {r['count']} |" for r in metrics["by_round"]] + [
            "", "### Agentes que participaron", "| Agente sintético | ID | Acciones | Mensajes |",
            "|---|---|---:|---:|",
        ] + [f"| {r['name'].replace('|','/')} | {r['id']} | {r['actions']} | {r['messages']} |"
             for r in metrics["participants"]] + [
            "", "### Tipos de acción", "| Acción | Conteo |", "|---|---:|",
        ] + [f"| {r['type']} | {r['count']} |" for r in metrics["by_type"]] + [
            "", "### Interacciones con destinatario registrado",
            "| Emisor | Destinatario | Conteo |", "|---|---|---:|",
        ] + [f"| {r['from']} | {r['to']} | {r['count']} |" for r in metrics["interactions"]]
        if metrics["partial"]:
            metrics_lines += ["", "**Advertencia:** conteo parcial por límite de lectura segura."]
        follow=metrics["followups"]
        metrics_lines += [
            "", "## Conversaciones y encuestas posteriores al informe (separadas)", "",
            f"- Turnos de chat posteriores: {follow['chat_turns']}",
            f"- Encuestas posteriores: {follow['surveys']}",
            f"- Respuestas sintéticas a encuestas: {follow['survey_answers']}",
            f"- Respuestas dirigidas a participantes: {follow['participant_turns']}",
            "| Fecha | Interacciones posteriores |", "|---|---:|",
        ] + [f"| {item['date']} | {item['count']} |" for item in follow['by_day']]
        markdown += "\n" + "\n".join(metrics_lines) + "\n"
        if fmt == 'md':
            payload = markdown.encode('utf-8')
            mime, ext = "text/markdown", "md"
        elif fmt == 'txt':
            payload = markdown.encode('utf-8')
            mime, ext = "text/plain", "txt"
        elif fmt == 'json':
            payload = json.dumps({
                "report_id": report.report_id,
                "simulation_id": report.simulation_id,
                "created_at": report.created_at,
                "completed_at": report.completed_at,
                "content_markdown": markdown,
                "simulation_metrics": metrics,
                "source_note": "Escenario sintético; no es una encuesta real.",
            }, ensure_ascii=False, indent=2).encode('utf-8')
            mime, ext = "application/json", "json"
        elif fmt == 'html':
            # Escaped HTML intentionally avoids interpreting model-authored markup.
            page = (
                '<!doctype html><html lang="es"><head><meta charset="utf-8">'
                '<title>Tenonderã — Informe de simulación</title>'
                '<style>body{max-width:900px;margin:50px auto;padding:24px;'
                'font-family:system-ui,sans-serif;color:#173658;line-height:1.6}'
                'pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}'
                'h1{color:#11699f}small{color:#5d7890}'
                '@media print{body{margin:0;padding:0}}</style></head><body>'
                '<h1>Tenonderã · Informe guardado</h1>'
                '<small>Resultados de un escenario sintético, no de una encuesta real.</small>'
                + ('<aside role="alert" style="padding:14px;margin:15px 0;'
                   'border:2px solid #b24b32;background:#fff1e8">'
                   '<strong>CALIDAD DE INTERACCIÓN INSUFICIENTE O NO VERIFICABLE</strong><p>'
                   + html.escape(" ".join(quality["issues"]) or quality["label"])
                   + '</p></aside>' if quality_warning else '')
                + '<pre>' + html.escape(markdown) + '</pre></body></html>'
            )
            payload = page.encode("utf-8")
            mime, ext = "text/html", "html"
        else:
            return jsonify({"success": False, "error": "Formato no compatible."}), 400
        return send_file(
            io.BytesIO(payload),
            mimetype=mime,
            as_attachment=True,
            download_name=f"Tenondera_{report_id}.{ext}",
        )
    except Exception as error:
        logger.exception("Error en exportación: %s", type(error).__name__)
        return jsonify({"success": False, "error": "No se pudo exportar el informe."}), 500



@report_bp.route('/<report_id>/localize', methods=['GET', 'POST'])
def localize_persisted_report(report_id: str):
    """Read/translate one saved report part with durable Spanish caching."""
    from ..services.report_localization import (
        TranslationBusy, get_saved_translation, translate_saved_part,
    )
    part = request.args.get('part', 'outline') if request.method == 'GET' else (
        (request.get_json(silent=True) or {}).get('part', 'outline')
    )
    try:
        if request.method == 'GET':
            content = get_saved_translation(report_id, part)
            return jsonify({"success": True, "data": {"cached": bool(content), **(content or {})}})
        content = translate_saved_part(report_id, part)
        return jsonify({"success": True, "data": content})
    except TranslationBusy as error:
        return jsonify({"success": False, "error": str(error)}), 429
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        logger.exception("Error de traducción guardada: %s", type(error).__name__)
        return jsonify({"success": False, "error": "No se pudo traducir el informe. Volvé a intentarlo."}), 502


# ============== 报告进度与分章节接口 ==============

@report_bp.route('/<report_id>/progress', methods=['GET'])
def get_report_progress(report_id: str):
    """
    获取报告生成进度（实时）
    
    返回：
        {
            "success": true,
            "data": {
                "status": "generating",
                "progress": 45,
                "message": "正在生成章节: 关键发现",
                "current_section": "关键发现",
                "completed_sections": ["执行摘要", "模拟背景"],
                "updated_at": "2025-12-09T..."
            }
        }
    """
    try:
        progress = ReportManager.get_progress(report_id)
        
        if not progress:
            return jsonify({
                "success": False,
                "error": t('api.reportProgressNotAvail', id=report_id)
            }), 404
        
        return jsonify({
            "success": True,
            "data": progress
        })
        
    except Exception as e:
        logger.error(f"获取报告进度失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/sections', methods=['GET'])
def get_report_sections(report_id: str):
    """
    获取已生成的章节列表（分章节输出）
    
    前端可以轮询此接口获取已生成的章节内容，无需等待整个报告完成
    
    返回：
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "sections": [
                    {
                        "filename": "section_01.md",
                        "section_index": 1,
                        "content": "## 执行摘要\\n\\n..."
                    },
                    ...
                ],
                "total_sections": 3,
                "is_complete": false
            }
        }
    """
    try:
        sections = ReportManager.get_generated_sections(report_id)
        
        # 获取报告状态
        report = ReportManager.get_report(report_id)
        is_complete = report is not None and report.status == ReportStatus.COMPLETED
        
        return jsonify({
            "success": True,
            "data": {
                "report_id": report_id,
                "sections": sections,
                "total_sections": len(sections),
                "is_complete": is_complete
            }
        })
        
    except Exception as e:
        logger.error(f"获取章节列表失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/section/<int:section_index>', methods=['GET'])
def get_single_section(report_id: str, section_index: int):
    """
    获取单个章节内容
    
    返回：
        {
            "success": true,
            "data": {
                "filename": "section_01.md",
                "content": "## 执行摘要\\n\\n..."
            }
        }
    """
    try:
        section_path = ReportManager._get_section_path(report_id, section_index)
        
        if not os.path.exists(section_path):
            return jsonify({
                "success": False,
                "error": t('api.sectionNotFound', index=f"{section_index:02d}")
            }), 404
        
        with open(section_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            "success": True,
            "data": {
                "filename": f"section_{section_index:02d}.md",
                "section_index": section_index,
                "content": content
            }
        })
        
    except Exception as e:
        logger.error(f"获取章节内容失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 报告状态检查接口 ==============

@report_bp.route('/check/<simulation_id>', methods=['GET'])
def check_report_status(simulation_id: str):
    """
    检查模拟是否有报告，以及报告状态
    
    用于前端判断是否解锁Interview功能
    
    返回：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "has_report": true,
                "report_status": "completed",
                "report_id": "report_xxxx",
                "interview_unlocked": true
            }
        }
    """
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)
        
        has_report = report is not None
        report_status = report.status.value if report else None
        report_id = report.report_id if report else None
        
        # 只有报告完成后才解锁interview
        interview_unlocked = has_report and report.status == ReportStatus.COMPLETED
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "has_report": has_report,
                "report_status": report_status,
                "report_id": report_id,
                "interview_unlocked": interview_unlocked
            }
        })
        
    except Exception as e:
        logger.error(f"检查报告状态失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Agent 日志接口 ==============

@report_bp.route('/<report_id>/agent-log', methods=['GET'])
def get_agent_log(report_id: str):
    """
    获取 Report Agent 的详细执行日志
    
    实时获取报告生成过程中的每一步动作，包括：
    - 报告开始、规划开始/完成
    - 每个章节的开始、工具调用、LLM响应、完成
    - 报告完成或失败
    
    Query参数：
        from_line: 从第几行开始读取（可选，默认0，用于增量获取）
    
    返回：
        {
            "success": true,
            "data": {
                "logs": [
                    {
                        "timestamp": "2025-12-13T...",
                        "elapsed_seconds": 12.5,
                        "report_id": "report_xxxx",
                        "action": "tool_call",
                        "stage": "generating",
                        "section_title": "执行摘要",
                        "section_index": 1,
                        "details": {
                            "tool_name": "insight_forge",
                            "parameters": {...},
                            ...
                        }
                    },
                    ...
                ],
                "total_lines": 25,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        from_line = request.args.get('from_line', 0, type=int)
        
        log_data = ReportManager.get_agent_log(report_id, from_line=from_line)
        
        return jsonify({
            "success": True,
            "data": log_data
        })
        
    except Exception as e:
        logger.error(f"获取Agent日志失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/agent-log/stream', methods=['GET'])
def stream_agent_log(report_id: str):
    """
    获取完整的 Agent 日志（一次性获取全部）
    
    返回：
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 25
            }
        }
    """
    try:
        logs = ReportManager.get_agent_log_stream(report_id)
        
        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })
        
    except Exception as e:
        logger.error(f"获取Agent日志失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 控制台日志接口 ==============

@report_bp.route('/<report_id>/console-log', methods=['GET'])
def get_console_log(report_id: str):
    """
    获取 Report Agent 的控制台输出日志
    
    实时获取报告生成过程中的控制台输出（INFO、WARNING等），
    这与 agent-log 接口返回的结构化 JSON 日志不同，
    是纯文本格式的控制台风格日志。
    
    Query参数：
        from_line: 从第几行开始读取（可选，默认0，用于增量获取）
    
    返回：
        {
            "success": true,
            "data": {
                "logs": [
                    "[19:46:14] INFO: 搜索完成: 找到 15 条相关事实",
                    "[19:46:14] INFO: 图谱搜索: graph_id=xxx, query=...",
                    ...
                ],
                "total_lines": 100,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        from_line = request.args.get('from_line', 0, type=int)
        
        log_data = ReportManager.get_console_log(report_id, from_line=from_line)
        
        return jsonify({
            "success": True,
            "data": log_data
        })
        
    except Exception as e:
        logger.error(f"获取控制台日志失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/console-log/stream', methods=['GET'])
def stream_console_log(report_id: str):
    """
    获取完整的控制台日志（一次性获取全部）
    
    返回：
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 100
            }
        }
    """
    try:
        logs = ReportManager.get_console_log_stream(report_id)
        
        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })
        
    except Exception as e:
        logger.error(f"获取控制台日志失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 工具调用接口（供调试使用）==============

@report_bp.route('/tools/search', methods=['POST'])
def search_graph_tool():
    """
    图谱搜索工具接口（供调试使用）
    
    请求（JSON）：
        {
            "graph_id": "mirofish_xxxx",
            "query": "搜索查询",
            "limit": 10
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        query = data.get('query')
        limit = data.get('limit', 10)
        
        if not graph_id or not query:
            return jsonify({
                "success": False,
                "error": t('api.requireGraphIdAndQuery')
            }), 400
        
        from ..services.zep_tools import ZepToolsService
        
        tools = ZepToolsService()
        result = tools.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"图谱搜索失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/tools/statistics', methods=['POST'])
def get_graph_statistics_tool():
    """
    图谱统计工具接口（供调试使用）
    
    请求（JSON）：
        {
            "graph_id": "mirofish_xxxx"
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.requireGraphId')
            }), 400
        
        from ..services.zep_tools import ZepToolsService
        
        tools = ZepToolsService()
        result = tools.get_graph_statistics(graph_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取图谱统计失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
