<template>
  <section class="analytics" aria-label="Estadísticas de interacción de la simulación">
    <header class="heading">
      <div><h2>Actividad e interacción simulada</h2><p>Estadísticas calculadas desde eventos guardados, sin estimaciones inventadas.</p></div>
      <button type="button" @click="load" :disabled="loading">{{ loading ? 'Cargando…' : 'Actualizar métricas' }}</button>
    </header>
    <p v-if="error" class="alert" role="alert">{{ error }}</p>
    <template v-if="data">
      <p class="notice">Son personajes y decisiones <strong>simulados</strong>, no personas o conversaciones reales. Las fechas corresponden a registros de ejecución, no al calendario ficticio del escenario.</p>
      <div v-if="data.partial" class="alert">Muestra parcial: el registro superó el límite de lectura segura.</div>
      <div class="kpis">
        <div><small>Participantes activos</small><strong>{{ data.active_participants }}</strong></div>
        <div><small>Acciones registradas</small><strong>{{ data.total_actions }}</strong></div>
        <div><small>Mensajes / comentarios</small><strong>{{ data.message_actions }}</strong></div>
        <div><small>Pares de interacción explícitos</small><strong>{{ data.recorded_interaction_pairs }}</strong></div>
      </div>
      <section v-if="data.followups?.available" class="followups">
        <h3>Conversaciones y encuestas posteriores al informe</h3>
        <p class="notice">Estas consultas fueron realizadas después de la simulación y se cuentan por separado.</p>
        <div class="kpis">
          <div><small>Turnos de chat</small><strong>{{data.followups.chat_turns}}</strong></div>
          <div><small>Encuestas realizadas</small><strong>{{data.followups.surveys}}</strong></div>
          <div><small>Respuestas de encuesta</small><strong>{{data.followups.survey_answers}}</strong></div>
          <div><small>Respuestas a participantes</small><strong>{{data.followups.participant_turns}}</strong></div>
        </div>
        <div class="two-col">
          <article><h3>Actividad posterior por día</h3>
            <div class="bars">
              <div class="bar" v-for="item in data.followups.by_day" :key="item.date">
                <span>{{item.date}}</span><div class="track"><i :style="{width:width(item.count,data.followups.by_day)+'%'}"></i></div><b>{{item.count}}</b>
              </div>
            </div>
          </article>
          <article><h3>Participantes consultados</h3>
            <table><thead><tr><th>Agente ficticio</th><th>Respuestas</th></tr></thead>
              <tbody><tr v-for="p in data.followups.participants" :key="p.id"><td>{{p.name}} ({{p.id}})</td><td>{{p.responses}}</td></tr></tbody></table>
          </article>
        </div>
      </section>
      <div class="two-col">
        <article>
          <h3>Histograma por ronda</h3>
          <div v-if="data.by_round?.length" class="bars">
            <div class="bar" v-for="i in data.by_round" :key="i.round">
              <span>Ronda {{ i.round }}</span><div class="track"><i :style="{width:width(i.count,data.by_round)+'%'}"></i></div><b>{{ i.count }}</b>
            </div>
          </div><p v-else class="empty">Sin rondas registradas.</p>
        </article>
        <article>
          <h3>Actividad por fecha</h3>
          <div v-if="data.by_day?.length" class="bars">
            <div class="bar" v-for="i in data.by_day" :key="i.date">
              <span>{{ i.date }}</span><div class="track"><i :style="{width:width(i.count,data.by_day)+'%'}"></i></div><b>{{ i.count }}</b>
            </div>
          </div><p v-else class="empty">Sin fechas válidas.</p>
        </article>
        <article>
          <h3>Histograma horario de eventos</h3>
          <div class="hours" role="img" aria-label="Histograma de acciones por hora de ejecución">
            <div v-for="i in data.by_hour" :key="i.hour" class="hour" :title="i.hour+':00 — '+i.count+' acciones'">
              <span :style="{height:Math.max(i.count ? 8 : 2,width(i.count,data.by_hour))+'%'}"></span>
              <small v-if="Number(i.hour)%4===0">{{ i.hour }}</small>
            </div>
          </div>
        </article>
        <article>
          <h3>Tipos de acciones</h3>
          <div class="bars">
            <div class="bar" v-for="i in data.by_type" :key="i.type">
              <span>{{ i.type }}</span><div class="track"><i :style="{width:width(i.count,data.by_type)+'%'}"></i></div><b>{{ i.count }}</b>
            </div>
          </div>
        </article>
      </div>
      <article class="participants">
        <h3>Quiénes participaron (agentes simulados)</h3>
        <table><thead><tr><th>Participante</th><th>Acciones</th><th>Mensajes</th></tr></thead>
          <tbody><tr v-for="p in data.participants" :key="p.id"><td>{{ p.name }} <small>({{ p.id }})</small></td><td>{{ p.actions }}</td><td>{{ p.messages }}</td></tr></tbody></table>
        <p v-if="!data.participants?.length" class="empty">No hay agentes registrados.</p>
      </article>
      <article v-if="data.interactions?.length">
        <h3>Relaciones explícitas entre agentes</h3>
        <div v-for="edge in data.interactions" :key="edge.from+'-'+edge.to" class="edge">
          {{ edge.from }} → {{ edge.to }} <strong>{{ edge.count }} interacción(es)</strong>
        </div>
      </article>
      <article v-if="data.messages?.length">
        <h3>Intervenciones registradas — muestra de hasta 50</h3>
        <div v-for="(m,index) in data.messages" :key="index" class="message">
          <strong>{{ m.participant }} · ronda {{ m.round ?? '—' }}</strong>
          <p>{{ m.excerpt }}</p><small>{{ m.timestamp || 'Fecha no disponible' }}</small>
        </div>
      </article>
      <p class="notice">Origen: {{ data.source }} · Inicio: {{ data.first_event || '—' }} · Último evento: {{ data.last_event || '—' }}. Los vínculos entre actores solo aparecen si el registro identifica explícitamente al destinatario.</p>
    </template>
  </section>
</template>
<script setup>
import {ref,watch} from 'vue'
import service from '../api'
const props=defineProps({reportId:{type:String,default:''},nativeRunId:{type:String,default:''}})
const data=ref(null),loading=ref(false),error=ref('')
function width(n,values){const max=Math.max(1,...(values||[]).map(v=>Number(v.count)||0));return Math.min(100,Math.round(100*(Number(n)||0)/max))}
async function load(){
  const id=props.nativeRunId||props.reportId
  if(!id)return
  loading.value=true;error.value='';data.value=null
  try{
    const endpoint=props.nativeRunId?'/api/native-simulation/'+encodeURIComponent(id)+'/metrics':'/api/report/'+encodeURIComponent(id)+'/metrics'
    const response=await service.get(endpoint)
    data.value=response.data||null
  }catch(e){error.value='No se pudieron cargar las estadísticas: '+(e.message||'Error de conexión')}
  finally{loading.value=false}
}
watch(()=>[props.reportId,props.nativeRunId],load,{immediate:true})
</script>
<style scoped>
.analytics{background:#fff;border:1px solid #d8e5ee;border-radius:14px;margin:18px 0;padding:clamp(12px,2vw,20px);color:#12345a;font:inherit}
.heading{display:flex;align-items:center;flex-wrap:wrap;justify-content:space-between;gap:12px}
.heading h2{font-size:19px;margin:0 0 7px}.heading p,.notice{font-size:12px;color:#4e667b;line-height:1.6}
button{border:1px solid #bed4e4;border-radius:8px;padding:9px 12px;color:#164f74;background:#eef7fb;cursor:pointer}
.alert{color:#a12c3d;font-size:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:20px 0}
.kpis>div{background:#edf7fa;border-radius:10px;padding:14px}.kpis small{display:block;font-size:11px;color:#4b697c}
.kpis strong{font-size:26px;display:block;margin-top:7px}
.two-col{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,265px),1fr));gap:16px}
article{border:1px solid #e1eaf1;border-radius:10px;padding:13px;margin:10px 0;min-width:0}
h3{font-size:14px;margin:0 0 14px}.bars{display:grid;gap:9px;max-height:250px;overflow:auto}
.bar{display:grid;grid-template-columns:minmax(85px,100px) 1fr 28px;gap:7px;align-items:center;font-size:11px}
.bar span{overflow-wrap:anywhere}.bar b{text-align:right}.track{height:10px;border-radius:10px;background:#edf3f7;overflow:hidden}
.track i{display:block;background:linear-gradient(90deg,#1057a4,#08aeb8);height:100%;border-radius:10px}
.hours{height:145px;display:flex;align-items:end;gap:3px;border-bottom:1px solid #b9ccdb}
.hour{flex:1;height:125px;min-width:0;display:flex;align-items:center;justify-content:end;flex-direction:column}
.hour span{background:#13a5ad;width:100%;max-width:24px;min-height:2px}.hour small{font-size:9px;color:#5c748e;position:absolute;transform:translateY(15px)}
table{width:100%;border-collapse:collapse;font-size:12px}
td,th{text-align:left;padding:8px;border-bottom:1px solid #e8f0f5;overflow-wrap:anywhere}td small{color:#7990a1}
.edge,.message{padding:8px 0;border-bottom:1px solid #eef2f7;font-size:12px;overflow-wrap:anywhere}.edge strong{float:right}
.message p{white-space:pre-wrap;line-height:1.5}.message small,.empty{font-size:11px;color:#708598}
@media print{button{display:none}.bars{max-height:none;overflow:visible}.analytics{break-inside:avoid}}
</style>