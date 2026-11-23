<template>
  <TenonderaShell title="Historial de simulaciones" subtitle="Consultá todos los análisis anteriores, sus reportes y las nuevas versiones." section="HISTORIAL Y REPORTES">
    <section class="history-page">
      <div class="tools">
        <input v-model.trim="filter" aria-label="Buscar proyectos" placeholder="Buscar por nombre, fecha o identificador" />
        <button :disabled="loading" @click="load">{{ loading ? 'Actualizando…' : 'Actualizar' }}</button>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p class="muted">Cada ejecución y reporte es independiente. Las versiones anteriores nunca se reemplazan.</p>
      <article v-for="project in filtered" :key="project.project_id" class="project">
        <header class="project-head">
          <div><h2>{{ friendlyProjectName(project.name,project.simulation_requirement,project.project_id) }}</h2>
            <small>{{ project.project_id }} · {{ shortDate(project.created_at) }}</small></div>
          <button class="secondary" @click="router.push('/process/'+project.project_id)">Abrir proyecto</button>
        </header>
        <p class="description">{{ project.simulation_requirement }}</p>
        <p v-if="busyProject === project.project_id" class="muted">Consultando historial…</p>
        <p v-if="loadErrors[project.project_id]" class="error">{{ loadErrors[project.project_id] }}</p>
        <div v-if="entries(project.project_id).length" class="runs">
          <div v-for="(run,index) in entries(project.project_id)" :key="run.simulation_id" class="run">
            <div class="run-title">
              <strong>{{ run.native ? 'Simulación local' : 'Simulación' }} · Versión {{ entries(project.project_id).length-index }}</strong>
              <span>{{ state(run) }} · {{ shortDate(run.started_at || run.created_at) }}</span>
            </div>
            <small>{{ run.simulation_id }}</small>
            <small v-if="run.parent_run_id">Basada en {{ run.parent_run_id }}</small>
            <p v-if="run.instructions"><strong>Nueva indicación:</strong> {{ run.instructions }}</p>
            <div class="actions">
              <button class="secondary" v-if="run.native" @click="selectNative(run)">Consultar resultado</button>
              <button class="secondary" v-else @click="router.push('/simulation/'+run.simulation_id)">Consultar simulación</button>
              <button v-if="run.report_id" @click="router.push('/report/'+run.report_id)">Ver reporte</button>
              <a v-if="run.native && run.report" :href="'/api/native-simulation/'+encodeURIComponent(run.simulation_id)+'/report.md'">Exportar informe</a>
              <button v-if="run.native && ['completed','failed','interrupted'].includes(run.status)" @click="selectFollowup(run)">Complementar con nueva simulación</button>
            </div>
          </div>
        </div>
        <p v-else-if="busyProject !== project.project_id" class="muted">No hay ejecuciones registradas para este proyecto.</p>
      </article>
      <p v-if="!filtered.length && !loading" class="muted">No se encontraron proyectos.</p>
      <div v-if="selected" class="overlay" @click.self="selected=null">
        <section class="dialog" role="dialog" aria-modal="true" aria-label="Detalle de simulación">
          <button class="close" @click="selected=null">Cerrar ×</button>
          <h2>{{ followup ? 'Nueva simulación basada en el histórico' : 'Resultado guardado' }}</h2>
          <p class="muted">{{ selected.simulation_id }}</p>
          <template v-if="followup">
            <p>Se conservará la versión anterior. El motor reutilizará el grafo y las revisiones humanas disponibles del proyecto; las indicaciones serán una nueva hipótesis, no evidencia nueva.</p>
            <label for="followup-note">¿Qué querés ampliar, contrastar o simular ahora?</label>
            <textarea id="followup-note" v-model="instructions" maxlength="1200" rows="5" placeholder="Ej.: Simular una nueva alerta, revisar la contención y comparar las decisiones con el escenario anterior."></textarea>
            <label for="followup-mode">Modo de ejecución</label>
            <select id="followup-mode" v-model="mode"><option value="rules">Reglas locales rápidas</option><option value="hybrid">IA local + reglas</option></select>
            <button :disabled="submitting || !instructions.trim()" @click="startFollowup">{{ submitting ? 'Iniciando…' : 'Crear nueva versión' }}</button>
          </template>
          <template v-else>
            <p><strong>Estado:</strong> {{ state(selected) }}</p>
            <p><strong>Escenario:</strong> {{ selected.report?.scenario_goal || 'Resultado todavía no disponible' }}</p>
            <p v-if="selected.report"><strong>Decisiones simuladas:</strong> {{ selected.report.actions }} · <strong>Cobertura de evidencias:</strong> {{ selected.report.evidence_coverage_pct }}%</p>
            <p v-if="selected.instructions"><strong>Indicaciones de la versión:</strong> {{ selected.instructions }}</p>
            <a v-if="selected.report" :href="'/api/native-simulation/'+encodeURIComponent(selected.simulation_id)+'/report.md'">Descargar informe guardado (.md)</a>
          </template>
          <p v-if="dialogError" class="error" role="alert">{{ dialogError }}</p>
        </section>
      </div>
    </section>
  </TenonderaShell>
</template>
<script setup>
import {computed,ref,onMounted} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import service from '../api'
import TenonderaShell from '../components/TenonderaShell.vue'
import {friendlyProjectName} from '../utils/projectHistory'
const route=useRoute(),router=useRouter()
const projects=ref([]),legacy=ref([]),native=ref({}),filter=ref(''),loading=ref(false)
const busyProject=ref(null),loadErrors=ref({}),error=ref('')
const selected=ref(null),followup=ref(false),instructions=ref(''),mode=ref('rules'),submitting=ref(false),dialogError=ref('')
const shortDate=value=>value ? new Date(value).toLocaleString('es-PY') : 'Sin fecha'
const state=run=>run.native ? ({completed:'Completada',running:'En curso',queued:'En cola',failed:'Fallida',interrupted:'Interrumpida'}[run.status]||run.status) : ({completed:'Completada',running:'En curso',failed:'Fallida'}[run.runner_status] || run.runner_status || 'Preparada')
const entries=id=>[...(native.value[id]||[]).map(x=>({...x,native:true})),...legacy.value.filter(x=>x.project_id===id).map(x=>({...x,native:false}))].sort((a,b)=>String(b.started_at||b.created_at||'').localeCompare(String(a.started_at||a.created_at||'')))
const filtered=computed(()=>projects.value.filter(p=>{
  const needle=filter.value.toLowerCase()
  return !needle || [p.name,p.project_id,p.created_at,p.simulation_requirement].some(x=>String(x||'').toLowerCase().includes(needle))
}))
async function load() {
  loading.value=true;error.value=''
  const results=await Promise.allSettled([
    service.get('/api/graph/project/list',{params:{limit:1000}}),
    service.get('/api/simulation/history',{params:{limit:1000}})
  ])
  if(results[0].status==='fulfilled')projects.value=results[0].value.data||[]
  else error.value='No se pudo leer el inventario de proyectos.'
  if(results[1].status==='fulfilled')legacy.value=results[1].value.data||[]
  else error.value+=' Algunas ejecuciones históricas no están disponibles.'
  if(results[0].status==='fulfilled'){
    await Promise.all(projects.value.map(async p=>{
      try {const response=await service.get('/api/native-simulation/project/'+encodeURIComponent(p.project_id)+'/history')
        native.value={...native.value,[p.project_id]:response.data||[]}
      }catch(e){loadErrors.value={...loadErrors.value,[p.project_id]:'No se pudo consultar el historial local de este proyecto.'}}
    }))
  }
  if(route.query.project)filter.value=String(route.query.project)
  loading.value=false
}
async function selectNative(run) {
  dialogError.value='';followup.value=false
  try {const response=await service.get('/api/native-simulation/'+encodeURIComponent(run.simulation_id));selected.value={...response.data,native:true}}
  catch(e){error.value=e.message||'No se pudo consultar la ejecución'}
}
function selectFollowup(run) {selected.value=run;followup.value=true;instructions.value='';dialogError.value='';mode.value='rules'}
async function startFollowup() {
  if(!selected.value || submitting.value || !instructions.value.trim())return
  submitting.value=true;dialogError.value=''
  try {
    const p=selected.value.project_id
    await service.post('/api/native-simulation/start',{
      project_id:p,parent_run_id:selected.value.simulation_id,instructions:instructions.value.trim(),mode:mode.value
    })
    selected.value=null
    await load()
  } catch(e){dialogError.value=e.message||'No se pudo crear la versión'}
  finally{submitting.value=false}
}
onMounted(load)
</script>
<style scoped>
.history-page{max-width:1250px;margin:auto;min-width:0}
.tools{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 16px}.tools input{flex:1;min-width:min(100%,240px);border:1px solid #b8cedd;border-radius:10px;padding:12px}
button{border:0;border-radius:9px;padding:10px 14px;background:#087f9c;color:white;cursor:pointer;font-weight:650}
button:disabled{opacity:.55;cursor:not-allowed}
button.secondary{background:#f0f7fc;color:#15516c;border:1px solid #bfd7e4}
.muted{font-size:13px;color:#6c8094;line-height:1.5;margin:12px 0}
.error{color:#b32039;font-size:13px;line-height:1.5}
.project{background:#fff;border:1px solid #dbe8ef;border-radius:15px;padding:clamp(14px,2.4vw,23px);margin:14px 0;min-width:0;overflow-wrap:anywhere}
.project-head{display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:12px}
.project h2{font-size:18px;margin:0 0 5px}.project small{font-size:11px;color:#697f95}
.description{font-size:13px;margin:13px 0;color:#3d5970;white-space:pre-wrap}
.runs{display:grid;gap:10px;margin-top:14px}
.run{border:1px solid #e0eaf1;background:#f9fcff;border-radius:12px;padding:13px;min-width:0}
.run-title{display:flex;align-items:center;flex-wrap:wrap;gap:8px;justify-content:space-between;font-size:13px}
.run-title span{color:#47718a}.run small{display:block;margin:6px 0}
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:10px}.actions a,.dialog a{color:#12639a;font-size:13px;overflow-wrap:anywhere}
.overlay{position:fixed;inset:0;background:#0c24477d;z-index:100;display:grid;place-items:center;padding:12px}
.dialog{position:relative;background:#fff;border-radius:16px;padding:clamp(16px,3vw,28px);width:min(100%,660px);max-height:90vh;overflow:auto;display:grid;gap:12px}
.dialog h2{font-size:20px}.dialog p{line-height:1.5;font-size:13px}.dialog label{font-size:13px;font-weight:700}
.dialog textarea,.dialog select{width:100%;max-width:100%;border:1px solid #b8cedd;border-radius:9px;padding:10px;font:inherit}
.dialog .close{justify-self:end;background:transparent;color:#164c6c}
</style>