<template>
  <section class="character-network" aria-label="Grafo de conversaciones del escenario">
    <div class="network-bar">
      <div>
        <strong>Quién conversó con quién</strong>
        <small>Nombres de escena · Profesiones · Respuestas registradas</small>
      </div>
      <button class="reload" type="button" @click="load" :disabled="loading">{{ loading ? 'Consultando…' : '↻' }}</button>
    </div>
    <div v-if="data?.rooms?.length" class="room-filter">
      <label for="social-room-filter">Espacio</label>
      <select id="social-room-filter" v-model="selectedRoom">
        <option value="">Todos los espacios</option>
        <option v-for="room in data.rooms" :key="room" :value="room">{{ spaceName(room) }}</option>
      </select>
    </div>
    <div v-if="error" class="network-message" role="alert">
      {{ error }} <button type="button" @click="load">Reintentar</button>
    </div>
    <div v-else-if="loading && !data" class="network-message">Leyendo conversaciones guardadas…</div>
    <div v-else-if="!data?.nodes?.length" class="network-message">
      Todavía no hay conversaciones registradas para esta simulación.
    </div>
    <template v-if="data?.nodes?.length">
      <div class="visual-area" ref="visualArea">
        <svg ref="canvas" role="img" aria-label="Mapa de personajes ficticios y respuestas dirigidas entre ellos"></svg>
      </div>
      <div class="network-foot">
        <span><strong>{{ visibleNodes.length }}</strong> participantes</span>
        <span><strong>{{ visibleEdges.length }}</strong> conexiones</span>
        <span><strong>{{ responseCount }}</strong> respuestas</span>
      </div>
      <p v-if="data.partial" class="partial-warning">
        El historial superó el límite de lectura segura. El mapa puede estar incompleto.
      </p>
      <p class="source-note">Las flechas representan respuestas guardadas en este escenario, no relaciones de personas reales.
        Los nombres son alias del ejercicio.</p>
    </template>

    <div v-if="selected" class="conversation-detail" role="dialog" aria-modal="false"
         :aria-label="selected.type === 'person' ? 'Participante de la escena' : 'Conversación registrada'">
      <header>
        <div v-if="selected.type === 'person'">
          <strong>{{ selected.person.name }}</strong>
          <small>{{ selected.person.profession }}</small>
        </div>
        <div v-else>
          <strong>{{ personName(selected.edge.source) }} → {{ personName(selected.edge.target) }}</strong>
          <small>{{ spaceName(selected.edge.channel) }} · {{ selected.edge.count }} respuestas</small>
        </div>
        <button type="button" @click="selected=null" aria-label="Cerrar detalle">×</button>
      </header>
      <div class="conversation-detail-body">
        <template v-if="selected.type === 'person'">
          <p>Nombre ficticio utilizado para explorar su participación en el escenario.</p>
          <h4>Intervenciones guardadas</h4>
          <article v-for="(m,i) in personMessages(selected.person.id).slice(0,12)" :key="i" class="dialog-line">
            <b>{{ spaceName(m.channel) }}</b>
            <span v-if="m.recipient">Responde a {{ m.recipient }}</span>
            <p>{{ m.content }}</p>
          </article>
          <p v-if="!personMessages(selected.person.id).length">No hay textos visibles en la muestra conservada.</p>
        </template>
        <template v-else>
          <h4>Qué se dijeron</h4>
          <article v-for="(message,i) in edgeMessages(selected.edge).slice(0,12)" :key="i" class="dialog-line">
            <b>{{ message.author }} → {{ message.recipient }}</b>
            <p>{{ message.content }}</p>
          </article>
          <p v-if="!edgeMessages(selected.edge).length">La conexión está registrada, pero no hay texto en la muestra.</p>
        </template>
      </div>
    </div>
  </section>
</template>

<script setup>
import {computed, ref, nextTick, watch, onMounted, onUnmounted} from 'vue'
import * as d3 from 'd3'
import service from '../api'
const props = defineProps({simulationId:{type:String,required:true}})
const data = ref(null)
const loading = ref(false)
const error = ref('')
const selectedRoom = ref('')
const selected = ref(null)
const visualArea = ref(null)
const canvas = ref(null)
let simulation = null
let observer = null

const spaceName = value => ({
  plaza:'Plaza · micropublicaciones',foro:'Foro abierto',
  profesional:'Comunidad profesional',grupos:'Grupo social',
  videos:'Comentarios a videos',twitter:'Plaza',reddit:'Comunidad',
})[value] || value || 'Espacio de conversación'
const visibleEdges = computed(() => (data.value?.edges || []).filter(e =>
  !selectedRoom.value || e.channel === selectedRoom.value))
const visibleNodes = computed(() => {
  const all = data.value?.nodes || []
  if (!selectedRoom.value) return all
  const mentioned = new Set((data.value?.messages || [])
    .filter(m => m.channel === selectedRoom.value).map(m => m.from))
  return all.filter(p => mentioned.has(p.id))
})
const responseCount = computed(()=>visibleEdges.value.reduce((sum,e)=>sum+e.count,0))
const personName = id => data.value?.nodes?.find(p => String(p.id) === String(id))?.name || 'Participante'
const personMessages = id => (data.value?.messages || []).filter(m =>
  String(m.from) === String(id) && (!selectedRoom.value || m.channel===selectedRoom.value))
const edgeMessages = e => (data.value?.messages || []).filter(m =>
  String(m.from)===String(e.source) && String(m.to)===String(e.target) && m.channel===e.channel)

async function load(){
  if(!props.simulationId) return
  loading.value=true; error.value=''
  try{
    const result = await service.get('/api/simulation/'+encodeURIComponent(props.simulationId)+'/conversation-graph')
    if(!result.success || !result.data) throw new Error(result.error || 'Sin datos')
    data.value=result.data
    selectedRoom.value=''
    selected.value=null
    await nextTick(); render()
  }catch(e){error.value='No fue posible consultar las conversaciones: '+(e.message||'Error')}
  finally{loading.value=false}
}
function render(){
  if(simulation){simulation.stop();simulation=null}
  if(!canvas.value || !visualArea.value || !data.value) return
  const width=Math.max(280,visualArea.value.clientWidth)
  const height=Math.max(250,visualArea.value.clientHeight)
  const svg=d3.select(canvas.value).attr('viewBox',`0 0 ${width} ${height}`).attr('width',width).attr('height',height)
  svg.selectAll('*').remove()
  const rawNodes=visibleNodes.value
  const nodes=rawNodes.map(p=>({...p}))
  if(!nodes.length)return
  const ids=new Set(nodes.map(p=>p.id))
  const edges=visibleEdges.value.filter(e=>ids.has(e.source)&&ids.has(e.target))
    .map(e=>({...e}))
  const defs=svg.append('defs')
  defs.append('marker').attr('id','character-response-arrow').attr('viewBox','0 -5 10 10')
    .attr('refX',18).attr('refY',0).attr('markerWidth',7).attr('markerHeight',7)
    .attr('orient','auto').append('path').attr('d','M0,-5L10,0L0,5').attr('fill','#1683a7')
  const frame=svg.append('g')
  svg.call(d3.zoom().scaleExtent([.35,3]).on('zoom',ev=>frame.attr('transform',ev.transform)))
  const lines=frame.append('g').attr('class','character-edges').selectAll('line').data(edges)
    .enter().append('line').attr('stroke','#1683a7').attr('stroke-opacity',.65)
    .attr('stroke-width',d=>Math.min(5,1.5+Math.sqrt(d.count)))
    .attr('marker-end','url(#character-response-arrow)')
    .style('cursor','pointer')
    .on('click',(event,d)=>{event.stopPropagation();selected.value={type:'edge',edge:d}})
  const groups=frame.append('g').attr('class','character-nodes').selectAll('g').data(nodes)
    .enter().append('g').attr('class','character-node').attr('tabindex',0)
    .attr('role','button').attr('aria-label',d=>d.name+', '+d.profession)
    .style('cursor','pointer')
    .on('click',(event,d)=>{event.stopPropagation();selected.value={type:'person',person:d}})
    .on('keydown',(event,d)=>{if(event.key==='Enter'||event.key===' '){
      event.preventDefault();selected.value={type:'person',person:d}
    }})
  groups.append('circle').attr('r',22).attr('fill','#e5f3f7')
    .attr('stroke','#187894').attr('stroke-width',2.5)
  groups.append('text').text(d=>d.name?.split(' ').map(p=>p[0]).slice(0,2).join('')||'P')
    .attr('text-anchor','middle').attr('dy','0.32em')
    .attr('fill','#115473').attr('font-size','13px').attr('font-weight',800)
  groups.append('text').text(d=>d.name).attr('y',37).attr('text-anchor','middle')
    .attr('font-size','11px').attr('font-weight',750).attr('fill','#213e56')
  groups.append('text').text(d=>d.profession==='Profesión no indicada'?'Profesión no indicada':d.profession)
    .attr('y',52).attr('text-anchor','middle').attr('font-size','9px')
    .attr('fill','#617b90')
    .text(function(){
      const v=d3.select(this).text()
      return v.length>27?v.slice(0,26)+'…':v
    })
  simulation=d3.forceSimulation(nodes)
    .force('link',d3.forceLink(edges).id(d=>d.id).distance(140).strength(.5))
    .force('charge',d3.forceManyBody().strength(-420))
    .force('collision',d3.forceCollide(82))
    .force('center',d3.forceCenter(width/2,height/2))
    .alphaDecay(.08).on('tick',()=>{
      lines.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
        .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y)
      groups.attr('transform',d=>`translate(${d.x},${d.y})`)
    })
}
watch(selectedRoom,()=>nextTick(render))
watch(visualArea, el=>{
  observer?.disconnect()
  if(el) observer?.observe(el)
})
watch(()=>props.simulationId,load)
onMounted(()=>{
  load()
  if(typeof ResizeObserver!=='undefined'){
    observer=new ResizeObserver(()=>{if(data.value)render()})
    if(visualArea.value)observer.observe(visualArea.value)
  }
})
onUnmounted(()=>{observer?.disconnect();simulation?.stop()})
</script>

<style scoped>
.character-network{position:absolute;inset:0;display:flex;flex-direction:column;background:#f8fbfd;overflow:hidden;font-family:system-ui,sans-serif}
.network-bar{z-index:2;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 17px 8px;background:#fff;border-bottom:1px solid #e2ebf1}
.network-bar strong{display:block;font-size:14px;color:#184b68}.network-bar small{display:block;margin:3px 0;color:#6b8496;font-size:10px;line-height:1.5}
.reload{border:1px solid #d1e2eb;background:#f2f8fb;color:#125d80;border-radius:9px;font-size:18px;min-width:40px;min-height:40px}
.room-filter{z-index:2;padding:10px 16px;display:flex;align-items:center;gap:10px;background:#fff;border-bottom:1px solid #e3edf2}
.room-filter label{font-size:11px;font-weight:800;color:#5b778a}.room-filter select{font:12px system-ui,sans-serif;max-width:75%;min-height:35px;border:1px solid #c9dfe9;border-radius:9px;background:#fff;color:#23536b;padding:6px}
.visual-area{flex:1;min-height:150px;min-width:0;background-image:radial-gradient(#dce7ed .9px,transparent .9px);background-size:23px 23px}
.visual-area svg{width:100%;height:100%;touch-action:none}
.network-foot{display:flex;justify-content:space-around;gap:8px;padding:10px 7px;border-top:1px solid #dfeaf1;background:#fff;font-size:11px;color:#536f83}
.network-foot strong{color:#175f7e}
.source-note,.partial-warning{font-size:10px;color:#5c7487;margin:0;padding:6px 11px 10px;line-height:1.5;background:#fff}
.partial-warning{color:#a45c27;background:#fff4e6}
.network-message{padding:22px 16px;text-align:center;color:#648094;font-size:12px}
.conversation-detail{position:absolute;z-index:15;top:110px;right:14px;bottom:14px;width:min(370px,calc(100% - 28px));background:#fff;box-shadow:0 10px 36px #153c5b26;border:1px solid #d5e5ef;border-radius:16px;display:flex;flex-direction:column;overflow:hidden}
.conversation-detail header{display:flex;align-items:start;justify-content:space-between;gap:11px;padding:15px;border-bottom:1px solid #e6edf3}
.conversation-detail header strong{display:block;font-size:15px;color:#193f5b}
.conversation-detail header small{display:block;font-size:11px;color:#587b90;margin-top:4px}
.conversation-detail header button{font-size:22px;border:0;border-radius:9px;background:#edf4f8;min-width:37px;min-height:37px}
.conversation-detail-body{padding:12px 15px;overflow:auto;min-height:0;font-size:12px;color:#526b7b}
.conversation-detail-body h4{margin:9px 0;font-size:13px;color:#1f5575}
.dialog-line{padding:10px 0;border-bottom:1px solid #e8eff4}
.dialog-line b{font-size:11px;color:#1d6584}.dialog-line span{font-size:10px;display:block;color:#7490a3}
.dialog-line p{font-size:12px;line-height:1.6;margin:6px 0;white-space:pre-wrap;overflow-wrap:anywhere;color:#28465b}
@media(max-width:767px){.network-bar{padding:11px}.conversation-detail{position:absolute;inset:0;width:100%;border-radius:0;border:0;top:0}.network-foot{font-size:10px;flex-wrap:wrap}}
</style>
