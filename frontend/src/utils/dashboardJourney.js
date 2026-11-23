/**
 * One truthful next action for each saved project. This module never infers
 * an unsaved report, an actual conversation, or a completed preparation step.
 * The API already filters resources by the authenticated account.
 */
export const JOURNEY_STEPS = Object.freeze([
  {number:1,title:'Definí el escenario',short:'Objetivo y documentos',description:'Describí qué querés explorar y agregá tus fuentes.'},
  {number:2,title:'Construí el mapa',short:'Relaciones y contexto',description:'Revisá entidades, vínculos y la información encontrada.'},
  {number:3,title:'Elegí los participantes',short:'Personajes y espacios',description:'Definí cantidad, profesiones, lugares y profundidad del debate.'},
  {number:4,title:'Ejecutá las conversaciones',short:'Rondas e intercambios',description:'Observá intervenciones guardadas, respuestas y avance real.'},
  {number:5,title:'Analizá los resultados',short:'Informe y preguntas',description:'Explorá qué se dijeron, cómo se relacionan y qué conclusiones permite el escenario.'},
])

const makeUrl = (kind,id)=>`/${kind}/${encodeURIComponent(String(id))}`
const preparation = item => {
  const status=item?.project_status
  if(status==='graph_completed') return {stage:3,label:'Preparar participantes',detail:'El mapa está listo; revisá personajes y configurá la conversación.'}
  if(status==='ontology_generated') return {stage:2,label:'Construir el mapa',detail:'Se preparó la estructura de información. Revisá las relaciones y continuá.'}
  if(status==='graph_building') return {stage:2,label:'Ver progreso',detail:'El mapa de relaciones se está construyendo. El avance aparece en el proyecto.'}
  if(status==='failed') return {stage:2,label:'Revisar proyecto',detail:'El procesamiento necesita atención. Los documentos pueden seguir guardados.'}
  return {stage:1,label:'Continuar preparación',detail:'Completá la preparación del proyecto y su contexto antes de simular.'}
}

export function dashboardNextAction(item={}) {
  if(item.report_id) return {stage:5,label:'Analizar informe',detail:'Explorá las conversaciones, gráficos y conclusiones del informe.',to:makeUrl('report',item.report_id),kind:'report'}
  if(item.simulation_id) {
    const state=item.runner_status
    if(['running','paused','stopping'].includes(state))
      return {stage:4,label:'Ver ejecución',detail:'Consultá el avance y los intercambios registrados.',to:makeUrl('simulation',item.simulation_id)+'/start',kind:'running'}
    if(state==='failed') return {stage:4,label:'Revisar error',detail:'Consultá qué falló y qué opciones de recuperación están disponibles.',to:makeUrl('simulation',item.simulation_id),kind:'needs-attention'}
    if(state==='completed') return {stage:5,label:'Consultar simulación',detail:'La ejecución terminó; revisá si el informe ya está disponible.',to:makeUrl('simulation',item.simulation_id),kind:'report-pending'}
    return {stage:3,label:'Configurar simulación',detail:'Elegí participantes, redes simuladas y rondas antes de ejecutar.',to:makeUrl('simulation',item.simulation_id),kind:'preparing'}
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
