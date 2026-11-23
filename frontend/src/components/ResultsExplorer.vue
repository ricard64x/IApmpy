<template>
  <section class="results-hub" aria-label="Centro de resultados de la simulación">
    <div class="hub-heading">
      <div>
        <span class="eyebrow">RESULTADOS EXPLICADOS</span>
        <h2>Entendé lo que ocurrió en la simulación</h2>
        <p>Datos observados en los registros. Explorá participantes, respuestas y evolución sin interpretar hipótesis como hechos reales.</p>
      </div>
      <button class="refresh" type="button" :disabled="loading" @click="load">
        {{ loading ? 'Actualizando…' : '↻ Actualizar datos' }}
      </button>
    </div>

    <div v-if="error" class="error" role="alert">
      {{ error }} <button type="button" @click="load">Reintentar</button>
    </div>
    <p v-else-if="loading && !data" class="loading" role="status">Leyendo las acciones registradas…</p>
    <p v-else-if="!data" class="loading">Todavía no hay métricas disponibles.</p>

    <template v-if="data">
      <section class="status-banner" :class="statusClass" role="status">
        <span class="status-mark" aria-hidden="true">{{ statusIcon }}</span>
        <div>
          <strong>{{ qualityLabel }}</strong>
          <p>{{ qualityExplanation }}</p>
          <p v-if="qualityIssues.length" class="issues">{{ qualityIssues.join(' ') }}</p>
        </div>
      </section>

      <div class="number-grid">
        <div class="number-card"><strong>{{ number(data.active_participants) }}</strong><span>Participantes activos</span><small>{{ data.population?.selected_participants!=null ? 'De '+number(data.population.selected_participants)+' perfiles seleccionados' : 'Personajes con al menos una acción guardada' }}.</small></div>
        <div class="number-card"><strong>{{ number(data.message_actions) }}</strong><span>Mensajes registrados</span><small>Publicaciones y respuestas; no son mensajes reales.</small></div>
        <div class="number-card"><strong>{{ number(data.cross_agent_messages || 0) }}</strong><span>Respuestas entre perfiles</span><small>Mensajes dirigidos a otro participante identificable.</small></div>
        <div class="number-card"><strong>{{ number(data.recorded_interaction_pairs || 0) }}</strong><span>Relaciones dirigidas</span><small>Pares emisor → destinatario con evidencia.</small></div>
      </div>

      <p v-if="data.population?.synthetic_additions > 0" class="population-note">
        De los {{ number(data.population.selected_participants) }} perfiles configurados,
        {{ number(data.population.synthetic_additions) }} son roles hipotéticos adicionales solicitados para el escenario.
        No fueron detectados en el grafo ni representan personas reales.
      </p>
      <div class="hub-tabs" role="tablist" aria-label="Explorar resultados">
        <button v-for="item in tabs" :key="item.id" type="button" role="tab"
          :aria-selected="tab===item.id" :class="{active:tab===item.id}"
          @click="tab=item.id">{{ item.icon }} {{ item.label }}</button>
      </div>

      <div v-if="tab==='overview'" class="hub-content">
        <article class="insight-panel">
          <h3>Lo esencial, en pocas palabras</h3>
          <p>{{ executiveSummary }}</p>
          <div class="highlights">
            <div><span>Actividad total</span><strong>{{ number(data.total_actions) }} acciones</strong>
              <small>Incluye acciones distintas de mensajes.</small></div>
            <div><span>Concentración de actividad</span><strong>{{ concentrationLabel }}</strong>
              <small>Máxima participación de una sola voz: {{ percent(concentration) }}.</small></div>
            <div><span>Evidencia de diálogo</span><strong>{{ conversationLabel }}</strong>
              <small>Medida por destinatarios explícitos, no por texto parecido a respuestas.</small></div>
          </div>
        </article>
        <div class="two">
          <article class="panel">
            <div class="panel-heading">
              <h3>Quién concentró la actividad</h3>
              <small>Proporción de las acciones registradas por agente.</small>
            </div>
            <div v-if="people.length" class="share-summary">
              <div class="donut" :style="donutStyle" role="img"
                :aria-label="topPerson.name+' tiene '+percent(topShare)+' de las acciones'">
                <span><strong>{{ percent(topShare) }}</strong><small>participante principal</small></span>
              </div>
              <div class="ranking">
                <button v-for="p in people.slice(0,5)" :key="p.id" type="button"
                  @click="showParticipant(p.id)" :title="'Ver mensajes de '+p.name">
                  <span class="dot" :style="{background:personColor(p.id)}"></span>
                  <span class="name">{{ p.name }}</span>
                  <strong>{{ percent(share(p)) }}</strong>
                </button>
              </div>
            </div>
            <p v-else class="empty">No hay actividad individual para mostrar.</p>
          </article>
          <article class="panel">
            <div class="panel-heading"><h3>Evolución de la conversación</h3><small>Cada barra representa acciones guardadas en una ronda.</small></div>
            <div v-if="rounds.length" class="chart-rows">
              <button type="button" v-for="r in rounds.slice(0,12)" :key="r.round"
                @click="showRound(r.round)">
                <span>Ronda {{ r.round }}</span>
                <span class="bar-track"><i :style="{width:barWidth(r.count,rounds)+'%'}"></i></span>
                <strong>{{ r.count }}</strong>
              </button>
            </div>
            <p v-else class="empty">No se registraron rondas.</p>
            <p class="hint">Seleccioná una barra para revisar las intervenciones de esa ronda.</p>
          </article>
        </div>
        <div class="two">
          <article class="panel">
            <h3>Interacciones que sí quedaron registradas</h3>
            <p class="helper">Las flechas muestran a quién respondió cada personaje; no representan relaciones reales.</p>
            <div v-if="data.interactions?.length" class="edges">
              <button v-for="(edge,i) in data.interactions.slice(0,8)" :key="i" type="button"
                @click="showParticipant(edge.from)">
                <span>{{ agentName(edge.from) }} <b aria-label="respondió a">→</b> {{ agentName(edge.to) }}</span>
                <strong>{{ edge.count }} {{ edge.count===1?'respuesta':'respuestas' }}</strong>
              </button>
            </div>
            <p v-else class="empty">No se encontraron respuestas con destinatario verificable.</p>
          </article>
          <article class="panel">
            <h3>¿Qué significan estos resultados?</h3>
            <dl class="glossary">
              <dt>Participante activo</dt><dd>Perfil que efectivamente realizó acciones, no solo un perfil creado.</dd>
              <dt>Respuesta cruzada</dt><dd>Acción dirigida de un perfil a otro en el mismo espacio.</dd>
              <dt>Calidad estructural</dt><dd>Comprobación de diversidad y vínculos; no mide verdad, representatividad ni precisión.</dd>
              <dt>Fecha de ejecución</dt><dd>Cuándo se guardó el evento; no corresponde necesariamente a la cronología imaginaria.</dd>
            </dl>
          </article>
        </div>
      </div>

      <div v-else-if="tab==='people'" class="hub-content">
        <div class="panel-heading"><h3>Participantes y niveles de actividad</h3>
          <small>Compará cuánto intervino cada perfil. Seleccioná un nombre para explorar sus mensajes.</small>
        </div>
        <p v-if="!people.length" class="empty">No se encontraron participantes con acciones.</p>
        <div v-else class="people-list">
          <button type="button" v-for="p in people" :key="p.id" @click="showParticipant(p.id)">
            <span class="avatar">{{ p.name?.charAt(0) || 'P' }}</span>
            <span class="person-text"><strong>{{ p.name }}</strong><small>Perfil {{ p.id }} · {{ p.messages }} mensajes · {{ p.actions }} acciones</small></span>
            <span class="person-bar"><i :style="{width:share(p)+'%',background:personColor(p.id)}"></i></span>
            <b>{{ percent(share(p)) }}</b>
          </button>
        </div>
      </div>

      <div v-else-if="tab==='talk'" class="hub-content">
        <div class="panel-heading"><h3>Explorador de conversaciones</h3>
          <small>Buscá palabras y filtrá por perfil, ronda o plataforma. Las respuestas enlazadas indican su destinatario.</small>
        </div>
        <div class="filters">
          <label>Buscar en los mensajes
            <input v-model="search" type="search" placeholder="Ej.: presupuesto, costo, proveedor">
          </label>
          <label>Participante
            <select v-model="selectedPerson"><option value="all">Todos</option><option v-for="p in people" :key="p.id" :value="p.id">{{ p.name }}</option></select>
          </label>
          <label>Ronda
            <select v-model="selectedRound"><option value="all">Todas</option><option v-for="r in rounds" :key="r.round" :value="String(r.round)">Ronda {{ r.round }}</option></select>
          </label>
          <label>Espacio
            <select v-model="selectedPlatform"><option value="all">Todos</option><option v-for="p in platforms" :key="p.platform" :value="p.platform">{{ platformLabel(p.platform) }}</option></select>
          </label>
        </div>
        <div class="filter-summary">
          <span>{{ filteredMessages.length }} intervenciones en la muestra</span>
          <button type="button" @click="clearFilters">Limpiar filtros</button>
        </div>
        <p v-if="data.messages_sample_truncated" class="sample-warning">
          Vista limitada a {{ data.messages_sample_limit }} intervenciones; los totales superiores se calculan sobre más registros. La búsqueda solo consulta esta muestra.
        </p>
        <div v-if="filteredMessages.length" class="conversation-list">
          <article v-for="(m,i) in filteredMessages.slice(0,displayLimit)" :key="i" class="conversation-card">
            <header><span class="avatar small">{{ m.participant?.charAt(0) || 'P' }}</span>
              <strong>{{ m.participant }}</strong>
              <span class="pill">{{ platformLabel(m.platform) }}</span>
              <span class="pill">Ronda {{ m.round ?? '—' }}</span></header>
            <p v-if="m.target_id!=null" class="reply-label">↳ Responde a <strong>{{ agentName(m.target_id) }}</strong></p>
            <p class="excerpt">{{ m.excerpt }}</p>
            <footer>{{ messageType(m.type) }} · {{ m.timestamp ? formatDate(m.timestamp) : 'Sin fecha registrada' }}
              <span v-if="m.synthetic">· Contenido sintético</span></footer>
          </article>
          <button v-if="filteredMessages.length>displayLimit" class="more" type="button" @click="displayLimit+=25">
            Ver 25 intervenciones más
          </button>
        </div>
        <p v-else class="empty">No hay intervenciones que coincidan con los filtros.</p>
      </div>

      <div v-else-if="tab==='activity'" class="hub-content">
        <div class="two">
          <article class="panel"><h3>Acciones por día</h3><p class="helper">Fechas de almacenamiento, no fechas ficticias.</p>
            <div class="chart-rows"><div v-for="r in data.by_day||[]" :key="r.date" class="chart-row">
              <span>{{ r.date }}</span><span class="bar-track"><i :style="{width:barWidth(r.count,data.by_day)+'%'}"></i></span><strong>{{ r.count }}</strong>
            </div></div><p v-if="!data.by_day?.length" class="empty">Sin fechas válidas.</p>
          </article>
          <article class="panel"><h3>Tipos de acciones</h3><p class="helper">Distingue publicaciones, comentarios y demás actividad.</p>
            <div class="chart-rows"><div v-for="r in data.by_type||[]" :key="r.type" class="chart-row">
              <span>{{ messageType(r.type) }}</span><span class="bar-track"><i :style="{width:barWidth(r.count,data.by_type)+'%'}"></i></span><strong>{{ r.count }}</strong>
            </div></div><p v-if="!data.by_type?.length" class="empty">No hay acciones.</p>
          </article>
        </div>
        <article class="panel"><h3>Histograma horario</h3><p class="helper">Distribución de los eventos por hora de ejecución (UTC del registro).</p>
          <div class="hour-chart" role="img" aria-label="Número de acciones registradas en cada hora">
            <div v-for="r in data.by_hour||[]" :key="r.hour" :title="r.hour+':00 — '+r.count+' acciones'">
              <span :style="{height:Math.max(2,barWidth(r.count,data.by_hour))+'%'}"></span>
              <small v-if="Number(r.hour)%4===0">{{ r.hour }}h</small>
            </div>
          </div>
        </article>
        <article class="panel">
          <h3>Canales de actividad</h3>
          <div class="chart-rows"><div v-for="r in data.by_platform||[]" :key="r.platform" class="chart-row">
            <span>{{ platformLabel(r.platform) }}</span><span class="bar-track"><i :style="{width:barWidth(r.count,data.by_platform)+'%'}"></i></span><strong>{{ r.count }}</strong>
          </div></div>
        </article>
      </div>

      <div class="explore-next">
        <div>
          <strong>Preguntá sobre estos resultados</strong>
          <p>Podés pedir un resumen, contrastar perfiles o investigar la concentración de actividad. Las respuestas del asistente son interpretaciones y se guardan separadas de la simulación.</p>
        </div>
        <div class="question-actions">
          <button type="button" :disabled="!reportId" @click="ask('Explicá los indicadores de participación e interacción de esta simulación y sus límites, sin inventar datos.')">Explicame las métricas</button>
          <button type="button" :disabled="!reportId" @click="ask('¿Qué participantes intervinieron más y cuáles menos? Usá solo evidencia del informe y advertí cualquier falta de datos.')">Comparar perfiles</button>
          <button type="button" :disabled="!reportId" @click="ask('¿Qué conclusiones están respaldadas por eventos de la simulación y cuáles son solo hipótesis?')">Evaluar evidencia</button>
        </div>
        <small v-if="!reportId">Las consultas están disponibles desde un informe guardado.</small>
      </div>
      <p class="provenance">Origen: {{ data.source }}. {{ data.metric_basis }}.
        Registros leídos hasta {{ data.last_event ? formatDate(data.last_event) : 'fecha no disponible' }}.
        <strong> No es una encuesta ni una predicción del comportamiento de personas reales.</strong></p>
      <div v-if="data.followups?.available" class="after-report">
        Después del informe se registraron {{ data.followups.chat_turns }} turnos de consulta y
        {{ data.followups.surveys }} encuestas sintéticas adicionales. Se contabilizan por separado.
      </div>
    </template>
  </section>
</template>

<script setup>
import {ref,computed,watch} from 'vue'
import {useRouter} from 'vue-router'
import service from '../api'

const props=defineProps({
  reportId:{type:String,default:''},
  nativeRunId:{type:String,default:''}
})
const emit=defineEmits(['quality-updated'])
const router=useRouter()
const data=ref(null)
const loading=ref(false)
const error=ref('')
const tab=ref('overview')
const search=ref('')
const selectedPerson=ref('all')
const selectedRound=ref('all')
const selectedPlatform=ref('all')
const displayLimit=ref(25)
const tabs=[
  {id:'overview',label:'Resumen',icon:'◈'},
  {id:'people',label:'Participantes',icon:'♙'},
  {id:'talk',label:'Conversaciones',icon:'▤'},
  {id:'activity',label:'Actividad',icon:'▥'}
]
const number=value=>Number(value||0).toLocaleString('es-PY')
const percent=value=>Number(value||0).toLocaleString('es-PY',{maximumFractionDigits:1})+' %'
const people=computed(()=>data.value?.participants||[])
const rounds=computed(()=>data.value?.by_round||[])
const platforms=computed(()=>data.value?.by_platform||[])
const quality=computed(()=>data.value?.interaction_quality||{})
const qualityIssues=computed(()=>quality.value.issues||[])
const concentration=computed(()=>Number(quality.value.maximum_action_share_percent||0))
const topPerson=computed(()=>people.value[0]||{id:'',name:'Ninguno',actions:0})
const share=p=>data.value?.total_actions ? Number(p.actions||0)*100/data.value.total_actions:0
const topShare=computed(()=>share(topPerson.value))
const palette=['#0e789a','#19a6a2','#6f69bd','#e68d4d','#87ad65','#a86ba5']
const personColor=id=>palette[(Math.abs(Number(id))||0)%palette.length]
const donutStyle=computed(()=>{
  const v=Math.min(100,Math.max(0,topShare.value))
  return {background:`conic-gradient(#0e789a 0% ${v}%, #e6eef5 ${v}% 100%)`}
})
const barWidth=(value,values)=>{
  const max=Math.max(1,...(values||[]).map(x=>Number(x.count)||0))
  return Math.min(100,100*(Number(value)||0)/max)
}
const qualityLabel=computed(()=>quality.value.label||'Calidad aún no evaluada')
const statusClass=computed(()=>{
  if(quality.value.status==='good'||quality.value.status==='acceptable')return 'status-good'
  if(quality.value.status==='not_applicable')return 'status-neutral'
  return 'status-warning'
})
const statusIcon=computed(()=>statusClass.value==='status-good'?'✓':statusClass.value==='status-neutral'?'i':'!')
const qualityExplanation=computed(()=>{
  if(quality.value.status==='not_applicable')return 'Esta actividad contiene decisiones simuladas, no conversaciones entre personas.'
  if(quality.value.valid_multiagent_interaction)return 'Los registros permiten comprobar diversidad mínima y respuestas dirigidas entre perfiles ficticios.'
  if(quality.value.status==='insufficient')return 'La ejecución puede estar terminada, pero no cumple la evidencia mínima de una conversación entre varios perfiles.'
  return 'No hay datos completos suficientes para certificar la interacción.'
})
const concentrationLabel=computed(()=>concentration.value>=80?'Muy alta':concentration.value>60?'Alta':'Distribuida')
const conversationLabel=computed(()=>data.value?.cross_agent_messages>=2?'Respuestas verificadas':'Sin evidencia suficiente')
const executiveSummary=computed(()=>{
  if(!data.value)return ''
  const n=data.value
  const intro=`Se registraron ${number(n.total_actions)} acciones de ${number(n.active_participants)} personajes simulados; ${number(n.message_actions)} fueron mensajes.`
  if(quality.value.status==='not_applicable')return intro+' Es un ejercicio de decisiones, no un diálogo social.'
  if(quality.value.valid_multiagent_interaction)return intro+` Hubo ${number(n.cross_agent_messages)} respuestas dirigidas y ${number(n.recorded_interaction_pairs)} relaciones explícitas. Esto acredita interacción estructural, no representatividad de opiniones.`
  return intro+' No hay suficientes vínculos entre perfiles para considerarlo un diálogo multiagente válido. Las conclusiones deben leerse con esa advertencia.'
})
const agentName=id=>people.value.find(p=>String(p.id)===String(id))?.name||'Perfil '+String(id)
const messageType=t=>({
  CREATE_POST:'Publicación',POST:'Publicación',CREATE_COMMENT:'Respuesta',COMMENT:'Comentario',
  REPLY:'Respuesta',REPLY_POST:'Respuesta',LIKE_POST:'Me gusta',DECISION:'Decisión simulada'
})[t]||String(t||'Acción').replaceAll('_',' ').toLowerCase()
const platformLabel=t=>({twitter:'Plaza',reddit:'Comunidad',oasis:'Simulación',getangiru:'Decisiones simuladas'})[t]||t||'Espacio'
const formatDate=value=>{
  if(!value)return 'Sin fecha'
  const date=new Date(value)
  return Number.isNaN(date.getTime())?String(value):date.toLocaleString('es-PY')
}
const filteredMessages=computed(()=>(data.value?.messages||[]).filter(m=>{
  if(selectedPerson.value!=='all'&&String(m.participant_id)!==String(selectedPerson.value))return false
  if(selectedRound.value!=='all'&&String(m.round)!==String(selectedRound.value))return false
  if(selectedPlatform.value!=='all'&&m.platform!==selectedPlatform.value)return false
  if(search.value.trim()){
    const q=search.value.toLocaleLowerCase().trim()
    return (m.excerpt+' '+m.participant+' '+agentName(m.target_id)).toLocaleLowerCase().includes(q)
  }
  return true
}))
const clearFilters=()=>{
  search.value='';selectedPerson.value='all';selectedRound.value='all';selectedPlatform.value='all';displayLimit.value=25
}
const showParticipant=id=>{
  clearFilters();selectedPerson.value=String(id);tab.value='talk'
}
const showRound=round=>{
  clearFilters();selectedRound.value=String(round);tab.value='talk'
}
const ask=question=>{
  if(!props.reportId)return
  router.push({name:'Interaction',params:{reportId:props.reportId},query:{pregunta:question}})
}
async function load(){
  const id=props.nativeRunId||props.reportId
  if(!id)return
  loading.value=true;error.value=''
  try{
    const path=props.nativeRunId
      ?'/api/native-simulation/'+encodeURIComponent(id)+'/metrics'
      :'/api/report/'+encodeURIComponent(id)+'/metrics'
    const response=await service.get(path)
    if(!response.success||!response.data)throw Error(response.error||'Sin datos.')
    data.value=response.data
    emit('quality-updated',data.value.interaction_quality||null)
  }catch(e){error.value='No se pudieron leer las métricas: '+(e.message||'Error de conexión')}
  finally{loading.value=false}
}
watch(()=>[props.reportId,props.nativeRunId],()=>{data.value=null;tab.value='overview';clearFilters();load()},{immediate:true})
</script>

<style scoped>
.results-hub{font-family:inherit;border:1px solid #d6e2ed;background:#fff;border-radius:16px;padding:clamp(14px,2.5vw,24px);margin:20px 0;color:#193451;box-shadow:0 2px 14px rgba(20,48,80,.04)}
*{box-sizing:border-box}
.hub-heading{display:flex;justify-content:space-between;align-items:start;gap:14px;flex-wrap:wrap}
.eyebrow{font-size:10px;letter-spacing:1.3px;font-weight:800;color:#147891}
.hub-heading h2{font-size:clamp(19px,2vw,25px);margin:7px 0;line-height:1.25;letter-spacing:-.4px}
.hub-heading p{font-size:12px;color:#60738a;line-height:1.6;max-width:580px;margin:0}
button{font:inherit;cursor:pointer}
button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid #087caa;outline-offset:2px}
.refresh{border:1px solid #bed3e2;background:#eef6fb;color:#175675;border-radius:9px;padding:9px 12px;font-size:12px;font-weight:700}
.status-banner{display:flex;align-items:start;gap:13px;padding:14px;border-radius:11px;margin:18px 0 15px;border:1px solid #d5e2eb;background:#eff5fa}
.status-banner.status-good{border-color:#a2d1bd;background:#edf8f1}
.status-banner.status-warning{border-color:#ecbd94;background:#fff7ec}
.status-banner.status-neutral{border-color:#c7d6e3;background:#f4f7fa}
.status-mark{display:grid;place-items:center;min-width:27px;height:27px;border-radius:50%;background:#2f729a;color:white;font-weight:800}
.status-warning .status-mark{background:#a45f24}
.status-good .status-mark{background:#24805b}
.status-banner strong{font-size:14px}.status-banner p{font-size:12px;line-height:1.5;margin:5px 0 0}
.status-banner .issues{color:#9b4e27}
.number-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:15px 0}
.number-card{padding:14px 12px;background:#f0f7fa;border:1px solid #e1edf3;border-radius:11px;display:grid;gap:4px}
.number-card strong{font-size:27px;font-variant-numeric:tabular-nums;line-height:1.15}
.number-card span{font-size:12px;font-weight:750}.number-card small{font-size:10px;color:#5c7289;line-height:1.5}
.hub-tabs{display:flex;gap:6px;flex-wrap:wrap;border-bottom:1px solid #dce7ed;padding:5px 0 10px;margin:14px 0}
.hub-tabs button{border:1px solid transparent;background:transparent;color:#5a7288;border-radius:8px;padding:9px 12px;font-size:12px;font-weight:750}
.hub-tabs button:hover{background:#f4f9fc}
.hub-tabs button.active{background:#145b7d;color:#fff}
.hub-content{display:grid;gap:15px;margin:15px 0}
.insight-panel{padding:16px;background:#f8fafc;border:1px solid #dbe5ef;border-radius:12px}
.insight-panel h3,.panel h3{font-size:15px;margin:0 0 8px}.insight-panel>p,.helper,.hint{font-size:12px;color:#526b81;line-height:1.6;margin:4px 0 12px}
.highlights{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:12px}
.highlights>div{border-top:2px solid #d9e8f0;padding:10px 4px;display:grid;gap:4px}
.highlights span{font-size:10px;color:#62778a}.highlights strong{font-size:13px}.highlights small{font-size:10px;color:#63788c;line-height:1.45}
.two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.panel{background:#fff;border:1px solid #dce6ed;border-radius:12px;padding:16px;min-width:0}
.panel-heading{margin-bottom:12px}.panel-heading h3{font-size:15px;margin:0 0 5px}
.panel-heading small{font-size:11px;color:#6b8093;line-height:1.4}
.share-summary{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.donut{width:148px;height:148px;border-radius:50%;display:grid;place-items:center;flex-shrink:0}
.donut>span{width:106px;height:106px;background:white;border-radius:50%;display:grid;align-content:center;justify-items:center;text-align:center;padding:12px}
.donut strong{font-size:23px}.donut small{font-size:9px;line-height:1.4;color:#718395}
.ranking{flex:1;min-width:145px;display:grid;gap:6px}
.ranking button{display:flex;align-items:center;gap:6px;text-align:left;border:0;background:none;padding:5px 0;color:#294961;font-size:11px}
.ranking .name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}.ranking strong{font-size:11px}
.dot{width:10px;height:10px;flex-shrink:0;border-radius:50%}
.chart-rows{display:grid;gap:8px;max-height:290px;overflow:auto}
.chart-rows button,.chart-row{display:grid;grid-template-columns:minmax(70px,100px) minmax(35px,1fr) 28px;gap:9px;align-items:center;border:0;background:transparent;text-align:left;padding:5px 0;color:#34536e;font-size:11px}
.chart-rows button:hover{background:#f5f9fc}
.chart-rows strong{text-align:right}
.bar-track{height:11px;border-radius:9px;background:#eaf1f5;overflow:hidden}
.bar-track i{display:block;height:100%;border-radius:9px;background:linear-gradient(90deg,#155caf,#0eb5b2)}
.hint{margin-top:11px;font-size:10px}
.edges{display:grid;gap:5px;max-height:270px;overflow:auto}
.edges button{display:flex;align-items:center;justify-content:space-between;gap:8px;border:0;background:#f5f9fc;border-radius:7px;padding:8px;color:#274861;font-size:11px;text-align:left}
.edges strong{white-space:nowrap}.edges b{color:#0f92aa}
.glossary{display:grid;gap:7px;margin:4px 0}.glossary dt{font-size:11px;font-weight:800}.glossary dd{font-size:11px;color:#63788d;margin:0;line-height:1.5}
.people-list{display:grid;gap:6px}.people-list>button{border:1px solid #e1ebf2;background:#fff;border-radius:9px;padding:10px;display:flex;align-items:center;gap:10px;text-align:left;color:#1e3e5d}
.people-list>button:hover{border-color:#8dbbd3;background:#f8fbfd}
.avatar{width:35px;height:35px;background:#d8ecf5;color:#15506c;border-radius:50%;display:grid;place-items:center;font-size:13px;font-weight:800;flex-shrink:0}
.avatar.small{width:27px;height:27px;font-size:11px}
.person-text{display:grid;gap:3px;flex:2;min-width:100px;overflow:hidden}
.person-text strong{font-size:12px;white-space:nowrap;text-overflow:ellipsis;overflow:hidden}.person-text small{font-size:10px;color:#6b8193}
.person-bar{flex:1;height:8px;border-radius:9px;background:#edf3f6;overflow:hidden;min-width:35px}
.person-bar i{display:block;height:100%;border-radius:8px}
.people-list b{font-size:12px;min-width:46px;text-align:right}
.filters{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.filters label{display:grid;gap:5px;font-size:11px;font-weight:700;color:#39566c}
.filters select,.filters input{width:100%;padding:9px 10px;background:#fff;border:1px solid #cfdfe8;border-radius:8px;color:#254764;font:inherit;font-size:12px}
.filter-summary{display:flex;align-items:center;justify-content:space-between;font-size:11px;color:#647c90}
.filter-summary button{border:0;background:none;color:#0c6e99;text-decoration:underline;font-size:11px}
.conversation-list{display:grid;gap:9px}
.conversation-card{padding:13px;border:1px solid #dfeaf1;border-radius:10px;background:#fff}
.conversation-card header{display:flex;align-items:center;flex-wrap:wrap;gap:8px;font-size:12px}
.conversation-card header>strong{margin-right:auto}
.pill{font-size:10px;background:#eaf2f7;color:#526f85;border-radius:8px;padding:4px 7px}
.reply-label{color:#12618b;margin:8px 0 0;font-size:11px}
.excerpt{font-size:12px;line-height:1.65;color:#203b53;margin:8px 0;white-space:pre-wrap;overflow-wrap:anywhere}
.conversation-card footer{color:#8191a0;font-size:10px;line-height:1.4}
.more{margin:auto;border:1px solid #bdd9e8;padding:10px 18px;border-radius:9px;color:#156389;background:#eef7fa;font-size:12px}
.hour-chart{height:125px;display:flex;gap:4px;align-items:end;border-bottom:1px solid #c6d5e0;margin:25px 0 19px}
.hour-chart>div{flex:1;height:115px;min-width:0;display:flex;align-items:center;justify-content:end;flex-direction:column;position:relative}
.hour-chart span{width:100%;max-width:23px;min-height:2px;background:#129baa;border-radius:3px 3px 0 0}
.hour-chart small{font-size:9px;color:#718699;position:absolute;bottom:-18px}
.explore-next{margin-top:20px;padding:16px;background:#f0f8fa;border:1px solid #cfe4e8;border-radius:11px;display:grid;gap:9px}
.explore-next strong{font-size:14px}.explore-next p{font-size:12px;color:#587186;line-height:1.55;margin:5px 0}
.question-actions{display:flex;flex-wrap:wrap;gap:8px}
.question-actions button{border:1px solid #bad2e0;background:#fff;color:#155d82;border-radius:9px;padding:9px 12px;font-size:11px;font-weight:750}
.question-actions button:disabled{opacity:.5;cursor:not-allowed}
.provenance,.after-report,.sample-warning{font-size:10px;color:#6b8397;line-height:1.6;margin:15px 0 0}
.population-note{font-size:11px;color:#566982;background:#f6f8fc;border:1px solid #dbe2ed;padding:11px;border-radius:9px;line-height:1.6}
.sample-warning{color:#9b6224;background:#fff8ea;border:1px solid #ecd3a2;padding:10px;border-radius:8px}
.after-report{background:#f8fafb;padding:10px;border:1px solid #e1e9ed;border-radius:8px}
.error{padding:12px;border:1px solid #d99595;background:#fff0ee;border-radius:8px;color:#9e3939;margin:15px 0}
.error button{margin-left:10px}.loading,.empty{font-size:12px;color:#8292a0;line-height:1.6;padding:8px 0}
@media(max-width:950px){.two{grid-template-columns:1fr}.number-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.highlights{grid-template-columns:1fr}}
@media(max-width:520px){.number-grid,.filters{grid-template-columns:1fr 1fr}.person-bar{display:none}.hub-tabs button{flex:1;padding:9px 5px}.hub-heading h2{font-size:20px}.number-card strong{font-size:23px}}
@media print{.refresh,.hub-tabs,.question-actions,.filters,.more{display:none!important}.results-hub,.panel{box-shadow:none;border-color:#ddd}.two{break-inside:avoid}.hub-content{break-inside:auto}}
</style>
