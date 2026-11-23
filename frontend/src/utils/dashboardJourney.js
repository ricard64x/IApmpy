/**
 * One truthful next action for each saved project. This module never infers
 * an unsaved report, an actual conversation, or a completed preparation step.
 * The API already filters resources by the authenticated account.
 */
export const JOURNEY_STEPS = Object.freeze([
  {number:1,title:'Prepará fuentes y mapa',short:'Objetivo, documentos y relaciones',description:'Cargá documentos, definí tu objetivo y revisá el mapa de relaciones.'},
  {number:2,title:'Configurá participantes',short:'Personajes, espacios y rondas',description:'Elegí cuántos personajes intervienen, dónde conversan y sus rondas.'},
  {number:3,title:'Ejecutá conversaciones',short:'Debates e interacciones',description:'Observá mensajes, respuestas y avance real del escenario.'},
  {number:4,title:'Generá el informe',short:'Síntesis y calidad',description:'Verificá la calidad de la interacción y generá el resultado documentado.'},
  {number:5,title:'Explorá los resultados',short:'Grafo, consultas y decisiones',description:'Consultá intercambios, redes de participantes y conclusiones con su contexto.'},
])

const makeUrl = (kind,id)=>`/${kind}/${encodeURIComponent(String(id))}`
const preparation = item => {
  const status=item?.project_status
  if(status==='graph_completed') return {stage:2,label:'Preparar participantes',detail:'El mapa está listo; revisá personajes y configurá la conversación.'}
  if(status==='ontology_generated') return {stage:1,label:'Construir el mapa',detail:'Se preparó la estructura de información. Revisá las relaciones y continuá.'}
  if(status==='graph_building') return {stage:1,label:'Ver progreso',detail:'El mapa de relaciones se está construyendo. El avance aparece en el proyecto.'}
  if(status==='failed') return {stage:1,label:'Revisar proyecto',detail:'El procesamiento necesita atención. Los documentos pueden seguir guardados.'}
  return {stage:1,label:'Continuar preparación',detail:'Completá la preparación del proyecto y su contexto antes de simular.'}
}

export function dashboardNextAction(item={}) {
  if(item.report_id) return {stage:4,label:'Abrir informe',detail:'Revisá el informe y accedé a las consultas avanzadas desde esa pantalla.',to:makeUrl('report',item.report_id),kind:'report'}
  if(item.simulation_id) {
    const state=item.runner_status
    if(['running','paused','stopping'].includes(state))
      return {stage:3,label:'Ver ejecución',detail:'Consultá el avance y los intercambios registrados.',to:makeUrl('simulation',item.simulation_id)+'/start',kind:'running'}
    if(state==='failed') return {stage:3,label:'Revisar error',detail:'Consultá qué falló y qué opciones de recuperación están disponibles.',to:makeUrl('simulation',item.simulation_id),kind:'needs-attention'}
    if(state==='completed') return {stage:4,label:'Consultar simulación',detail:'La ejecución terminó; revisá si el informe ya está disponible.',to:makeUrl('simulation',item.simulation_id),kind:'report-pending'}
    return {stage:2,label:'Configurar simulación',detail:'Elegí participantes, redes simuladas y rondas antes de ejecutar.',to:makeUrl('simulation',item.simulation_id),kind:'preparing'}
  }
  const status=preparation(item)
  return {...status,to:item.project_id?makeUrl('process',item.project_id):'/workspace',kind:item.project_status==='failed'?'needs-attention':item.project_status==='graph_building'?'running':'preparing'}
}

export function dashboardBucket(item) {
  const action=dashboardNextAction(item)
  if(action.kind==='report')return 'report'
  if(action.kind==='running')return 'running'
  if(action.kind==='needs-attention')return 'attention'
  return 'preparing'
}

export function dashboardCounts(items=[]) {
  return {
    projects:items.length,
    running:items.filter(x=>dashboardBucket(x)==='running').length,
    reports:items.filter(x=>dashboardBucket(x)==='report').length,
    pending:items.filter(x=>['preparing','attention'].includes(dashboardBucket(x))).length,
  }
}
