import test from 'node:test'
import assert from 'node:assert/strict'
import { mergeProjectHistory, projectEntryStatus } from '../src/utils/projectHistory.js'

const base = {
  project_id: 'proj_5fc1fd3c7cb2', name: 'Caso guardado',
  status: 'failed', zep_batch_id: 'remote-batch',
  owner_id: 'user-admin', created_at: '2026-11-22T14:00:00',
  files: [{filename:'expediente.md'}], simulation_requirement:'Evaluación hipotética'
}
test('unstarted project is visible without a simulation', () => {
  const rows=mergeProjectHistory([base],[])
  assert.equal(rows.length,1)
  assert.equal(rows[0].project_id,base.project_id)
  assert.equal(rows[0].simulation_id,null)
  assert.equal(rows[0].owner_id,'user-admin')
  assert.equal(rows[0].files.length,1)
  assert.equal(projectEntryStatus(rows[0]).label,'Revisar avance remoto')
})
test('simulation joins existing project, without duplicate rows', () => {
  const simulation={project_id:base.project_id,simulation_id:'sim_123',runner_status:'running',
    owner_id:'user-admin',created_at:'2026-11-22T15:00:00',total_rounds:10}
  const [row]=mergeProjectHistory([base],[simulation])
  assert.equal(mergeProjectHistory([base],[simulation]).length,1)
  assert.equal(row.project_name,'Caso guardado')
  assert.equal(row.simulation_id,'sim_123')
  assert.equal(row.files.length,1)
  assert.equal(row.is_project_only,false)
  assert.equal(projectEntryStatus(row).label,'En ejecución')
})
test('multiple projects and orphan simulations remain individually available', () => {
  const projects=[base,{project_id:'proj_other',name:'Segundo',status:'created',created_at:'2026-11-22T16:00:00'}]
  const sims=[{simulation_id:'sim_orphan',runner_status:'completed',created_at:'2026-11-21T15:00:00'}]
  const rows=mergeProjectHistory(projects,sims)
  assert.equal(rows.length,3)
  assert.deepEqual(rows.map(x=>x.project_id||x.simulation_id), ['proj_other',base.project_id,'sim_orphan'])
  assert.equal(projectEntryStatus(rows[0]).label,'Documentos guardados')
})
test('does not invent inaccessible projects or change account ownership', () => {
  assert.deepEqual(mergeProjectHistory([],[]),[])
  const rows=mergeProjectHistory([base],[])
  assert.equal(rows[0].owner_id,base.owner_id)
  assert.equal(rows[0].is_project_only,true)
})
