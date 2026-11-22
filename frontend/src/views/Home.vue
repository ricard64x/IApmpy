<template>
  <TenonderaShell title="Crear una nueva simulación" subtitle="De un documento a un escenario vivo: explorá qué podría pasar." section="NUEVO ESCENARIO">
    <div class="workspace-grid">
      <section class="workspace-intro">
        <div class="intro-label">✦ INTELIGENCIA COLECTIVA</div>
        <h2>Subí tus documentos.<br><em>Explorá el futuro.</em></h2>
        <p>Tenonderã conecta información, genera agentes sintéticos y simula sus interacciones para anticipar tendencias y escenarios posibles.</p>
        <div class="steps">
          <div><span>01</span><p><strong>Documentos</strong><small>Contexto y fuentes del escenario</small></p></div>
          <div><span>02</span><p><strong>Grafo de conocimiento</strong><small>Entidades, vínculos y memoria</small></p></div>
          <div><span>03</span><p><strong>Simulación</strong><small>Agentes, acontecimientos y rondas</small></p></div>
          <div><span>04</span><p><strong>Resultados</strong><small>Informes y análisis de tendencias</small></p></div>
        </div>
        <div class="info-card">
          <span>🇵🇾</span>
          <div><strong>Simulando el futuro desde Paraguay</strong><p>Los resultados son sintéticos: exploran escenarios, no reemplazan encuestas ni datos verificables.</p></div>
        </div>
      </section>
      <section class="workspace-form">
        <div class="form-header"><span class="form-icon">◇</span><div><h3>Configurá tu escenario</h3><p>Tu proyecto se guardará de forma privada en tu cuenta.</p></div></div>
        <div class="form-group">
          <div class="form-label"><label>01 · Documentos de referencia</label><small>PDF, Markdown y TXT · Máximo 50 MB por solicitud</small></div>
          <div class="upload-area" :class="{dragging,hasFiles:files.length>0}" @dragover.prevent="dragging=true" @dragleave.prevent="dragging=false" @drop.prevent="drop" @click="pick">
            <input ref="fileInput" type="file" hidden multiple accept=".pdf,.md,.txt,.markdown" @change="select" />
            <template v-if="!files.length"><div class="upload-glyph">↑</div><strong>Arrastrá o seleccioná tus archivos</strong><span>Cargá documentos con información del escenario</span></template>
            <template v-else><div class="upload-glyph">✓</div><strong>{{files.length}} archivo(s) preparados</strong><span>Hacé clic para agregar más documentos</span></template>
          </div>
          <ul v-if="files.length" class="file-list"><li v-for="(file,index) in files" :key="index"><span>▤ {{file.name}}</span><button aria-label="Quitar archivo" @click="files.splice(index,1)">×</button></li></ul>
        </div>
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
        <div class="system-capacity">
          <span class="resource-icon">◉</span>
          <div><strong>Capacidad segura en esta máquina</strong><small>Hasta {{capacity?.recommended_max_profiles||'—'}} perfiles · {{capacity?.max_active_agents_per_platform_per_round||'—'}} agentes activos por plataforma y ronda · 1 ejecución simultánea</small></div>
        </div>
        <p v-if="error" class="error" role="alert">{{error}}</p>
        <button class="start" :disabled="!canStart||capacity?.busy" @click="start">Iniciar proyecto de simulación <span>→</span></button>
        <p class="small-note">El sistema bloqueará automáticamente una ejecución que exceda la capacidad disponible.</p>
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
import HistoryDatabase from '../components/HistoryDatabase.vue'
const router=useRouter()
const prompt=ref(''),interactionArea=ref('Paraguay'),files=ref([]),dragging=ref(false),error=ref(''),capacity=ref(null),fileInput=ref(null)
const canStart=computed(()=>files.value.length>0&&!!prompt.value.trim())
const pick=()=>fileInput.value?.click()
function addFiles(collection){
  error.value=''
  for(const file of collection) {
    if(!/\.(pdf|md|markdown|txt)$/i.test(file.name)){error.value='Formato no admitido: '+file.name;continue}
    if(!files.value.some(f=>f.name===file.name&&f.size===file.size))files.value.push(file)
  }
}
function select(event){addFiles(Array.from(event.target.files||[]));event.target.value=''}
function drop(event){dragging.value=false;addFiles(Array.from(event.dataTransfer.files||[]))}
function start(){
  if(!canStart.value||capacity.value?.busy)return
  const scope = interactionArea.value.trim()
  const requirement = scope
    ? prompt.value.trim() + '\n\nÁmbito territorial de interacción de los agentes: ' + scope + '. Considerá este contexto al crear sus perfiles y simular las conversaciones.'
    : prompt.value.trim()
  setPendingUpload(files.value,requirement)
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
</style>
