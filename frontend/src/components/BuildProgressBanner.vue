<template>
  <section class="tracking-banner" :class="{ 'is-complete': isComplete, 'is-stale': stale }"
           role="status" aria-live="polite" aria-atomic="true">
    <div class="tracking-copy">
      <span class="tracking-kicker">
        <span class="tracking-dot" :class="{ 'is-stale': stale }"></span>
        {{ stateLabel }}
      </span>
      <strong v-if="knownTotal">{{ processed.toLocaleString('es-PY') }} de {{ total.toLocaleString('es-PY') }} fragmentos procesados</strong>
      <strong v-else>Preparando el procesamiento del conocimiento</strong>
      <p>{{ explanation }}</p>
    </div>
    <div class="tracking-result" v-if="knownTotal">
      <strong class="tracking-percent">{{ percent.toFixed(1) }} %</strong>
      <div class="tracking-bar" role="progressbar" :aria-valuenow="percent"
           aria-valuemin="0" aria-valuemax="100" :aria-label="'Fragmentos procesados: '+percent.toFixed(1)+' por ciento'">
        <div :style="{ width: percent + '%' }"></div>
      </div>
      <small>{{ remaining }} pendientes · {{ processing }} en curso · {{ failures }} fallidos</small>
    </div>
    <div class="tracking-last">
      <span>{{ refreshedAt ? 'Consultado ' + formattedTime : 'Consultando el avance…' }}</span>
      <span v-if="refreshedAt">Actualización automática cada 12 segundos</span>
      <span v-else>El trabajo continúa en el servidor</span>
      <div class="tracking-actions">
        <button type="button" @click="$emit('refresh')" :disabled="refreshing" class="tracking-refresh"
                aria-label="Consultar avance actualizado">↻ Actualizar</button>
        <button type="button" @click="$emit('go-projects')" class="tracking-refresh">Mis proyectos</button>
      </div>
    </div>
  </section>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({
  progress: { type: Object, default: null },
  refreshedAt: { type: Number, default: null },
  refreshing: { type: Boolean, default: false },
  stale: { type: Boolean, default: false },
})
defineEmits(['refresh', 'go-projects'])
const processed = computed(() => Math.max(0, Number(props.progress?.processed) || 0))
const total = computed(() => Math.max(0, Number(props.progress?.total) || 0))
const knownTotal = computed(() => total.value > 0)
const processing = computed(() => Math.max(0, Number(props.progress?.processing) || 0))
const failures = computed(() => Math.max(0, Number(props.progress?.failed) || 0))
const remaining = computed(() => Math.max(0, total.value - processed.value - processing.value - failures.value))
const percent = computed(() => knownTotal.value ? Math.min(100, 100 * processed.value / total.value) : 0)
const isComplete = computed(() => props.progress?.status === 'succeeded' || props.progress?.status === 'completed')
const stateLabel = computed(() => {
  if (props.stale) return 'No se pudo consultar el último avance'
  if (isComplete.value) return 'Procesamiento remoto terminado · verificando red'
  if (props.progress?.status === 'queued') return 'En cola de procesamiento'
  if (!knownTotal.value) return 'Preparando documentos'
  return 'Construcción en curso · avance verificado'
})
const explanation = computed(() => {
  if (props.stale) return 'El último avance conocido se conserva. El trabajo remoto puede continuar; consultá nuevamente.'
  if (isComplete.value) return 'Los fragmentos ya se procesaron. Se está verificando la red antes de habilitar la siguiente etapa.'
  return 'Podés cerrar esta pestaña y volver desde Mis proyectos. El procesamiento remoto no se detiene.'
})
const formattedTime = computed(() => props.refreshedAt
  ? new Date(props.refreshedAt).toLocaleTimeString('es-PY', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  : '')
</script>
<style scoped>
.tracking-banner{display:grid;grid-template-columns:minmax(260px,1fr) minmax(225px,360px) auto;gap:20px;align-items:center;padding:12px 24px;border-bottom:1px solid #bee3ed;background:#effafe;color:#174762;flex-shrink:0;position:relative;z-index:20}
.tracking-copy{display:grid;gap:4px;min-width:0}
.tracking-kicker{font-size:11px;letter-spacing:.02em;color:#0f7285;font-weight:800;display:flex;align-items:center;gap:8px}
.tracking-dot{width:8px;height:8px;background:#16a47f;box-shadow:0 0 0 4px #16a47f20;border-radius:50%;animation:pulse-progress 2s infinite}
.tracking-dot.is-stale{background:#c17b2a;box-shadow:none;animation:none}
.tracking-copy strong{font-size:15px;line-height:1.3}
.tracking-copy p{font-size:11px;line-height:1.5;color:#526b82;margin:0}
.tracking-result{display:grid;gap:5px;min-width:0}
.tracking-percent{font-size:20px;color:#095c80;font-variant-numeric:tabular-nums}
.tracking-bar{height:9px;width:100%;border-radius:20px;overflow:hidden;background:#d0e5ee}
.tracking-bar div{height:100%;border-radius:20px;background:linear-gradient(90deg,#0877b3,#14aa96);transition:width .6s ease}
.tracking-result small{font-size:10px;color:#526b82}
.tracking-last{display:flex;align-items:flex-start;flex-direction:column;gap:3px;color:#537189;font-size:10px;min-width:140px}
.tracking-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.tracking-refresh{margin-top:3px;border:1px solid #94d0e1;background:white;border-radius:8px;padding:5px 10px;color:#146a84;font-weight:750;cursor:pointer}
.tracking-refresh:disabled{opacity:.5;cursor:wait}
.is-complete{background:#ecfbf2;border-bottom-color:#bce5cb}
.is-stale{background:#fff8e9;border-bottom-color:#f0dbb4}
@keyframes pulse-progress{50%{opacity:.55}}
@media(max-width:900px){.tracking-banner{grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:12px 15px}.tracking-result{grid-column:1 / -1;grid-row:2}.tracking-last{font-size:9px}.tracking-copy strong{font-size:13px}.tracking-copy p{font-size:10px}}
@media(max-width:520px){.tracking-banner{grid-template-columns:1fr}.tracking-last{grid-row:3;flex-direction:row;align-items:center;flex-wrap:wrap}.tracking-result{grid-row:2}.tracking-refresh{margin-top:0}}
</style>
