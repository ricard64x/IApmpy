<template>
  <div class="main-view" :class="{ 'view-graph': viewMode === 'graph' }">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')"><TenonderaBrand compact /></div>
      </div>
      
      <div class="header-center">
        <div class="view-switcher">
          <button 
            v-for="mode in ['graph', 'split', 'workbench']" 
            :key="mode"
            class="switch-btn"
            :class="{ active: viewMode === mode }"
            @click="viewMode = mode"
          >
            {{ { graph: $t('main.layoutGraph'), split: $t('main.layoutSplit'), workbench: $t('main.layoutWorkbench') }[mode] }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <LanguageSwitcher />
        <div class="step-divider"></div>
        <div class="workflow-step">
          <span class="step-num">{{ $t('main.stepPrefix') }} {{ currentStep }}/5</span>
          <span class="step-name">{{ $tm('main.stepNames')[currentStep - 1] }}</span>
        </div>
        <div class="step-divider"></div>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
      </div>
    </header>
    <BuildProgressBanner
      v-if="currentPhase === 1"
      :progress="cloudProgress || buildProgress"
      :refreshed-at="lastProgressAt"
      :stale="progressUnavailable"
      :refreshing="progressRefreshing"
      @refresh="pollTaskStatus(projectData?.graph_build_task_id)"
      @go-projects="router.push('/')"
      @focus-workbench="viewMode = 'workbench'"
    />

    <section v-if="projectNeedsAttention" class="workflow-attention" role="status">
      <div>
        <strong>Este proyecto no está procesando</strong>
        <p>{{ projectActionMessage(projectData) }}</p>
        <p v-if="capabilities && !capabilities.ontology_enabled" class="workflow-capability">
          El modelo de IA para analizar documentos no está configurado en esta instancia.
          Getangiru sí puede consultar la memoria local, pero no generar la ontología.
        </p>
        <p v-if="capabilities && !capabilities.graph_enabled" class="workflow-capability">
          La construcción del grafo también requiere configurar su proveedor.
        </p>
      </div>
      <div class="workflow-attention-actions">
        <button @click="router.push({ name: 'Home' })">Preparar nuevo análisis</button>
        <button class="secondary" @click="router.push({ name: 'Dashboard' })">Mis proyectos</button>
      </div>
    </section>
    <section v-else-if="error" class="workflow-attention workflow-error" role="alert">
      <div><strong>El proceso no pudo continuar</strong><p>{{ error }}</p></div>
      <button @click="router.push({ name: 'Home' })">Volver a cargar documentos</button>
    </section>

    <!-- Main Content Area -->
    <main class="content-area">
      <!-- Left Panel: Graph -->
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <GraphPanel 
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="currentPhase"
          :idle="projectNeedsAttention"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- Right Panel: Step Components -->
      <div class="panel-wrapper right" :style="rightPanelStyle">
        <!-- Step 1: 图谱构建 -->
        <Step1GraphBuild 
          v-if="currentStep === 1"
          :currentPhase="currentPhase"
          :projectData="projectData"
          :ontologyProgress="ontologyProgress"
          :buildProgress="buildProgress"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @next-step="handleNextStep"
        />
        <!-- Step 2: 环境搭建 -->
        <Step2EnvSetup
          v-else-if="currentStep === 2"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import TenonderaBrand from '../components/TenonderaBrand.vue'
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import GraphPanel from '../components/GraphPanel.vue'
import BuildProgressBanner from '../components/BuildProgressBanner.vue'
import Step1GraphBuild from '../components/Step1GraphBuild.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import { generateOntology, getProject, buildGraph, getTaskStatus, getProjectBuildStatus, getGraphData, getProcessingCapabilities } from '../api/graph'
import { projectRequiresAction, projectActionMessage } from '../utils/projectWorkflow'
import { getPendingUpload, clearPendingUpload } from '../store/pendingUpload'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'

const route = useRoute()
const router = useRouter()
const { t, tm } = useI18n()

// Layout State
const viewMode = ref('split') // graph | split | workbench

// Recalculate the D3 canvas after the user switches from the compact workbench
// to the full-width graph. A hidden SVG may otherwise retain a zero-size viewBox.
watch(viewMode, async () => {
  await nextTick()
  window.dispatchEvent(new Event('resize'))
})

// Step State
const currentStep = ref(1) // 1: 图谱构建, 2: 环境搭建, 3: 开始模拟, 4: 报告生成, 5: 深度互动
const stepNames = computed(() => tm('main.stepNames'))

// Data State
const currentProjectId = ref(route.params.projectId)
const loading = ref(false)
const graphLoading = ref(false)
const error = ref('')
const projectData = ref(null)
const capabilities = ref(null)
const projectNeedsAttention = computed(() => projectRequiresAction(projectData.value))
const graphData = ref(null)
const currentPhase = ref(-1) // -1: Upload, 0: Ontology, 1: Build, 2: Complete
const ontologyProgress = ref(null)
const buildProgress = ref(null)
const cloudProgress = ref(null)
const lastProgressAt = ref(null)
const progressUnavailable = ref(false)
const progressRefreshing = ref(false)
const systemLogs = ref([])

// Polling timers
let pollTimer = null
let graphPollTimer = null
let graphPollBusy = false
let recoveryInProgress = false
let lastProgressLogBucket = -1

// --- Computed Layout Styles ---
const leftPanelStyle = computed(() => {
  if (viewMode.value === 'graph') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'workbench') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const rightPanelStyle = computed(() => {
  if (viewMode.value === 'workbench') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'graph') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

// --- Status Computed ---
const statusClass = computed(() => {
  if (projectNeedsAttention.value) return 'waiting'
  if (error.value) return 'error'
  if (currentPhase.value >= 2) return 'completed'
  return 'processing'
})

const statusText = computed(() => {
  if (projectNeedsAttention.value) return 'Pendiente de preparación'
  if (error.value) return t('common.error')
  if (currentPhase.value >= 2) return t('common.ready')
  if (currentPhase.value === 1) return t('main.statusBuildingGraph')
  if (currentPhase.value === 0) return t('main.statusGeneratingOntology')
  return t('main.statusInitializing')
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  // Keep last 100 logs
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

const handleNextStep = (params = {}) => {
  if (currentStep.value < 5) {
    currentStep.value++
    addLog(t('log.enterStep', { step: currentStep.value, name: stepNames.value[currentStep.value - 1] }))
    
    // 如果是从 Step 2 进入 Step 3，记录模拟轮数配置
    if (currentStep.value === 3 && params.maxRounds) {
      addLog(t('log.customSimRounds', { rounds: params.maxRounds }))
    }
  }
}

const handleGoBack = () => {
  if (currentStep.value > 1) {
    currentStep.value--
    addLog(t('log.returnToStep', { step: currentStep.value, name: stepNames.value[currentStep.value - 1] }))
  }
}

// --- Data Logic ---

const initProject = async () => {
  addLog('Project view initialized.')
  try {
    const response = await getProcessingCapabilities()
    if (response.success && response.data) capabilities.value = response.data
  } catch (_e) {
    // Non-critical: project status still comes from durable storage.
  }
  if (currentProjectId.value === 'new') {
    await handleNewProject()
  } else {
    await loadProject()
  }
}

const handleNewProject = async () => {
  const pending = getPendingUpload()
  if (!pending.isPending || pending.files.length === 0) {
    error.value = 'No pending files found.'
    addLog('Error: No pending files found for new project.')
    return
  }
  
  if (capabilities.value?.ontology_enabled === false) {
    error.value = 'Esta instancia no tiene un modelo de IA configurado para analizar documentos. Getangiru puede recuperar memoria local, pero no generar ontologías.'
    addLog('Generación no iniciada: falta configurar el motor de IA.')
    return
  }
  try {
    loading.value = true
    currentPhase.value = 0
    ontologyProgress.value = { message: 'Uploading and analyzing docs...' }
    addLog('Starting ontology generation: Uploading files...')
    
    const formData = new FormData()
    pending.files.forEach(f => formData.append('files', f))
    formData.append('simulation_requirement', pending.simulationRequirement)
    
    const res = await generateOntology(formData)
    if (res.success) {
      clearPendingUpload()
      currentProjectId.value = res.data.project_id
      projectData.value = res.data
      
      router.replace({ name: 'Process', params: { projectId: res.data.project_id } })
      ontologyProgress.value = null
      addLog(`Ontology generated successfully for project ${res.data.project_id}`)
      await startBuildGraph()
    } else {
      error.value = res.error || 'Ontology generation failed'
      addLog(`Error generating ontology: ${error.value}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in handleNewProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const loadProject = async () => {
  try {
    loading.value = true
    addLog(`Loading project ${currentProjectId.value}...`)
    const res = await getProject(currentProjectId.value)
    if (res.success) {
      projectData.value = res.data
      updatePhaseByStatus(res.data.status)
      addLog(`Project loaded. Status: ${res.data.status}`)
      if (projectRequiresAction(res.data)) {
        addLog('No existe una tarea activa de generación; el expediente queda pendiente.')
      }
      
      if (res.data.status === 'ontology_generated' && !res.data.graph_id) {
        await startBuildGraph()
      } else if (
        (res.data.status === 'graph_building' || res.data.status === 'failed')
        && res.data.zep_batch_id
      ) {
        // Old code marked large batches as locally failed after 600s while
        // Zep was still processing. Recover status from the saved batch ID.
        currentPhase.value = 1
        error.value = ''
        startPollingTask(res.data.graph_build_task_id)
      } else if (res.data.status === 'graph_completed' && res.data.graph_id) {
        currentPhase.value = 2
        await loadGraph(res.data.graph_id)
      }
    } else {
      error.value = res.error
      addLog(`Error loading project: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in loadProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const updatePhaseByStatus = (status) => {
  switch (status) {
    case 'created': currentPhase.value = -1; break;
    case 'ontology_generated': currentPhase.value = 0; break;
    case 'graph_building': currentPhase.value = 1; break;
    case 'graph_completed': currentPhase.value = 2; break;
    case 'failed':
      currentPhase.value = -1
      error.value = projectData.value?.error || 'El análisis anterior no se completó.'
      break;
  }
}

const startBuildGraph = async () => {
  try {
    currentPhase.value = 1
    buildProgress.value = { progress: 0, message: 'Starting build...' }
    addLog('Initiating graph build...')
    
    const res = await buildGraph({ project_id: currentProjectId.value })
    if (res.success) {
      if (res.data.reused && res.data.graph_id) {
        const projectRes = await getProject(currentProjectId.value)
        if (projectRes.success) projectData.value = projectRes.data
        if (projectRes.data?.status === 'graph_completed') {
          await finishGraphBuild()
        } else {
          // 'reused' also means a running Cloud batch; never treat it as done.
          startPollingTask(res.data.task_id || projectRes.data?.graph_build_task_id)
        }
        return
      }

      addLog(`Graph build task started. Task ID: ${res.data.task_id}`)
      startPollingTask(res.data.task_id)
    } else {
      error.value = res.error
      addLog(`Error starting build: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in startBuildGraph: ${err.message}`)
  }
}

const startGraphPolling = () => {
  addLog('Started polling for graph data...')
  fetchGraphData()
  graphPollTimer = setInterval(fetchGraphData, 10000)
}

const fetchGraphData = async () => {
  try {
    // Refresh project info to check for graph_id
    const projRes = await getProject(currentProjectId.value)
    if (projRes.success && projRes.data.graph_id) {
      const gRes = await getGraphData(projRes.data.graph_id)
      if (gRes.success) {
        graphData.value = gRes.data
        const nodeCount = gRes.data.node_count || gRes.data.nodes?.length || 0
        const edgeCount = gRes.data.edge_count || gRes.data.edges?.length || 0
        addLog(`Graph data refreshed. Nodes: ${nodeCount}, Edges: ${edgeCount}`)
      }
    }
  } catch (err) {
    console.warn('Graph fetch error:', err)
  }
}

const finishGraphBuild = async () => {
  if (currentPhase.value >= 2) return
  stopPolling()
  stopGraphPolling()
  currentPhase.value = 2
  buildProgress.value = { progress: 100, message: 'Red de conocimiento finalizada.' }
  const projectRes = await getProject(currentProjectId.value)
  if (projectRes.success) {
    projectData.value = projectRes.data
    if (projectRes.data.graph_id) await loadGraph(projectRes.data.graph_id)
  }
}

const recoverFinishedCloudBatch = async () => {
  if (recoveryInProgress) return
  recoveryInProgress = true
  try {
    // This is safe for a saved, verified Zep batch: the backend re-attaches
    // its existing identity instead of adding the document for a second time.
    const response = await buildGraph({ project_id: currentProjectId.value })
    if (!response.success) throw new Error(response.error || 'No se pudo retomar.')
    if (response.data.task_id) {
      startPollingTask(response.data.task_id)
    } else {
      const projectRes = await getProject(currentProjectId.value)
      if (projectRes.data?.status === 'graph_completed') await finishGraphBuild()
    }
  } catch (e) {
    error.value = 'No se pudo recuperar el cierre de la red: ' + (e.message || 'error')
  } finally {
    recoveryInProgress = false
  }
}

const startPollingTask = (taskId) => {
  stopPolling()
  pollTaskStatus(taskId)
  // The remote Cloud batch advances independently; avoid 2s HTTP polling.
  pollTimer = setInterval(() => pollTaskStatus(taskId), 12000)
}

const pollTaskStatus = async (taskId) => {
  if (graphPollBusy || !currentProjectId.value || (typeof document !== 'undefined' && document.hidden)) return
  graphPollBusy = true
  progressRefreshing.value = true
  try {
    // The Zep batch status is durable; TaskManager is only in-process.
    // Read the remote truth first so a Fly restart does not freeze the UI.
    let cloud = null
    try {
      const result = await getProjectBuildStatus(currentProjectId.value)
      if (result.success && result.data) {
        cloud = result.data
        cloudProgress.value = result.data
        lastProgressAt.value = Date.now()
        progressUnavailable.value = false
      } else {
        progressUnavailable.value = true
      }
    } catch (_e) {
      // Keep the latest known status on transient read failures.
      progressUnavailable.value = true
    }

    if (cloud?.project_status === 'graph_completed' || cloud?.status === 'completed') {
      await finishGraphBuild()
      return
    }

    if (cloud && ['failed', 'partial', 'invalid', 'canceled'].includes(cloud.status)) {
      stopPolling()
      error.value = 'El servicio de conocimiento informó un fallo. Revisá el estado del lote antes de reintentar.'
      return
    }

    if (cloud?.total > 0) {
      const pct = Number(cloud.percent || 0)
      const state = cloud.status === 'succeeded' ? 'Consolidando relaciones'
        : cloud.status === 'queued' ? 'En cola de procesamiento'
        : 'Construyendo relaciones'
      const message = state + ': ' + cloud.processed + ' de ' + cloud.total
        + ' fragmentos (' + pct.toFixed(1) + ' %). '
        + (cloud.processing || 0) + ' en curso, ' + (cloud.failed || 0) + ' fallidos.'
      buildProgress.value = { progress: pct, message, processed: cloud.processed, total: cloud.total }
      const bucket = Math.floor(pct / 5)
      if (bucket > lastProgressLogBucket) {
        lastProgressLogBucket = bucket
        addLog(message)
      }
      if (cloud.needs_recovery) await recoverFinishedCloudBatch()
      return
    }

    // Early stages may not have an external batch yet.
    if (taskId) {
      try {
        const res = await getTaskStatus(taskId)
        if (res.success) {
          const task = res.data
          if (task.status === 'completed') {
            await finishGraphBuild()
          } else if (task.status === 'failed') {
            stopPolling()
            error.value = task.message || 'No se pudo preparar el procesamiento.'
          } else {
            buildProgress.value = { progress: task.progress || 0, message: task.message }
          }
        }
      } catch (_e) {
        // A Fly restart can erase this in-memory task. Cloud status remains
        // available through the project endpoint and will be polled again.
        buildProgress.value = buildProgress.value || {
          progress: 0, message: 'Recuperando el seguimiento del procesamiento...'
        }
      }
    }
  } finally {
    graphPollBusy = false
    progressRefreshing.value = false
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  addLog(`Loading full graph data: ${graphId}`)
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('Graph data loaded successfully.')
    } else {
      addLog(`Failed to load graph data: ${res.error}`)
    }
  } catch (e) {
    addLog(`Exception loading graph: ${e.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    addLog('Manual graph refresh triggered.')
    loadGraph(projectData.value.graph_id)
  }
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const stopGraphPolling = () => {
  if (graphPollTimer) {
    clearInterval(graphPollTimer)
    graphPollTimer = null
    addLog('Graph polling stopped.')
  }
}

const onVisibilityChange = () => {
  if (!document.hidden && currentPhase.value === 1) {
    pollTaskStatus(projectData.value?.graph_build_task_id)
  }
}
onMounted(() => {
  // On a narrow screen the split view forces two tiny unusable columns.
  // Prefer the light, readable workbench; let users open the full-width
  // graph explicitly from the header.
  if (window.matchMedia('(max-width: 720px)').matches && viewMode.value === 'split') {
    viewMode.value = 'workbench'
  }
  document.addEventListener('visibilitychange', onVisibilityChange)
  initProject()
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', onVisibilityChange)
  stopPolling()
  stopGraphPolling()
})
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #FFF;
  overflow: hidden;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

/* Header */
.app-header {
  height: 60px;
  border-bottom: 1px solid #EAEAEA;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #FFF;
  z-index: 100;
  position: relative;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  cursor: pointer;
}

.view-switcher {
  display: flex;
  background: #F5F5F5;
  padding: 4px;
  border-radius: 6px;
  gap: 4px;
}

.switch-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: #FFF;
  color: #000;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #999;
}

.step-name {
  font-weight: 700;
  color: #000;
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: #E0E0E0;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #CCC;
}

.status-indicator.processing .dot { background: #FF5722; animation: pulse 1s infinite; }
.status-indicator.waiting .dot { background: #B7791F; animation: none; }
.status-indicator.completed .dot { background: #4CAF50; }
.status-indicator.error .dot { background: #F44336; }

@keyframes pulse { 50% { opacity: 0.5; } }

/* Persistent project states must not be presented as running tasks. */
.workflow-attention {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
  padding: 14px 24px;
  background: #fffaf0;
  border-bottom: 1px solid #ead7a8;
  color: #44351c;
  font-size: 13px;
}
.workflow-attention strong { font-size: 15px; }
.workflow-attention p { margin: 6px 0; line-height: 1.45; max-width: 800px; }
.workflow-attention .workflow-capability { color: #745325; }
.workflow-attention-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.workflow-attention button { border: none; background: #244b66; color: white; border-radius: 7px; padding: 9px 13px; cursor: pointer; }
.workflow-attention button.secondary { color: #244b66; background: white; border: 1px solid #a3b1bf; }
.workflow-error { background: #fff4f3; border-color: #dfb8b4; }
@media (max-width: 720px) { .workflow-attention { align-items: stretch; padding: 12px; } }

/* Content */
.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border-right: 1px solid #EAEAEA;
}

@media (max-width: 720px) {
  .app-header {
    height: auto;
    min-height: 96px;
    padding: 8px 12px;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-rows: auto auto;
    gap: 7px;
    flex-shrink: 0;
  }
  .header-left { grid-column: 1; grid-row: 1; min-width: 0; }
  .header-right { grid-column: 2; grid-row: 1; gap: 7px; justify-content: flex-end; }
  .header-center {
    position: static;
    left: auto;
    transform: none;
    grid-column: 1 / -1;
    grid-row: 2;
    width: 100%;
  }
  .view-switcher { width: 100%; display: flex; justify-content: stretch; }
  .switch-btn { flex: 1; padding: 7px 8px; font-size: 11px; white-space: nowrap; }
  .switch-btn:nth-child(2) { display: none; }
  .step-divider, .status-indicator { display: none; }
  .workflow-step { flex-direction: column; align-items: flex-end; gap: 2px; font-size: 11px; }
  .step-name { display: none; }
  .content-area { display: block; min-height: 0; }
  .panel-wrapper { height: 100%; transition: none; }
  .main-view:not(.view-graph) .panel-wrapper.left { display: none; }
  .main-view:not(.view-graph) .panel-wrapper.right {
    display: block;
    width: 100% !important;
    opacity: 1 !important;
    transform: none !important;
  }
  .main-view.view-graph .panel-wrapper.left {
    display: block;
    width: 100% !important;
    opacity: 1 !important;
    transform: none !important;
  }
  .main-view.view-graph .panel-wrapper.right { display: none; }
}
</style>
