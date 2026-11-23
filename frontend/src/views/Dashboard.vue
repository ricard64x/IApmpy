<template>
  <TenonderaShell :title="isAdmin ? 'Hola, Administrador' : 'Hola, ' + (activeUser?.name || 'bienvenido')" subtitle="Tus escenarios, usuarios y capacidad operativa, en un solo lugar." :section="isAdmin ? 'ADMINISTRACIÓN' : 'MIS SIMULACIONES'">
    <div class="top-strip"><span><i></i> Tu espacio privado · proyectos y versiones guardadas</span><div class="account-actions"><button class="account-password" type="button" @click="router.push('/cambiar-clave')">Cambiar mi contraseña</button><button class="text-btn" type="button" :disabled="loadingData" @click="loadData">{{loadingData?'Actualizando…':'↻ Actualizar datos'}}</button></div></div>
    <section class="dashboard-hero" aria-label="Acciones recomendadas">
      <div class="hero-copy">
        <span class="hero-eyebrow">TU PRÓXIMA ACCIÓN</span>
        <h2>{{nextEntry?'Continuá donde quedaste':'Tu primera simulación comienza acá'}}</h2>
        <p v-if="nextEntry" class="hero-project">{{friendlyProjectName(nextEntry.project_name,nextEntry.simulation_requirement,nextEntry.project_id)}}</p>
        <p>{{nextEntry?dashboardNextAction(nextEntry).detail:'Elegí una pregunta, agregá documentos y prepará un escenario de conversaciones. Te acompañamos durante todo el proceso.'}}</p>
        <div class="hero-buttons">
          <button v-if="nextEntry" type="button" class="hero-primary" @click="openNext(nextEntry)">
            {{dashboardNextAction(nextEntry).label}} <span aria-hidden="true">→</span>
          </button>
          <button type="button" :class="nextEntry?'hero-secondary':'hero-primary'" @click="router.push('/workspace')">
            ＋ Crear nueva simulación
          </button>
        </div>
      </div>
      <div class="hero-side">
        <span class="hero-side-kicker">EN QUÉ PASO ESTÁS</span>
        <strong>{{nextEntry?String(dashboardNextAction(nextEntry).stage).padStart(2,'0'):'01'}} <small>/ 05</small></strong>
        <span>{{nextEntry?journeyStepName(dashboardNextAction(nextEntry).stage):'Objetivo y documentos'}}</span>
        <p>{{nextEntry?'Tu próximo paso se determina a partir del estado guardado, no de un progreso estimado.':'La guía muestra lo que ocurrirá antes de empezar.'}}</p>
      </div>
    </section>
    <SimulationJourney :current-step="nextEntry?dashboardNextAction(nextEntry).stage:0" />

    <section class="stat-grid" aria-label="Resumen de proyectos guardados">
      <article class="stat-card"><span class="stat-icon blue">▤</span><div class="stat-label">Proyectos visibles</div><strong>{{summary.projects}}</strong><span class="stat-foot">Incluye proyectos en preparación</span></article>
      <article class="stat-card"><span class="stat-icon teal">▶</span><div class="stat-label">Simulaciones en curso</div><strong>{{summary.running}}</strong><span class="stat-foot">Ejecuciones registradas como activas</span></article>
      <article class="stat-card"><span class="stat-icon purple">▣</span><div class="stat-label">Con informe guardado</div><strong>{{summary.reports}}</strong><span class="stat-foot">Proyectos con un informe vinculado</span></article>
      <article class="stat-card"><span class="stat-icon green">◇</span><div class="stat-label">Por continuar o revisar</div><strong>{{summary.pending}}</strong><span class="stat-foot">Aún no tienen informe final vinculado</span></article>
    </section>

    <section class="middle-grid">
      <article class="panel capacity">
        <div class="panel-heading"><span class="title-icon">◉</span><div><h2>¿Cuántos participantes puedo usar?</h2><p>Depende del motor elegido; no hay un único límite para todos los escenarios.</p></div></div>
        <div class="engine-comparison">
          <div class="engine-card">
            <div class="engine-head"><strong>Modo eficiente</strong><span :class="capacity?.lightweight_engine_available?'enabled':'unavailable'">{{capacity?'Motor '+(capacity.lightweight_engine_available?'disponible':'no configurado'):'Consultando'}}</span></div>
            <div class="engine-number">{{capacity?.lightweight_max_profiles??'—'}} <small>máximo técnico</small></div>
            <p>Personajes configurables y conversaciones por lotes. Empezá con 5 a 10 participantes para revisar la calidad.</p>
          </div>
          <div class="engine-card legacy">
            <div class="engine-head"><strong>Motor social completo</strong><span>Experimental</span></div>
            <div class="engine-number">{{capacity?.recommended_max_profiles??'—'}} <small>límite conservador</small></div>
            <p>Puede consumir mucha memoria incluso con pocos participantes. No agrega personajes fuera de los perfiles detectados.</p>
          </div>
        </div>
        <p class="capacity-explain">Los límites no garantizan estabilidad. La cantidad activa por ronda y el consumo real son distintos de la población total. La selección definitiva se hace en <strong>Preparar entorno</strong>.</p>
      </article>
      <article class="panel resources">
        <div class="panel-heading"><span class="title-icon">▤</span><div><h2>Recursos disponibles</h2><p>Estado actual de la infraestructura</p></div></div>
        <div class="resource-head"><strong>{{capacity?.memory_used_mb ?? '—'}} MB</strong><span>de {{capacity?.machine_memory_mb||'—'}} MB</span></div>
        <div class="progress-track"><div :style="{width:memoryPercent+'%'}"></div></div>
        <p class="resource-tip">Memoria utilizada (estimada). La disponibilidad puede variar durante una simulación.</p>
        <div class="resource-status" :class="{busy:capacity?.busy}"><span>{{capacity?.busy?'◉':'✓'}}</span>{{capacity?.busy?'Hay una simulación ejecutándose':'No se detecta una simulación activa'}}</div>
        <p class="resource-tip">{{capacity?.busy?'Podés revisar proyectos e informes, pero no iniciar otra ejecución hasta liberar recursos.':'Solo se ejecuta una simulación a la vez. La capacidad se comprueba nuevamente antes del inicio.'}}</p>
        <div v-if="!capacity" class="capacity-loading">No se pudo confirmar la capacidad en esta lectura. <button type="button" @click="loadData">Reintentar</button></div>
      </article>
    </section>

    <section class="bottom-grid" :class="{'single-column':!isAdmin}">
      <article v-if="isAdmin" class="panel users-panel">
        <div class="table-top"><div><h2>Usuarios y sus simulaciones</h2><p>Solo vos podés crear cuentas o modificar sus permisos.</p></div><button class="add-user" @click="showUserForm=true">＋ Crear usuario</button></div>
        <div class="search"><span>⌕</span><input v-model="search" placeholder="Buscar usuario…"/></div>
        <div class="table-scroll"><table><thead><tr><th>Usuario</th><th>Perfil</th><th>Simulaciones</th><th>Estado</th><th></th></tr></thead>
          <tbody><tr v-for="person in filteredUsers" :key="person.id">
            <td><div class="person"><span class="initial">{{person.name[0]?.toUpperCase()}}</span><div><strong>{{person.name}}</strong><small>{{person.username}}</small></div></div></td>
            <td><span class="role-tag" :class="person.role">{{roleText(person.role)}}</span></td>
            <td>{{person.simulation_count||0}}</td>
            <td><span class="status" :class="{inactive:!person.active}">{{person.active?'Activo':'Suspendido'}}</span></td>
            <td><button v-if="person.role!=='administrator'" class="text-btn" @click="editUser(person)">Gestionar</button><span v-else class="owner-tag">Propietario</span></td>
          </tr></tbody>
        </table></div><div v-if="!users.length" class="empty">Todavía no hay otros usuarios registrados.</div>
      </article>

      <article class="panel simulations-panel" id="mis-proyectos">
        <div class="table-top"><div><h2>{{isAdmin?'Proyectos y simulaciones guardados':'Mis escenarios'}}</h2><p>Elegí un escenario para continuar exactamente desde el último paso guardado.</p></div><button class="text-btn" :disabled="loadingData" @click="loadData">↻ Actualizar</button></div>
        <div class="project-filters">
          <label class="project-search"><span aria-hidden="true">⌕</span><input v-model.trim="projectQuery" aria-label="Buscar escenarios" placeholder="Buscar por nombre u objetivo…"/></label>
          <div class="filter-tabs" role="group" aria-label="Filtrar escenarios">
            <button v-for="tab in stageTabs" :key="tab.id" type="button" :class="{active:stageFilter===tab.id}" :aria-pressed="stageFilter===tab.id" @click="stageFilter=tab.id">{{tab.title}}</button>
          </div>
        </div>
        <div v-if="isAdmin&&users.length" class="owner-filter"><label for="owner-filter">Filtrar por usuario</label><select id="owner-filter" v-model="selectedOwner"><option value="">Todos</option><option v-for="p in users" :key="p.id" :value="p.id">{{p.name}}</option></select></div>
        <p v-if="historyError" class="history-error" role="alert">{{historyError}}</p>
        <div class="simulation-list">
          <article v-for="item in filteredHistory" :key="item.simulation_id || item.project_id" class="simulation-item">
            <div class="simulation-icon" aria-hidden="true">{{statusClass(item)==='failed'?'⚠':'◇'}}</div>
            <div class="simulation-info">
              <strong>{{friendlyProjectName(item.project_name,item.simulation_requirement,item.project_id)}}</strong>
              <small>{{personName(item.owner_id)}} · {{(item.created_at||'').slice(0,10)}} · {{item.simulation_id ? (item.total_rounds||0)+' rondas previstas o registradas' : 'Sin ejecución iniciada'}}</small>
              <p class="next-hint"><b>Paso {{dashboardNextAction(item).stage}}:</b> {{dashboardNextAction(item).detail}}</p>
              <div v-if="liveProgress[item.project_id]" class="project-live-inline" :aria-label="progressLabel(liveProgress[item.project_id])">
                <span>{{progressLabel(liveProgress[item.project_id])}}</span>
                <div class="project-live-track"><div :style="{width:Math.min(100,Math.max(0,Number(liveProgress[item.project_id].percent)||0))+'%'}"></div></div>
                <small>{{unavailable[item.project_id] ? 'Última lectura conservada · comprobando conexión' : 'Avance registrado · actualización automática cada 15 segundos'}}</small>
              </div>
            </div>
            <span class="run-pill" :class="statusClass(item)">{{liveProgress[item.project_id] ? progressLabel(liveProgress[item.project_id]) : statusText(item)}}</span>
            <div class="simulation-actions">
              <button class="next-action" type="button" @click="openNext(item)">{{dashboardNextAction(item).label}} <span aria-hidden="true">→</span></button>
              <button class="text-btn" v-if="item.project_id" @click="router.push('/historial?project='+encodeURIComponent(item.project_id))">Versiones</button>
              <button class="text-btn" v-if="item.project_id" @click="rename(item)">Renombrar</button>
            </div>
          </article>
          <div v-if="!filteredHistory.length" class="empty">
            <p>{{visibleHistory.length?'No hay escenarios que coincidan con esos filtros.':'Todavía no hay proyectos guardados.'}}</p>
            <button type="button" v-if="visibleHistory.length" class="clear-filters" @click="stageFilter='all';projectQuery=''">Mostrar todos</button>
            <button type="button" v-else class="new-action" @click="router.push('/workspace')">Crear mi primer escenario</button>
          </div>
        </div>
        <button class="secondary-action" @click="router.push('/historial')">Consultar historial completo y reportes →</button>
      </article>
    </section>

    <div v-if="showUserForm" class="modal-backdrop" @click.self="showUserForm=false">
      <form class="modal" @submit.prevent="submitUser"><button class="modal-close" type="button" @click="showUserForm=false">×</button>
        <span class="modal-eyebrow">ADMINISTRACIÓN DE ACCESOS</span><h2>Crear usuario</h2><p>Las cuentas no pueden registrarse por su cuenta. El administrador define el rol y la contraseña temporal.</p>
        <label for="new-name">Nombre visible</label><input id="new-name" v-model.trim="newUser.name" required placeholder="Nombre y apellido"/>
        <label for="new-username">Usuario o correo</label><input id="new-username" v-model.trim="newUser.username" required placeholder="usuario@empresa.com"/>
        <label for="new-role">Perfil</label><select id="new-role" v-model="newUser.role"><option value="analyst">Analista</option><option value="researcher">Investigador</option></select>
        <label for="new-pass">Contraseña temporal (mínimo 12 caracteres)</label><input id="new-pass" v-model="newUser.password" type="password" minlength="12" required autocomplete="new-password"/>
        <p v-if="modalError" class="error" role="alert">{{modalError}}</p>
        <button class="modal-submit" :disabled="saving" type="submit">{{saving?'Guardando…':'Crear cuenta y habilitar acceso'}}</button>
      </form>
    </div>
    <div v-if="editingUser" class="modal-backdrop" @click.self="editingUser=null">
      <form class="modal" @submit.prevent="submitEdit"><button class="modal-close" type="button" @click="editingUser=null">×</button>
        <span class="modal-eyebrow">GESTIÓN DE USUARIOS</span><h2>{{editingUser.name}}</h2><p>{{editingUser.username}}</p>
        <label for="edit-role">Perfil</label><select id="edit-role" v-model="editRole"><option value="analyst">Analista</option><option value="researcher">Investigador</option></select>
        <label class="checkbox-label"><input type="checkbox" v-model="editActive"/> Usuario habilitado</label>
        <label for="edit-pass">Nueva contraseña temporal (opcional)</label><input id="edit-pass" type="password" v-model="editPassword" placeholder="Dejar vacío para conservar" autocomplete="new-password"/>
        <p v-if="modalError" class="error" role="alert">{{modalError}}</p>
        <button class="modal-submit" :disabled="saving" type="submit">{{saving?'Guardando…':'Guardar cambios'}}</button>
      </form>
    </div>
  </TenonderaShell>
</template>
<script setup>
import {computed,onMounted,reactive,ref} from 'vue'
import {useRouter} from 'vue-router'
import TenonderaShell from '../components/TenonderaShell.vue'
import SimulationJourney from '../components/SimulationJourney.vue'
import {dashboardNextAction,dashboardBucket,dashboardCounts,JOURNEY_STEPS} from '../utils/dashboardJourney'
import {activeUser} from '../api/auth'
import service from '../api'
import {mergeProjectHistory, projectEntryStatus, friendlyProjectName} from '../utils/projectHistory'
import {useLiveProjectProgress,progressLabel} from '../composables/useLiveProjectProgress'
const router=useRouter()
const isAdmin=computed(()=>activeUser.value?.role==='administrator')
const roleLabel=computed(()=>roleText(activeUser.value?.role))
const users=ref([]),history=ref([]),savedProjects=ref([]),capacity=ref(null),historyError=ref('')
const stageFilter=ref('all'),projectQuery=ref(''),loadingData=ref(false)
const stageTabs=[{id:'all',title:'Todos'},{id:'preparing',title:'En preparación'},{id:'running',title:'En curso'},{id:'report',title:'Con informe'},{id:'attention',title:'Revisar'}]
const journeyStepName=n=>JOURNEY_STEPS[n-1]?.short || 'Preparación'
const search=ref(''),selectedOwner=ref(''),showUserForm=ref(false),editingUser=ref(null)
const editRole=ref('analyst'),editActive=ref(true),editPassword=ref('')
const saving=ref(false),modalError=ref('')
const newUser=reactive({name:'',username:'',role:'analyst',password:''})
const roleText=r=>({administrator:'Administrador',analyst:'Analista',researcher:'Investigador'}[r]||'Usuario')
const personName=id=>isAdmin.value?(users.value.find(u=>u.id===id)?.name||'Administrador'):'Mi espacio'
const memoryPercent=computed(()=>capacity.value?.memory_used_mb&&capacity.value.machine_memory_mb?Math.min(100,Math.round(100*capacity.value.memory_used_mb/capacity.value.machine_memory_mb)):0)
const filteredUsers=computed(()=>users.value.filter(u=>(u.name+' '+u.username).toLowerCase().includes(search.value.toLowerCase())))
const visibleHistory=computed(()=>mergeProjectHistory(savedProjects.value,history.value).filter(s=>!isAdmin.value||!selectedOwner.value||s.owner_id===selectedOwner.value))
const summary=computed(()=>dashboardCounts(visibleHistory.value))
const filteredHistory=computed(()=>visibleHistory.value.filter(item=>{
  if(stageFilter.value!=='all'&&dashboardBucket(item)!==stageFilter.value)return false
  const needle=projectQuery.value.toLocaleLowerCase()
  return !needle || [item.project_name,item.simulation_requirement,item.project_id,item.simulation_id].some(v=>String(v||'').toLocaleLowerCase().includes(needle))
}))
const nextEntry=computed(()=>visibleHistory.value.find(item=>dashboardBucket(item)==='running')
  || visibleHistory.value.find(item=>dashboardBucket(item)==='attention')
  || visibleHistory.value.find(item=>dashboardBucket(item)==='preparing')
  || visibleHistory.value[0] || null)
const openNext=item=>router.push(dashboardNextAction(item).to)
const {liveProgress,unavailable} = useLiveProjectProgress(visibleHistory)
const brief=s=>typeof s==='string'?s.slice(0,54):''
const statusText=s=>projectEntryStatus(s).label
const statusClass=s=>projectEntryStatus(s).style
async function loadData(){
  if(loadingData.value)return
  loadingData.value=true
  historyError.value=''
  const requests=[service.get('/api/capacity/status'),service.get('/api/simulation/history',{params:{limit:100}}),service.get('/api/graph/project/list',{params:{limit:200}})]
  if(isAdmin.value)requests.push(service.get('/api/auth/users'))
  const results=await Promise.allSettled(requests)
  if(results[0].status==='fulfilled')capacity.value=results[0].value.data
  if(results[1].status==='fulfilled')history.value=results[1].value.data||[]
  else history.value=[]
  if(results[2].status==='fulfilled')savedProjects.value=results[2].value.data||[]
  else savedProjects.value=[]
  if(results[1].status==='rejected'||results[2].status==='rejected') {
    historyError.value='No se pudo cargar todo el historial. Volvé a intentar.'
  }
  if(results[3]?.status==='fulfilled')users.value=results[3].value.data||[]
  loadingData.value=false
}
async function submitUser(){
  saving.value=true;modalError.value=''
  try{await service.post('/api/auth/users',{...newUser});showUserForm.value=false;Object.assign(newUser,{name:'',username:'',role:'analyst',password:''});await loadData()}
  catch(e){modalError.value=e.message}
  finally{saving.value=false}
}
function editUser(person){editingUser.value=person;editRole.value=person.role;editActive.value=!!person.active;editPassword.value='';modalError.value=''}
async function submitEdit(){
  saving.value=true;modalError.value=''
  try{
    const payload={role:editRole.value,active:editActive.value}
    if(editPassword.value)payload.password=editPassword.value
    await service.patch('/api/auth/users/'+encodeURIComponent(editingUser.value.id),payload)
    editingUser.value=null;editPassword.value='';await loadData()
  }catch(e){modalError.value=e.message}
  finally{saving.value=false}
}
async function rename(item) {
  const current = friendlyProjectName(item.project_name,item.simulation_requirement,item.project_id)
  const requested = window.prompt('Nombre del proyecto (máximo 100 caracteres):', current)
  if (requested === null || !requested.trim()) return
  try {
    await service.patch('/api/graph/project/'+encodeURIComponent(item.project_id)+'/name', {name:requested.trim().slice(0,100)})
    await loadData()
  } catch (e) { historyError.value = e.message || 'No se pudo guardar el nombre' }
}
function openSimulation(s){
  if(s.report_id)router.push('/report/'+s.report_id)
  else if(s.simulation_id)router.push('/simulation/'+s.simulation_id)
  else if(s.project_id)router.push('/process/'+s.project_id)
}
onMounted(loadData)
</script>
<style scoped>
.top-strip{display:flex;align-items:center;justify-content:space-between;gap:15px;margin-bottom:23px;color:#436d83;font-size:13px;font-weight:600}.top-strip i{display:inline-block;width:8px;height:8px;border-radius:50%;background:#16c894;margin-right:7px}
.new-action,.add-user,.modal-submit{border:0;background:linear-gradient(105deg,#0c488c,#0bbcb3);color:white;font-weight:750;border-radius:12px;padding:13px 18px;cursor:pointer;box-shadow:0 8px 17px #065eae1d}.new-action:hover,.add-user:hover,.modal-submit:hover{filter:brightness(1.06)}
.stat-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:17px;margin-bottom:22px}.stat-card,.panel{border:1px solid #e0eaf2;background:#fff;border-radius:18px;box-shadow:0 6px 22px #0d346009}.stat-card{padding:20px;min-height:142px;position:relative}.stat-icon{display:grid;place-items:center;width:40px;height:40px;border-radius:12px;font-size:23px;margin-bottom:12px}.stat-icon.blue{color:#1177d0;background:#ebf4ff}.stat-icon.teal{color:#00a69c;background:#e9faf7}.stat-icon.purple{color:#7668d3;background:#f2f0ff}.stat-icon.green{color:#08a77c;background:#e8fbf3}.stat-label{font-size:12px;color:#617b97;font-weight:700}.stat-card strong{font-size:30px;line-height:1.2;display:block;margin:7px 0 4px;letter-spacing:-.045em}.stat-card small{font-size:12px}.stat-foot{font-size:11px;color:#8192aa}.middle-grid{display:grid;grid-template-columns:1.42fr 1fr;gap:20px;margin-bottom:23px}.panel{padding:24px}.panel-heading{display:flex;gap:12px;align-items:flex-start}.title-icon{width:37px;height:37px;border-radius:10px;background:#edf8fc;color:#047b9a;font-size:23px;display:grid;place-items:center;flex-shrink:0}.panel h2{font-size:17px;margin:2px 0 7px;letter-spacing:-.02em}.panel p{font-size:12px;color:#6d819a;line-height:1.55}.tier-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:23px 0 17px}.tier{border-radius:12px;padding:15px 11px;display:flex;flex-direction:column;gap:5px}.tier strong{font-size:22px;letter-spacing:-.04em}.tier span{font-weight:780;font-size:12px}.tier small{font-size:10px;color:#638394}.tier-green{background:#e3f9ed;color:#0b7949}.tier-blue{background:#e7f3ff;color:#165fb5}.tier-purple{background:#f0edff;color:#6350a9}.capacity-note{display:flex;gap:12px;align-items:flex-start;background:#fff9ec;border:1px solid #f5e7c8;border-radius:12px;padding:13px}.capacity-note>span{font-size:18px;color:#c77e05}.capacity-note p{color:#785b2b;margin:0}.capacity-note strong{color:#3f3e32}.resource-head{display:flex;justify-content:space-between;align-items:baseline;margin:30px 0 10px}.resource-head strong{font-size:23px;letter-spacing:-.04em}.resource-head span{font-size:12px;color:#7a8da0}.progress-track{height:10px;background:#e8f0f8;border-radius:100px;overflow:hidden}.progress-track div{background:linear-gradient(90deg,#1357bc,#15c5cd);height:100%;border-radius:100px;transition:width .4s}.resource-tip{margin-top:10px}.resource-status{background:#e5f9ec;color:#11774a;border-radius:11px;padding:13px;margin-top:22px;font-weight:750;font-size:12px}.resource-status.busy{background:#fff1df;color:#9c650e}.resource-status span{margin-right:7px}.algorithm{font-size:11px;color:#7690a2;margin-top:16px}.bottom-grid{display:grid;grid-template-columns:1.35fr 1fr;gap:20px}.bottom-grid.single-column{grid-template-columns:1fr}.table-top{display:flex;justify-content:space-between;align-items:flex-start;gap:15px}.table-top h2{font-size:17px}.add-user{font-size:12px;white-space:nowrap}.search{border:1px solid #e1ecf2;border-radius:10px;display:flex;gap:10px;padding:9px 13px;margin:18px 0}.search span{font-size:20px;color:#64809b}.search input{width:100%;border:0;outline:0;font:inherit;font-size:13px}.table-scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:515px;margin-top:14px}th{text-align:left;color:#6f859d;background:#f6f9fc;padding:12px 8px;font-size:10px;font-weight:750}td{border-bottom:1px solid #eef3f8;padding:14px 8px;font-size:12px;color:#3c5871}.person{display:flex;align-items:center;gap:10px}.initial{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(130deg,#347fd7,#07a6bf);color:#fff;font-weight:800}.person strong,.person small{display:block}.person strong{color:#233b57;font-size:11px}.person small{color:#8ba0b2;font-size:10px;margin-top:3px}.role-tag,.status{font-size:10px;font-weight:750;padding:6px 9px;border-radius:100px;display:inline-block}.role-tag.administrator{background:#eae7ff;color:#6755bc}.role-tag.analyst{background:#e5f0ff;color:#2e65bd}.role-tag.researcher{background:#e4f9f7;color:#058778}.status{background:#dcfae8;color:#0e8149}.status.inactive{background:#feeaea;color:#aa4242}.owner-tag{font-size:10px;color:#8a9cae}.text-btn,.link-open{border:0;background:none;color:#1175c4;font-weight:750;font-size:12px;cursor:pointer}.text-btn:hover{text-decoration:underline}.owner-filter{display:flex;align-items:center;gap:9px;margin:18px 0}.owner-filter label{color:#6d8195;font-size:11px}.owner-filter select{border:1px solid #d9e7f0;padding:7px;border-radius:8px;color:#295078;background:#fff}.simulation-list{margin-top:20px;display:grid;gap:11px}.simulation-item{display:flex;align-items:center;gap:10px;padding:12px;border:1px solid #ecf1f7;border-radius:12px;background:#fbfdff}.simulation-icon{width:37px;height:37px;display:grid;place-items:center;border-radius:10px;background:#ebf4ff;color:#1769b6;flex-shrink:0;font-size:20px}.simulation-info{flex:1;min-width:0}.simulation-info strong{display:block;font-size:12px;color:#223a56;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.simulation-info small{font-size:10px;color:#8a9dab;line-height:1.6;display:block}.run-pill{font-size:10px;font-weight:750;padding:6px 9px;border-radius:100px;background:#e8f0ff;color:#3b73b4;white-space:nowrap}.run-pill.failed{background:#ffebeb;color:#a83f46}.run-pill.running{background:#e6f3ff;color:#146ec8}.run-pill.completed{background:#e0fbed;color:#11794d}.link-open{font-size:19px}.secondary-action{padding:12px 0;border:0;background:none;color:#1176bf;font-weight:750;font-size:12px;cursor:pointer;margin-top:17px}.empty{padding:35px 12px;text-align:center;color:#7994aa;font-size:13px}.modal-backdrop{position:fixed;inset:0;background:#08254a96;z-index:80;display:grid;place-items:center;padding:20px}.modal{width:min(100%,500px);padding:32px;background:white;border-radius:20px;box-shadow:0 20px 80px #031a3960;display:grid;gap:10px;max-height:95vh;overflow:auto;position:relative}.modal-close{position:absolute;top:15px;right:18px;border:0;background:transparent;color:#66849a;font-size:26px;cursor:pointer}.modal-eyebrow{font-size:10px;letter-spacing:.17em;color:#039da7;font-weight:800}.modal h2{margin:8px 0 0;font-size:28px}.modal p{font-size:12px;color:#647c92;line-height:1.6;margin:0 0 7px}.modal label{font-size:12px;font-weight:700;color:#2b506d;margin-top:6px}.modal input,.modal select{border:1px solid #d6e4ef;border-radius:10px;min-height:46px;padding:8px 12px;outline:none;font:inherit;font-size:13px}.modal input:focus,.modal select:focus{border-color:#0ab9c0;box-shadow:0 0 0 3px #0cc7bc19}.modal-submit{margin-top:12px;min-height:48px}.modal .error{background:#ffeaea;color:#a43c3c;padding:12px}.checkbox-label{display:flex;align-items:center;gap:9px}.checkbox-label input{min-height:unset}
@media(max-width:1250px){.middle-grid,.bottom-grid{grid-template-columns:1fr}.stat-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:680px){.stat-grid{grid-template-columns:1fr 1fr;gap:10px}.stat-card{padding:14px}.tier-row{grid-template-columns:1fr 1fr}.top-strip{align-items:flex-start;flex-direction:column}.panel{padding:16px}.table-top{flex-direction:column}.stat-card strong{font-size:25px}}
.history-error{color:#a03838;font-size:12px;margin-top:12px}
.project-live-inline{display:grid;gap:5px;margin-top:7px;color:#216f81;font-size:11px;font-weight:700}
.project-live-inline small{font-size:10px}
.project-live-track{background:#dfedf3;height:6px;border-radius:9px;overflow:hidden;max-width:440px}
.project-live-track div{height:100%;border-radius:9px;background:linear-gradient(90deg,#1166b0,#13aa99);transition:width .6s ease}
.account-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.account-password{border:1px solid #c8e0eb;border-radius:10px;background:#fff;color:#145679;font-size:12px;font-weight:750;padding:10px 13px;cursor:pointer}
.account-password:hover{background:#eef8fc}
@media(max-width:680px){.top-strip{flex-wrap:wrap}.account-actions{width:100%}.account-actions button{flex:1}}

/* Keep the dashboard inside its shell at common laptop and mobile widths. */
.stat-grid,.middle-grid,.bottom-grid,.panel,.simulation-list{min-width:0;max-width:100%}
.panel{overflow-wrap:anywhere}
.simulations-panel,.users-panel{min-width:0}
.simulation-item{min-width:0;flex-wrap:wrap}
.simulation-info{min-width:min(190px,100%);overflow-wrap:anywhere}
.run-pill{max-width:100%;white-space:normal;overflow-wrap:anywhere}
.owner-filter{flex-wrap:wrap}
.owner-filter select{max-width:100%;min-width:0}
@media(max-width:900px){
  .stat-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .middle-grid,.bottom-grid{grid-template-columns:minmax(0,1fr)}
}
@media(max-width:480px){
  .stat-grid,.tier-row{grid-template-columns:minmax(0,1fr)}
  .simulation-item{align-items:flex-start}
  .run-pill{order:3}
}

/* Guided scenario dashboard: act first, inspect technical capacity second. */
.dashboard-hero{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(200px,.6fr);gap:18px;align-items:stretch;padding:clamp(20px,3vw,32px);background:linear-gradient(118deg,#093a70 0%,#075c7e 68%,#087c83 100%);border-radius:20px;color:#fff;margin:0 0 17px;box-shadow:0 12px 28px #154c811a}
.hero-copy{min-width:0}
.hero-eyebrow,.hero-side-kicker{font-size:10px;letter-spacing:.15em;color:#92e8e3;font-weight:850}
.dashboard-hero h2{font-size:clamp(23px,2.9vw,34px);line-height:1.2;letter-spacing:-.035em;margin:9px 0 12px}
.dashboard-hero p{font-size:13px;line-height:1.65;color:#d7eff6;max-width:690px;margin:0 0 12px}
.dashboard-hero .hero-project{font-weight:800;font-size:15px;color:white;margin-bottom:6px;overflow-wrap:anywhere}
.hero-buttons{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}
.hero-buttons button{min-height:47px;border-radius:11px;padding:10px 17px;font-size:13px;font-weight:850;cursor:pointer}
.hero-primary{border:1px solid #fff;background:white;color:#104875}
.hero-secondary{border:1px solid #ffffff6e;background:#ffffff12;color:#fff}
.hero-buttons button:hover{filter:brightness(.95)}
.hero-buttons button:focus-visible,.project-filters button:focus-visible,.next-action:focus-visible{outline:3px solid #7cf2e4;outline-offset:2px}
.hero-side{display:flex;flex-direction:column;justify-content:center;border-left:1px solid #ffffff38;padding:15px 5px 15px 22px;min-width:0}
.hero-side strong{font-size:48px;line-height:1.1;letter-spacing:-.06em;margin-top:8px}
.hero-side strong small{font-size:17px;color:#a9dce7}
.hero-side>span:not(.hero-side-kicker){font-size:14px;font-weight:800}
.hero-side p{font-size:11px;margin-top:12px;margin-bottom:0}
.stat-grid{margin-top:22px}
.engine-comparison{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px;margin:17px 0}
.engine-card{border:1px solid #bfe1e8;background:#f0fafb;border-radius:14px;padding:15px;min-width:0}
.engine-card.legacy{background:#f8fafc;border-color:#e1eaf2}
.engine-head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;flex-wrap:wrap}
.engine-head strong{font-size:13px;color:#174e67}
.engine-head span{font-size:10px;color:#777d94;border:1px solid #d3e1e7;background:#fff;padding:5px 7px;border-radius:100px}
.engine-head .enabled{color:#11714c;background:#e1f8e9}
.engine-head .unavailable{color:#a45130;background:#fff3eb}
.engine-number{font-size:32px;letter-spacing:-.05em;font-weight:850;color:#145b7b;margin:11px 0 7px}
.engine-number small{font-size:11px;color:#617e91;letter-spacing:0;font-weight:600}
.engine-card p{line-height:1.55;color:#5b7589;margin:0}
.panel .capacity-explain{font-size:11px;color:#516e84;line-height:1.65;padding:10px 12px;border-left:3px solid #0b9ca5;background:#f1f8fc;margin:0}
.capacity-loading{padding:10px;color:#9d6538;font-size:11px;background:#fff5ea;border-radius:9px;margin-top:10px}
.capacity-loading button{border:0;background:transparent;font-weight:750;color:#176d92;text-decoration:underline;cursor:pointer}
.project-filters{margin-top:18px;display:grid;gap:12px}
.project-search{border:1px solid #d9e7ed;border-radius:10px;background:#fff;display:flex;gap:9px;align-items:center;padding:8px 12px;max-width:100%}
.project-search span{font-size:23px;color:#59829a}
.project-search input{border:0;outline:0;width:100%;min-width:0;font:inherit;font-size:13px;color:#23475d}
.filter-tabs{display:flex;gap:7px;overflow-x:auto;padding:2px 0 7px;scrollbar-width:thin}
.filter-tabs button{border:1px solid #d8e6ee;background:#f8fbfd;color:#41677d;border-radius:999px;white-space:nowrap;min-height:38px;padding:8px 12px;font-size:11px;font-weight:750;cursor:pointer}
.filter-tabs button.active{background:#115d82;border-color:#115d82;color:#fff}
.simulation-item{gap:12px;padding:15px}
.simulation-info strong{font-size:13px}
.simulation-info .next-hint{margin:8px 0 0;font-size:11px;color:#4d7189;line-height:1.55}
.next-hint b{color:#185c7e}
.simulation-actions{display:flex;flex-wrap:wrap;gap:9px;align-items:center;width:100%;border-top:1px solid #edf2f7;padding-top:11px}
.next-action{border:1px solid #0c7394;background:#0d7092;color:#fff;border-radius:9px;padding:9px 13px;font:800 12px system-ui,sans-serif;cursor:pointer;min-height:40px}
.next-action:hover{background:#085a79}
.simulation-actions .text-btn{min-height:38px;padding:8px}
.clear-filters{background:#ebf7f9;border:1px solid #bad9e2;padding:10px 14px;border-radius:10px;font-weight:750;color:#145e7a;cursor:pointer}
@media(max-width:980px){.dashboard-hero{grid-template-columns:1fr}.hero-side{border-left:0;border-top:1px solid #ffffff38;padding:14px 0 0}.hero-side strong{font-size:35px}}
@media(max-width:620px){
 .dashboard-hero{padding:19px}
 .hero-buttons{display:grid}
 .hero-buttons button{width:100%}
 .engine-comparison{grid-template-columns:1fr}
 .project-filters{gap:10px}
 .simulation-actions{display:grid;grid-template-columns:1fr 1fr}
 .simulation-actions .next-action{grid-column:1/-1}
 .simulation-item{display:grid;grid-template-columns:38px minmax(0,1fr)}
 .simulation-info{min-width:0}
 .run-pill{grid-column:2;justify-self:start}
 .simulation-actions{grid-column:1/-1}
 .top-strip{flex-wrap:wrap}
 .account-actions{display:flex;flex-wrap:wrap;gap:10px}
}

</style>
