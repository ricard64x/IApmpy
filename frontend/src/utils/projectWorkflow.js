/**
 * Workflow state is derived from durable data, not the visual step number.
 * A saved "created" project has no active ontology job; never show a spinner.
 */
export function projectRequiresAction(project) {
  if (!project || typeof project !== 'object') return false
  if (project.status === 'created') {
    return !project.ontology && !project.graph_build_task_id && !project.zep_batch_id
  }
  return project.status === 'failed' && !project.zep_batch_id
}

export function projectActionMessage(project) {
  if (!projectRequiresAction(project)) return ''
  if (project.status === 'failed') {
    return 'El análisis anterior se interrumpió. No hay una tarea de ontología ejecutándose.'
  }
  if (!Array.isArray(project.files) || project.files.length === 0) {
    return 'Este proyecto no contiene documentos y no tiene un proceso de generación iniciado. La memoria contextual puede consultarse, pero no se creó una ontología.'
  }
  return 'Este proyecto tiene documentos guardados, pero no hay una generación activa de ontología. Podés iniciar un análisis nuevo sin perder el expediente actual.'
}
