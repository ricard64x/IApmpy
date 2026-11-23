import assert from 'node:assert/strict'
import test from 'node:test'
import { projectRequiresAction, projectActionMessage } from '../src/utils/projectWorkflow.js'

test('an empty persisted pilot project is actionable, not generating', () => {
  const project = { project_id: 'proj_8ceb832d7f4e', status: 'created', files: [],
    ontology: null, graph_build_task_id: null, zep_batch_id: null }
  assert.equal(projectRequiresAction(project), true)
  assert.match(projectActionMessage(project), /no contiene documentos/)
})

test('an interrupted ontology must report failure, not pretend to process', () => {
  assert.equal(projectRequiresAction({ status: 'failed', zep_batch_id: null }), true)
  assert.match(projectActionMessage({ status: 'failed' }), /se interrumpió/)
})

test('durable batch, completed graph and generated ontology are not stalled', () => {
  for (const project of [
    { status: 'graph_building', zep_batch_id: 'zep_batch_1' },
    { status: 'failed', zep_batch_id: 'zep_batch_1' },
    { status: 'ontology_generated', ontology: {entity_types:[]} },
    { status: 'graph_completed' },
  ]) {
    assert.equal(projectRequiresAction(project), false)
  }
})

test('created with active task is not falsely marked interrupted', () => {
  assert.equal(projectRequiresAction({status:'created',graph_build_task_id:'task_1'}),false)
})
