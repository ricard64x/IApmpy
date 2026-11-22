import { ref, watch, onMounted, onUnmounted } from 'vue'
import { getProjectBuildStatus } from '../api/graph'

// The owner-filtered project list is the only source of IDs.
// Poll a small number of active projects and never make the browser
// discover graph or batch identifiers from other users.
export function useLiveProjectProgress(projects, intervalMs = 15000) {
  const liveProgress = ref({})
  const lastUpdated = ref({})
  const unavailable = ref({})
  let timer = null
  let polling = false
  let disposed = false
  const activeIds = () => (projects.value || [])
    .filter(p => p?.project_id &&
      (p.project_status === 'graph_building' || p.status === 'graph_building'
      || ((p.project_status === 'failed' || p.status === 'failed') && p.zep_batch_id)))
    .map(p => p.project_id)
    .filter((id, i, ids) => ids.indexOf(id) === i)
    .slice(0, 5)

  async function refresh() {
    if (polling || disposed || (typeof document !== 'undefined' && document.hidden)) return
    const ids = activeIds()
    if (!ids.length) return
    polling = true
    try {
      await Promise.allSettled(ids.map(async id => {
        try {
          const res = await getProjectBuildStatus(id)
          if (res?.success && res.data) {
            liveProgress.value = { ...liveProgress.value, [id]: res.data }
            lastUpdated.value = { ...lastUpdated.value, [id]: Date.now() }
            unavailable.value = { ...unavailable.value, [id]: false }
          } else {
            unavailable.value = { ...unavailable.value, [id]: true }
          }
        } catch (_) {
          unavailable.value = { ...unavailable.value, [id]: true }
        }
      }))
    } finally {
      polling = false
    }
  }
  function onVisibility() { if (!document.hidden) refresh() }
  const stopWatching = watch(() => activeIds().join(','), refresh, { immediate: true })
  onMounted(() => {
    timer = setInterval(refresh, intervalMs)
    document.addEventListener('visibilitychange', onVisibility)
  })
  onUnmounted(() => {
    disposed = true
    stopWatching()
    if (timer) clearInterval(timer)
    document.removeEventListener('visibilitychange', onVisibility)
  })
  return { liveProgress, lastUpdated, unavailable, refresh }
}

export function progressLabel(remote) {
  if (!remote) return null
  if (remote.status === 'succeeded' || remote.status === 'completed') {
    return 'Procesamiento remoto completo · verificando red'
  }
  if (remote.status === 'queued') return 'En cola de procesamiento'
  if (['failed','invalid','canceled','partial'].includes(remote.status)) {
    return 'Procesamiento detenido · revisar'
  }
  if (!Number(remote.total)) return 'Preparando la red de conocimiento'
  return `Procesando ${remote.processed || 0} de ${remote.total} (${Math.max(0, Math.min(100, Number(remote.percent) || 0)).toFixed(1)} %)`
}
