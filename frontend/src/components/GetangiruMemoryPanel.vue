<template>
  <section class="memory-panel" aria-label="Memoria contextual del proyecto">
    <header>
      <h3>Memoria contextual</h3>
      <p>Consultá referencias asociadas a este proyecto. El resultado no reemplaza las evidencias originales.</p>
    </header>
    <form class="memory-form" @submit.prevent="searchMemory">
      <label for="memory-query">Buscar en la memoria del proyecto</label>
      <div class="memory-controls">
        <input id="memory-query" v-model.trim="query" type="search"
          maxlength="200" autocomplete="off"
          placeholder="Ej.: controles de acceso o continuidad" />
        <button type="submit" :disabled="loading || query.length < 2">
          {{ loading ? 'Consultando…' : 'Consultar memoria' }}
        </button>
      </div>
    </form>
    <p v-if="error" class="memory-error" role="alert">{{ error }}</p>
    <p v-else-if="searched && !results.length" class="memory-empty" role="status">
      No se encontraron referencias para esta consulta.
    </p>
    <template v-else-if="results.length">
      <p class="memory-count" role="status">
        {{ results.length }} referencia(s) · consulta local, sin llamadas a IA externa
      </p>
      <ul class="memory-list">
        <li v-for="item in results" :key="item.episode_id">
          <small>Fuente: {{ item.source_id || 'Memoria del proyecto' }}</small>
          <p>{{ item.content }}</p>
        </li>
      </ul>
    </template>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import service from '../api/index'

const props = defineProps({ projectId: { type: String, required: true } })
const query = ref('')
const loading = ref(false)
const searched = ref(false)
const error = ref('')
const results = ref([])
let sequence = 0

watch(() => props.projectId, () => {
  sequence += 1
  loading.value = false
  searched.value = false
  results.value = []
  error.value = ''
})

async function searchMemory() {
  if (!props.projectId || query.value.length < 2 || loading.value) return
  const requestId = ++sequence
  loading.value = true
  error.value = ''
  try {
    const response = await service.get(
      `/api/getangiru/project/${encodeURIComponent(props.projectId)}/search`,
      { params: { q: query.value.slice(0, 200), limit: 4 }, timeout: 10000 }
    )
    if (requestId !== sequence) return
    results.value = Array.isArray(response.items) ? response.items : []
    searched.value = true
  } catch (e) {
    if (requestId !== sequence) return
    results.value = []
    searched.value = false
    error.value = e?.message || 'No se pudo consultar la memoria.'
  } finally {
    if (requestId === sequence) loading.value = false
  }
}
</script>

<style scoped>
.memory-panel{margin-top:18px;padding:18px;background:#fff;border:1px solid #d9e0e8;border-radius:12px;color:#17283a}
.memory-panel h3{font-size:16px;margin:0 0 6px;font-weight:650}
.memory-panel header p{font-size:13px;line-height:1.45;color:#536579;margin:0 0 14px}
.memory-form label{display:block;font-size:13px;font-weight:600;margin-bottom:7px}
.memory-controls{display:flex;gap:8px;flex-wrap:wrap}
.memory-controls input{flex:1;min-width:180px;border:1px solid #aab9c9;padding:9px 11px;border-radius:8px;font-size:14px}
.memory-controls button{border:0;background:#1a3f61;color:white;padding:9px 13px;border-radius:8px;cursor:pointer}
.memory-controls button:disabled{opacity:.45;cursor:not-allowed}
.memory-error{color:#9c2121}
.memory-count,.memory-empty{font-size:13px;color:#506070;margin:13px 0 0}
.memory-list{margin:11px 0 0;padding:0;list-style:none;max-height:320px;overflow:auto}
.memory-list li{padding:10px 0;border-top:1px solid #e8edf3}
.memory-list small{font-weight:600;color:#506070}
.memory-list p{font-size:13px;line-height:1.5;margin:5px 0;white-space:pre-wrap;overflow-wrap:anywhere}
@media(max-width:600px){.memory-controls button{width:100%}}
</style>
