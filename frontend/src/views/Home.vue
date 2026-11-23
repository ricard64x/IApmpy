<template>
  <TenonderaShell title="Crear una nueva simulación" subtitle="De un documento a un escenario vivo: explorá qué podría pasar." section="NUEVO ESCENARIO">
    <div class="workspace-grid">
      <section class="workspace-intro">
        <div class="intro-label">✦ INTELIGENCIA COLECTIVA</div>
        <h2>Subí tus documentos.<br><em>Explorá el futuro.</em></h2>
        <p>Tenonderã conecta información, crea participantes virtuales y simula sus interacciones para anticipar tendencias y escenarios posibles.</p>
        <SimulationJourney theme="dark" compact :current-step="1" />
        <div class="info-card">
          <span>🇵🇾</span>
          <div><strong>Simulando el futuro desde Paraguay</strong><p>Los resultados son sintéticos: exploran escenarios, no reemplazan encuestas ni datos verificables.</p></div>
        </div>
      </section>
      <section class="workspace-form">
        <div class="form-header"><span class="form-icon">◇</span><div><h3>Paso 1 · Definí el escenario</h3><p>En esta pantalla guardás el contexto. Los participantes y las conversaciones se eligen después.</p></div></div>
        <div class="form-group">
          <div class="form-label"><label>01 · Documentos de referencia</label><small>PDF, Markdown y TXT · Máximo 50 MB por solicitud</small></div>
          <div class="upload-area" role="button" tabindex="0" :aria-label="files.length?'Agregar documentos de referencia':'Seleccionar documentos de referencia'"
               :class="{dragging,hasFiles:files.length>0}" @dragover.prevent="dragging=true" @dragleave.prevent="dragging=false" @drop.prevent="drop"
               @click="pick" @keydown.enter.prevent="pick" @keydown.space.prevent="pick">
            <input ref="fileInput" type="file" hidden multiple accept=".pdf,.md,.txt,.markdown" @change="select" />
            <template v-if="!files.length"><div class="upload-glyph">↑</div><strong>Arrastrá o seleccioná tus archivos</strong><span>Cargá documentos con información del escenario</span></template>
            <template v-else><div class="upload-glyph">✓</div><strong>{{files.length}} archivo(s) preparados</strong><span>Hacé clic para agregar más documentos</span></template>
          </div>
          <ul v-if="files.length" class="file-list"><li v-for="(file,index) in files" :key="index"><span>▤ {{file.name}}</span><button type="button" :aria-label="'Quitar '+file.name" @click="files.splice(index,1)">×</button></li></ul>
          <p v-if="files.length" class="file-summary" aria-live="polite">{{files.length}} documento(s) · {{totalFileMb}} MB de 50 MB permitidos por carga</p>
        </div>
        <div class="form-group"><div class="form-label"><label for="project-title">Nombre del proyecto (opcional)</label><small>Si lo dejás vacío, se genera desde el objetivo</small></div>
          <input id="project-title" class="area-input" v-model.trim="projectName" maxlength="100" placeholder="Ej.: Simulación de respuesta ante fraude"></div>
        <div class="form-group"><div class="form-label"><label for="sim-goal">02 · ¿Qué querés simular?</label><small>Pregunta o hipótesis</small></div>
          <textarea id="sim-goal" v-model="prompt" rows="6" placeholder="Ejemplo: ¿Cómo reaccionaría la opinión pública paraguaya al lanzamiento de un nuevo banco 100 % digital?"></textarea>
        </div>
        <div class="form-group">
          <div class="form-label">
            <label for="interaction-area">03 · Ámbito geográfico de interacción</label>
            <small>Contexto del escenario, no geolocalización real</small>
          </div>
          <input id="interaction-area" class="area-input" v-model.trim="interactionArea" maxlength="120" placeholder="Ej.: Paraguay, Asunción o América Latina">
          <p class="area-help">Los agentes tomarán este ámbito como referencia al generar perfiles y conversaciones. La plataforma social se elige en el paso 2.</p>
        </div>
        <div class="prepare-checklist" role="status" aria-live="polite">
          <strong>Antes de continuar</strong>
          <div :class="{ready:files.length>0}"><span>{{files.length?'✓':'1'}}</span> Agregá al menos un documento</div>
          <div :class="{ready:!!prompt.trim()}"><span>{{prompt.trim()?'✓':'2'}}</span> Explicá qué querés analizar o simular</div>
          <div class="ready"><span>✓</span> El lugar de interacción es opcional y editable</div>
        </div>
        <div class="system-capacity">
          <span class="resource-icon">◉</span>
          <div><strong>La cantidad de participantes se elige en el paso 3</strong>
            <small>Motor eficiente: hasta {{capacity?.lightweight_max_profiles??'—'}} personajes (si está disponible).
              Motor social completo: límite conservador de {{capacity?.recommended_max_profiles??'—'}} perfiles detectados. Solo una ejecución a la vez.</small></div>
        </div>
        <p v-if="capacity?.busy" class="busy-note" role="status">Hay otra simulación ejecutándose. Podés preparar el proyecto, pero tendrás que esperar a que termine para iniciar una nueva ejecución.</p>
        <p v-if="error" class="error" role="alert">{{error}}</p>
        <button class="start" :disabled="!canStart" @click="start">Guardar documentos y preparar el mapa <span>→</span></button>
        <p class="small-note">No inicia conversaciones todavía: primero se procesan las fuentes. Más adelante definirás participantes, espacios y rondas.</p>
      </section>
    </div>
    <section class="history-area"><div class="section-h"><div><span>MIS ESCENARIOS</span><h2>Historial de simulaciones</h2></div><button @click="router.push('/')">Volver al panel →</button></div><HistoryDatabase /></section>
  </TenonderaShell>
</template>
<script setup>
import {computed,onMounted,ref} from 'vue'
import {useRouter} from 'vue-router'
import service from '../api'
import {setPendingUpload} from '../store/pendingUpload'
import TenonderaShell from '../components/TenonderaShell.vue'
import SimulationJourney from '../components/SimulationJourney.vue'
import HistoryDatabase from '../components/HistoryDatabase.vue'
const router=useRouter()
const projectName=ref(''),prompt=ref(''),interactionArea=ref('Paraguay'),files=ref([]),dragging=ref(false),error=ref(''),capacity=ref(null),fileInput=ref(null)
const MAX_UPLOAD_BYTES=50*1024*1024
const totalFileMb=computed(()=>(files.value.reduce((sum,f)=>sum+(f.size||0),0)/1048576).toFixed(1))
const canStart=computed(()=>files.value.length>0&&!!prompt.value.trim())
const pick=()=>fileInput.value?.click()
function addFiles(collection){
  error.value=''
  for(const file of collection) {
    if(!/\.(pdf|md|markdown|txt)$/i.test(file.name)){error.value='Formato no admitido: '+file.name;continue}
    if(files.value.some(f=>f.name===file.name&&f.size===file.size))continue
    if(files.value.reduce((sum,f)=>sum+(f.size||0),0)+(file.size||0)>MAX_UPLOAD_BYTES){
      error.value='La carga supera 50 MB en total. Quitá algún documento e intentá otra vez.'
      continue
    }
    files.value.push(file)
  }
}
function select(event){addFiles(Array.from(event.target.files||[]));event.target.value=''}
function drop(event){dragging.value=false;addFiles(Array.from(event.dataTransfer.files||[]))}
function start(){
  if(!canStart.value)return
  const scope = interactionArea.value.trim()
  const requirement = scope
    ? prompt.value.trim() + '\n\nÁmbito territorial de interacción de los agentes: ' + scope + '. Considerá este contexto al crear sus perfiles y simular las conversaciones.'
    : prompt.value.trim()
  setPendingUpload(files.value,requirement,projectName.value)
  router.push({name:'Process',params:{projectId:'new'}})
}
onMounted(async()=>{try{capacity.value=(await service.get('/api/capacity/status')).data}catch(e){error.value='No se pudo consultar la capacidad: '+e.message}})
</script>
<style scoped>
.workspace-grid{display:grid;grid-template-columns:minmax(260px,.95fr) minmax(420px,1.18fr);gap:26px;align-items:start}.workspace-intro{background:linear-gradient(155deg,#063267,#092751 50%,#07788b);color:#fff;border-radius:23px;padding:clamp(26px,4vw,48px);min-height:600px;position:relative;overflow:hidden}
.workspace-intro:after{content:"✺";position:absolute;right:-140px;top:-150px;color:#a3ffff13;font-size:500px;line-height:1;pointer-events:none}
.intro-label{font-size:11px;letter-spacing:.17em;color:#76e8dd;font-weight:800}.workspace-intro h2{font-size:clamp(32px,3.6vw,51px);letter-spacing:-.06em;line-height:1.11;margin:26px 0}.workspace-intro h2 em{color:#69e8df;font-weight:550}.workspace-intro>p{color:#bbd4ea;line-height:1.8;max-width:500px;font-size:14px}.steps{margin-top:32px;display:grid;gap:15px;position:relative;z-index:1}.steps>div{display:flex;align-items:center;gap:16px}.steps>div>span{width:39px;height:39px;border-radius:10px;background:#ffffff14;border:1px solid #9eddee2f;display:grid;place-items:center;color:#6de9d9;font-size:12px;font-weight:800}.steps p{margin:0;display:flex;flex-direction:column;gap:3px}.steps strong{font-size:13px}.steps small{font-size:11px;color:#bdd8e9}.info-card{display:flex;align-items:flex-start;gap:13px;border-radius:14px;padding:17px;margin-top:35px;background:#ffffff14;border:1px solid #ffffff1d;position:relative;z-index:1}.info-card>span{font-size:23px}.info-card strong{font-size:12px}.info-card p{font-size:11px;line-height:1.5;color:#c0e1eb;margin-top:7px}.workspace-form{background:white;border:1px solid #dfe9f2;border-radius:23px;padding:clamp(20px,3vw,35px);box-shadow:0 7px 24px #103c6910}.form-header{display:flex;gap:12px;align-items:center;padding-bottom:25px;border-bottom:1px solid #eef2f7}.form-icon{display:grid;place-items:center;font-size:27px;background:#e7f8fb;color:#0088a1;width:44px;height:44px;border-radius:12px}.form-header h3{font-size:18px;margin:0 0 7px;color:#122c4b}.form-header p{color:#8292a5;font-size:12px}.form-group{margin-top:25px}.form-label{display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin-bottom:14px}.form-label label{font-weight:800;font-size:13px;color:#244767}.form-label small{font-size:10px;color:#8197ab}.upload-area{border:1.5px dashed #a4cdda;border-radius:14px;min-height:175px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:10px;color:#37677e;cursor:pointer;background:#f8fcfe;transition:.18s;text-align:center;padding:15px}.upload-area.dragging,.upload-area:hover{background:#eaf9fa;border-color:#04aeba}.upload-glyph{height:44px;width:44px;border-radius:13px;display:grid;place-items:center;background:#dcf7f3;font-size:25px;color:#008995}.upload-area strong{font-size:13px}.upload-area span{font-size:11px;color:#829bad}.file-list{list-style:none;padding:0;max-height:150px;overflow:auto}.file-list li{display:flex;justify-content:space-between;align-items:center;padding:9px;border-bottom:1px solid #eef3f8;font-size:11px;color:#527087}.file-list button{background:none;border:0;color:#b43d46;font-size:18px;cursor:pointer}textarea{width:100%;box-sizing:border-box;resize:vertical;border:1px solid #dbe7f0;border-radius:13px;padding:16px;font-family:inherit;font-size:13px;line-height:1.7;color:#133e62;outline:0}textarea:focus{border-color:#03afbb;box-shadow:0 0 0 3px #16bbbb12}.system-capacity{display:flex;gap:11px;align-items:center;background:#eff9fc;border-radius:12px;padding:15px;margin-top:18px}.resource-icon{color:#0799a2;font-size:22px}.system-capacity strong,.system-capacity small{display:block}.system-capacity strong{font-size:12px;color:#244863}.system-capacity small{font-size:11px;color:#65849b;line-height:1.5;margin-top:4px}.start{width:100%;border:0;border-radius:12px;margin-top:20px;height:53px;background:linear-gradient(110deg,#114d91,#08bcb3);color:white;font-weight:800;font-size:14px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:10px;box-shadow:0 8px 20px #09678b22}.start:disabled{opacity:.48;cursor:default}.small-note{font-size:11px;color:#8da1af;text-align:center;margin-top:13px}.error{font-size:12px;color:#ac3131;margin-top:13px}.history-area{margin-top:34px;background:#fff;padding:24px;border-radius:18px;border:1px solid #e0ebf3}.section-h{display:flex;align-items:center;justify-content:space-between;gap:15px}.section-h span{font-size:10px;color:#098b9b;font-weight:800;letter-spacing:.15em}.section-h h2{font-size:20px;margin:6px 0}.section-h button{border:0;background:transparent;color:#0879ae;font-weight:700;cursor:pointer}
@media(max-width:1200px){.workspace-grid{grid-template-columns:1fr}.workspace-intro{min-height:unset}.steps{grid-template-columns:1fr 1fr}}@media(max-width:680px){.steps{grid-template-columns:1fr}.form-label{flex-direction:column}.history-area{padding:13px}}
 .area-input{width:100%;box-sizing:border-box;height:49px;border:1px solid #d6e4ed;border-radius:11px;padding:0 13px;font:inherit;color:#254a68;background:#fff}
.area-input:focus{outline:3px solid #15d2bd18;border-color:#0cb3b2}.area-help{font-size:11px;color:#6e8a9e;line-height:1.6;margin-top:7px}

.workspace-intro :deep(.journey){margin-top:25px}
.workspace-intro :deep(.journey-track){grid-template-columns:1fr;gap:8px}
.workspace-intro :deep(.journey-track li){padding:10px;background:#ffffff14}
.workspace-intro :deep(.journey-track small){font-size:11px}
.file-summary{font-size:11px;color:#51768c;margin:9px 0}
.upload-area:focus-visible{outline:3px solid #21c6cc;outline-offset:3px}
.prepare-checklist{margin-top:20px;padding:15px;border-radius:13px;border:1px solid #d8e9ee;background:#f7fbfc;display:grid;gap:10px}
.prepare-checklist>strong{font-size:13px;color:#20516c}
.prepare-checklist div{display:flex;align-items:center;gap:10px;color:#6b8396;font-size:12px}
.prepare-checklist div span{width:24px;height:24px;display:grid;place-items:center;border-radius:8px;background:#e9eff5;color:#617e91;font-weight:850;flex:none}
.prepare-checklist div.ready{color:#235a6e}
.prepare-checklist div.ready span{color:#0c8256;background:#d9f7e8}
.busy-note{font-size:12px;color:#98641d;background:#fff6e4;border:1px solid #f1dda7;padding:12px;line-height:1.55;border-radius:10px;margin-top:13px}
</style>
