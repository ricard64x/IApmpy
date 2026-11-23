<template>
  <section class="efficiency-panel" aria-label="Mediciones verificables de la simulación">
    <div class="efficiency-title">
      <div>
        <strong>Resultados medibles · eficiencia operativa</strong>
        <p>Registros de esta ejecución. Sin estimar precisión ni ahorros sin comparación.</p>
      </div>
      <a v-if="metrics" :href="downloadUrl" download>Exportar métricas JSON</a>
    </div>
    <p v-if="error" class="metrics-error" role="status">{{ error }}</p>
    <p v-else-if="!metrics || !hasEvidence" class="metrics-empty">
      Aún no hay llamadas registradas. Los indicadores aparecerán al ejecutar las primeras rondas.
    </p>
    <template v-else>
      <div class="efficiency-grid">
        <div><strong>{{ metrics.quality_structural.synthetic_conversation_replies || 0 }}</strong><span>Respuestas entre agentes sintéticos</span></div>
        <div><strong>{{ metrics.quality_structural.recorded_interaction_pairs || 0 }}</strong><span>Pares con destinatario explícito</span></div>
        <div><strong>{{ metrics.model.calls }}</strong><span>Llamadas registradas al modelo</span></div>
        <div><strong>{{ milliseconds(metrics.model.latency_p95_ms) }}</strong><span>Latencia p95 por lote</span></div>
        <div><strong>{{ megabytes(metrics.resource.peak_child_process_rss_mb) }}</strong><span>RAM pico del proceso</span></div>
        <div><strong>{{ percentage(metrics.quality_structural.profile_coverage_percent) }}</strong><span>Cobertura de participantes</span></div>
        <div><strong>{{ metrics.memory.queries }}</strong><span>Consultas a memoria</span></div>
        <div><strong>{{ metrics.memory.cache_hits }}</strong><span>Lecturas desde caché</span></div>
        <div><strong>{{ tokens }}</strong><span>Tokens medidos por proveedor</span></div>
        <div><strong>{{ cost }}</strong><span>Costo USD (tarifas configuradas)</span></div>
      </div>
      <small>Exactitud factual: <b>no evaluada</b>. Requiere casos de referencia independientes.
      El porcentaje de cobertura no demuestra que las decisiones sean correctas.</small>
    </template>
  </section>
</template>

<script setup>
import {computed, onMounted, onUnmounted, ref, watch} from 'vue'
import service from '../api'
const props = defineProps({simulationId:{type:String,required:true}})
const metrics = ref(null)
const error = ref('')
let timer = null
let busy = false
const downloadUrl = computed(() => '/api/simulation/' + encodeURIComponent(props.simulationId) + '/efficiency?download=1')
const hasEvidence = computed(() => !!metrics.value && (
  metrics.value.model.calls > 0 || metrics.value.quality_structural.synthetic_actions > 0
))
const tokens = computed(() => {
  const model = metrics.value?.model
  if (model?.input_tokens_actual == null || model?.output_tokens_actual == null) return 'Sin medición'
  return (model.input_tokens_actual + model.output_tokens_actual).toLocaleString('es-PY')
})
const cost = computed(() => {
  const value = metrics.value?.model?.cost_usd_actual_from_configured_prices
  return typeof value === 'number' ? '$ ' + value.toFixed(4) : 'No calculado'
})
const milliseconds = n => typeof n === 'number' ? n.toLocaleString('es-PY') + ' ms' : 'Sin datos'
const megabytes = n => typeof n === 'number' ? n.toLocaleString('es-PY') + ' MB' : 'Sin datos'
const percentage = n => typeof n === 'number' ? n.toFixed(1) + ' %' : 'No medido'
async function refresh() {
  if (!props.simulationId || busy || document.hidden) return
  busy = true
  try {
    const response = await service.get('/api/simulation/' +
      encodeURIComponent(props.simulationId) + '/efficiency')
    if (response.success) {
      metrics.value = response.data
      error.value = ''
    }
  } catch (_) {
    if (!metrics.value) error.value = 'Métricas todavía no disponibles.'
    // Conserve last observed values on a transient query failure.
  } finally { busy = false }
}
const onVisibility = () => { if (!document.hidden) refresh() }
watch(() => props.simulationId, refresh)
onMounted(() => {
  refresh()
  timer = setInterval(refresh, 20000)
  document.addEventListener('visibilitychange', onVisibility)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>
<style scoped>
.efficiency-panel{background:#f7fafb;border-bottom:1px solid #d5e6e9;padding:10px 18px;display:grid;gap:9px;font-size:11px}
.efficiency-title{display:flex;justify-content:space-between;align-items:start;gap:12px}
.efficiency-title strong{font-size:13px;color:#1b5267}
.efficiency-title p{font-size:10px;color:#557681;margin:2px 0}
.efficiency-title a{color:#146582;font-size:11px;text-decoration:underline;font-weight:650;white-space:nowrap}
.efficiency-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}
.efficiency-grid div{background:white;border:1px solid #dce9ed;border-radius:8px;padding:8px;display:grid;gap:3px}
.efficiency-grid strong{font-size:14px;color:#144d67;font-variant-numeric:tabular-nums}
.efficiency-grid span{font-size:10px;line-height:1.4;color:#607c87}
.efficiency-panel small,.metrics-empty,.metrics-error{font-size:10px;color:#59737b;line-height:1.5}
.metrics-error{color:#914c28}
@media(max-width:900px){.efficiency-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:520px){.efficiency-title{flex-wrap:wrap}.efficiency-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>