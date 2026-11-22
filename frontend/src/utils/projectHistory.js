/** Unified, account-filtered project timeline.
 * The API already restricts both sources by account. Do not infer ownership
 * or expose cross-user projects on the client.
 */
export function mergeProjectHistory(savedProjects = [], simulations = []) {
  const entries = new Map()
  for (const project of savedProjects || []) {
    if (!project || !project.project_id) continue
    entries.set('project:' + project.project_id, {
      ...project,
      project_name: project.name || project.project_name || 'Proyecto sin título',
      project_status: project.status || null,
      status: undefined,
      simulation_id: null,
      runner_status: null,
      report_id: null,
      is_project_only: true,
    })
  }
  for (const simulation of simulations || []) {
    if (!simulation || !simulation.simulation_id) continue
    const key = simulation.project_id
      ? 'project:' + simulation.project_id
      : 'simulation:' + simulation.simulation_id
    const project = entries.get(key)
    entries.set(key, {
      ...(project || {}),
      ...simulation,
      project_name: simulation.project_name || project?.project_name || 'Proyecto sin título',
      project_status: project?.project_status || simulation.project_status || null,
      owner_id: simulation.owner_id || project?.owner_id || null,
      files: project?.files?.length ? project.files : simulation.files || [],
      simulation_requirement: simulation.simulation_requirement
        || project?.simulation_requirement || '',
      created_at: project?.created_at || simulation.created_at,
      is_project_only: false,
    })
  }
  return [...entries.values()].sort(
    (a, b) => String(b.created_at || '').localeCompare(String(a.created_at || ''))
  )
}

export function projectEntryStatus(item) {
  if (item?.simulation_id) {
    return {
      label: {
        completed: 'Completada',
        running: 'En ejecución',
        stopped: 'Detenida',
        failed: 'Fallida',
        idle: 'Preparada',
      }[item.runner_status] || 'Registrada',
      style: item.runner_status || 'idle',
    }
  }
  const status = item?.project_status
  if (status === 'graph_building') return { label: 'Construyendo conocimiento', style: 'running' }
  if (status === 'failed' && item?.zep_batch_id) {
    return { label: 'Revisar avance remoto', style: 'running' }
  }
  if (status === 'failed') return { label: 'Requiere atención', style: 'failed' }
  if (status === 'graph_completed') return { label: 'Red de conocimiento lista', style: 'completed' }
  if (status === 'ontology_generated') return { label: 'Estructura preparada', style: 'idle' }
  return { label: 'Documentos guardados', style: 'idle' }
}
