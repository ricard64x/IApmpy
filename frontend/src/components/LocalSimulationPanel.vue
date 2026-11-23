<template>
  <section class="local-sim-panel" aria-label="Simulación local Getangiru">
    <header class="local-sim-header">
      <div>
        <h3>Simulación multiactor local</h3>
        <p>Ejercicio hipotético con roles, decisiones, evidencias e informe. No ejecuta cambios reales.</p>
      </div>
      <span class="engine-chip">Getangiru · sin Zep</span>
    </header>

    <div v-if="!graphReady" class="local-sim-info">
      Primero completá la construcción del grafo local para habilitar esta simulación.
    </div>
    <template v-else>
      <div class="local-sim-controls">
        <label for="local-sim-mode">Motor de decisiones</label>
        <select id="local-sim-mode" v-model="mode" :disabled="active">
          <option value="hybrid">Híbrido: Qwen local + reglas verificables</option>
          <option value="rules">Solo reglas locales (más rápido)</option>
        </select>
        <button type="button" :disabled="active || busy" @click="run">
          {{ active ? 'Simulación en curso' : busy ? 'Preparando…' : 'Ejecutar simulación local' }}
        </button>
      </div>
      <p class="local-sim-note">
        Una consulta máxima al modelo local por ejecución. No se envían documentos ni memorias
        a proveedores externos. La búsqueda en Internet permanece desactivada.
      </p>
      <div v-if="error" class="local-sim-error" role="alert">{{ error }}</div>
      <div class="local-public-research">
        <p><strong>Consulta pública de vulnerabilidades (opcional)</strong></p>
        <p class="local-sim-note">
          Solo envía identificadores CVE al catálogo público de CISA.
          Nunca envía documentos internos. No realiza búsquedas automáticas.
        </p>
        <div v-if="researchEnabled" class="local-sim-controls">
          <input v-model="cves" placeholder="Ej.: CVE-2024-3400" aria-label="Identificadores CVE" />
          <button type="button" :disabled="busyResearch || !cves.trim()" @click="searchPublic">
            {{ busyResearch ? 'Consultando fuente pública…' : 'Consultar CISA KEV' }}
          </button>
        </div>
        <p v-else class="local-sim-note">Búsqueda externa bloqueada por configuración de seguridad.</p>
        <div v-if="researchError" class="local-sim-error" role="alert">{{ researchError }}</div>
        <div v-if="researchResult" class="local-sim-info">
          Catálogo: {{ researchResult.catalog_version || 'versión no indicada' }}.
          <p v-for="entry in researchResult.entries" :key="entry.cve">
            <strong>{{ entry.cve }}</strong> —
            {{ entry.listed_in_kev ? 'Figura en CISA KEV' : 'No figura en esta edición del catálogo (no significa que sea seguro)' }}.
            {{ entry.product || '' }}
          </p>
        </div>
      </div>

      <div v-if="result" class="local-sim-results" role="status">
        <div class="local-sim-status">
          <strong>{{ statusLabel }}</strong>
          <span>{{ result.phase }} / {{ result.total_phases }} fases</span>
        </div>
        <div class="local-sim-meter" role="progressbar"
             :aria-valuenow="result.progress_pct" aria-valuemin="0" aria-valuemax="100">
          <div :style="{width: result.progress_pct+'%'}"></div>
        </div>
        <p v-if="result.status === 'failed' || result.status === 'interrupted'" class="local-sim-error">
          La ejecución se interrumpió. No se reutilizaron acciones sin validación; podés iniciar una nueva.
          Código: {{ result.error_code || 'sin detalle' }}
        </p>
        <template v-if="result.report">
          <div class="local-sim-metrics">
            <div><strong>{{ result.report.actions }}</strong><span>Decisiones simuladas</span></div>
            <div><strong>{{ result.report.evidence_coverage_pct }}%</strong><span>Con referencia a evidencia</span></div>
            <div><strong>{{ result.report.local_llm_requests }}</strong><span>Consultas a Qwen</span></div>
            <div><strong>{{ result.report.external_model_requests }}</strong><span>Consultas IA externa</span></div>
            <div><strong>{{ result.report.execution_ms }} ms</strong><span>Tiempo total de ejecución</span></div>
          </div>
          <p class="local-sim-warning">
            {{ result.report.disclaimer }}
            La cobertura de evidencia no equivale a precisión ni confirma acciones reales.
          </p>
          <p v-if="result.report.local_model_fallback">
            Qwen no entregó un plan válido. Se aplicaron reglas locales; no se inventó una respuesta del modelo.
          </p>
          <div class="local-sim-actions">
            <button type="button" class="secondary" @click="showActions=!showActions">
              {{ showActions ? 'Ocultar decisiones' : 'Ver decisiones y evidencias' }}
            </button>
            <a :href="reportHref" class="local-sim-download">Exportar informe (.md)</a>
          </div>
          <div v-if="showActions" class="local-sim-history">
            <div v-for="(a, i) in result.actions" :key="a.phase+'-'+a.actor_uuid"
                 class="local-sim-decision">
              <p><strong>Ronda {{ a.phase }} · {{ a.actor_type }}</strong></p>
              <p>{{ a.action_text }}</p>
              <small>Fuente original: {{ a.evidence_source || 'sin evidencia' }}</small>
              <div class="local-sim-review">
                <button type="button" class="secondary" :disabled="busy" @click="review(a,'accept')">
                  Validar decisión
                </button>
                <button type="button" class="secondary" :disabled="busy" @click="review(a,'reject')">
                  Requiere corrección
                </button>
              </div>
            </div>
          </div>
          <p class="local-sim-note">
            Aprendizaje controlado: se almacenan validaciones humanas para priorizar revisiones futuras;
            no se modifican pesos del modelo ni se aprueban decisiones automáticamente.
            Revisiones: {{ result.feedback?.accept || 0 }} aceptadas ·
            {{ result.feedback?.reject || 0 }} observadas.
            <span v-if="result.human_validation?.reviewed">
              Aceptación revisada: {{ result.human_validation.acceptance_rate_pct }}%
              ({{ result.human_validation.reviewed }} decisiones evaluadas; no es precisión predictiva).
            </span>
            <span v-else>Exactitud predictiva: aún no evaluada con evidencia independiente.</span>
          </p>
        </template>
      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import service from '../api'

const props = defineProps({
  projectId: { type: String, required: true },
  graphReady: { type: Boolean, default: false },
})
const mode = ref('hybrid')
const result = ref(null)
const error = ref('')
const busy = ref(false)
const showActions = ref(false)
const researchEnabled = ref(false)
const busyResearch = ref(false)
const researchError = ref('')
const researchResult = ref(null)
const cves = ref('')
let timer = null
let requestNumber = 0

const active = computed(() => ['queued','running'].includes(result.value?.status))
const statusLabel = computed(() => ({
  queued:'En cola local',running:'Ejecutando decisiones simuladas',
  completed:'Simulación finalizada',failed:'Simulación fallida',
  interrupted:'Interrumpida sin reejecución automática'
})[result.value?.status] || 'Sin simulación')
const reportHref = computed(() => result.value?.simulation_id
  ? '/api/native-simulation/'+encodeURIComponent(result.value.simulation_id)+'/report.md' : '#')

async function loadCapabilities() {
  try {
    const r = await service.get('/api/native-simulation/capabilities')
    researchEnabled.value = r?.data?.external_research_enabled === true
  } catch (_e) { researchEnabled.value = false }
}
async function searchPublic() {
  if (!researchEnabled.value || busyResearch.value) return
  busyResearch.value = true
  researchError.value = ''
  researchResult.value = null
  try {
    const ids = [...new Set(cves.value.toUpperCase().split(/[\s,;]+/).filter(Boolean))]
    const response = await service.post('/api/native-simulation/public-cve', { cves: ids })
    researchResult.value = response.data
  } catch (e) {
    researchError.value = e.message || 'No se pudo consultar la fuente pública'
  } finally { busyResearch.value = false }
}
async function loadLatest() {
  const current = ++requestNumber
  if (!props.graphReady) return
  try {
    const response = await service.get('/api/native-simulation/project/'+encodeURIComponent(props.projectId)+'/latest')
    if (current !== requestNumber) return
    result.value = response?.data || null
    managePolling()
  } catch (e) {
    if (current === requestNumber) error.value = e.message || 'No se pudo consultar la simulación'
  }
}
async function update() {
  if (!result.value?.simulation_id) return loadLatest()
  const current = ++requestNumber
  try {
    const response = await service.get('/api/native-simulation/'+encodeURIComponent(result.value.simulation_id))
    if (current !== requestNumber) return
    result.value = response.data
    managePolling()
  } catch (e) {
    if (current === requestNumber) error.value = e.message || 'No se pudo actualizar el estado'
  }
}
function managePolling() {
  if (timer) {clearInterval(timer); timer = null}
  if (active.value) timer = setInterval(update, 2200)
}
async function run() {
  if (busy.value || active.value || !props.graphReady) return
  busy.value = true
  error.value = ''
  try {
    const res = await service.post('/api/native-simulation/start', {
      project_id: props.projectId, mode: mode.value,
    })
    result.value = {
      ...res.data,
      simulation_id:res.data.simulation_id,
      phase:0,total_phases:4,progress_pct:0,
      report:null,actions:[],feedback:{},
    }
    managePolling()
    await update()
  } catch (e) {
    error.value = e.message || 'No se inició la simulación'
  } finally {busy.value = false}
}
async function review(action, verdict) {
  if (!result.value?.simulation_id) return
  busy.value = true
  error.value = ''
  try {
    await service.post('/api/native-simulation/'+encodeURIComponent(result.value.simulation_id)+'/feedback',{
      actor_uuid:action.actor_uuid,phase:action.phase,verdict,note:'',
    })
    await update()
  } catch (e) {
    error.value = e.message || 'No se guardó la validación'
  } finally {busy.value=false}
}
watch(() => props.projectId, () => {
  requestNumber++
  result.value=null
  error.value=''
  showActions.value=false
  if (timer){clearInterval(timer);timer=null}
  loadLatest()
})
watch(() => props.graphReady, enabled => {if (enabled)loadLatest()})
onMounted(() => {loadCapabilities();loadLatest()})
onUnmounted(() => {requestNumber++;if(timer)clearInterval(timer)})
</script>

<style scoped>
.local-sim-panel{margin:18px 20px;padding:18px 20px;border:1px solid #cad7e0;border-radius:12px;background:#fff;color:#263c4b;font-size:13px}
.local-sim-header{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center}
.local-sim-header h3{font-size:17px;margin:0 0 5px}.local-sim-header p{margin:0;color:#61707d;line-height:1.5}
.engine-chip{font-size:11px;background:#ebf3f6;color:#264c63;border-radius:12px;padding:6px 10px;font-weight:700}
.local-sim-info,.local-sim-error{margin:12px 0;padding:9px 10px;border-radius:7px;background:#fff6ef;color:#7e3b23}
.local-sim-controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:14px}
.local-sim-controls label{font-weight:600}
.local-sim-controls select,.local-sim-controls input{min-width:220px;max-width:100%;padding:9px 8px;border:1px solid #abbeca;border-radius:7px;background:#fff;color:#263c4b;flex:1}
.local-public-research{margin-top:14px;padding-top:10px;border-top:1px solid #dce4eb}
.local-sim-panel button{padding:9px 12px;border:0;border-radius:7px;background:#244e67;color:#fff;cursor:pointer}
.local-sim-panel button.secondary{background:#fff;color:#244e67;border:1px solid #9bb2c0}
.local-sim-panel button:disabled{opacity:.55;cursor:not-allowed}
.local-sim-note,.local-sim-warning{font-size:12px;line-height:1.5;margin:12px 0;color:#606f79}
.local-sim-warning{color:#895d1d}
.local-sim-results{margin-top:18px;border-top:1px solid #dae2e8;padding-top:13px}
.local-sim-status{display:flex;justify-content:space-between;gap:10px}
.local-sim-meter{height:8px;background:#e8edf2;border-radius:7px;overflow:hidden;margin:9px 0}
.local-sim-meter>div{height:100%;background:#427897;transition:width .2s}
.local-sim-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin:13px 0}
.local-sim-metrics>div{border:1px solid #dce4eb;border-radius:8px;padding:10px;display:flex;flex-direction:column;gap:5px}
.local-sim-metrics strong{font-size:18px}.local-sim-metrics span{font-size:11px;color:#697985}
.local-sim-actions{display:flex;align-items:center;flex-wrap:wrap;gap:9px}
.local-sim-download{padding:9px 12px;border-radius:7px;color:#244e67;text-decoration:underline}
.local-sim-history{max-height:360px;overflow-y:auto;margin-top:12px;border-top:1px solid #dce4eb}
.local-sim-decision{padding:8px 0;border-bottom:1px solid #ebeff2}.local-sim-decision p{margin:4px 0;line-height:1.45}
.local-sim-decision small{color:#63727e}
.local-sim-review{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
@media(max-width:680px){.local-sim-panel{margin:12px;padding:12px}.local-sim-controls{align-items:stretch;flex-direction:column}}
</style>
