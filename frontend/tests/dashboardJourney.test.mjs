import test from 'node:test'
import assert from 'node:assert/strict'
import {dashboardNextAction,dashboardBucket,dashboardCounts,JOURNEY_STEPS} from '../src/utils/dashboardJourney.js'

test('guide has five user-readable steps with no unreachable links',()=>{
  assert.equal(JOURNEY_STEPS.length,5)
  assert.deepEqual(JOURNEY_STEPS.map(x=>x.number),[1,2,3,4,5])
  assert(JOURNEY_STEPS.every(x=>x.title && x.description))
})
test('new projects continue from documents, not invented runs',()=>{
  const item={project_id:'proj_abc 123',project_status:'created'}
  const action=dashboardNextAction(item)
  assert.equal(action.stage,1)
  assert.equal(action.to,'/process/proj_abc%20123')
  assert.equal(dashboardBucket(item),'preparing')
})
test('graph states direct to the correct preparation step',()=>{
  assert.equal(dashboardNextAction({project_id:'p',project_status:'ontology_generated'}).stage,1)
  assert.equal(dashboardNextAction({project_id:'p',project_status:'graph_completed'}).stage,2)
  assert.equal(dashboardNextAction({project_id:'p',project_status:'graph_building'}).label,'Ver progreso')
  assert.equal(dashboardBucket({project_id:'p',project_status:'graph_building'}),'running')
  assert.equal(dashboardBucket({project_id:'p',project_status:'failed'}),'attention')
})
test('running execution shows actual run, and a report opens evidence instead of restarting',()=>{
  const active={project_id:'p',simulation_id:'sim_live',runner_status:'running'}
  assert.equal(dashboardNextAction(active).to,'/simulation/sim_live/start')
  assert.equal(dashboardBucket(active),'running')
  const finished={...active,runner_status:'completed'}
  assert.equal(dashboardNextAction(finished).kind,'report-pending')
  assert.equal(dashboardNextAction(finished).to,'/simulation/sim_live')
  const reported={...finished,report_id:'report_123'}
  assert.equal(dashboardNextAction(reported).to,'/report/report_123')
  assert.equal(dashboardBucket(reported),'report')
})
test('aggregates only evidenced, visible projects, no fabricated metrics',()=>{
  const rows=[
    {project_id:'1',project_status:'created'},
    {project_id:'2',project_status:'graph_building'},
    {simulation_id:'sim_3',runner_status:'running'},
    {simulation_id:'sim_4',runner_status:'failed'},
    {simulation_id:'sim_5',runner_status:'completed',report_id:'r_5'},
    {simulation_id:'sim_6',runner_status:'completed'},
  ]
  assert.deepEqual(dashboardCounts(rows),{projects:6,running:2,reports:1,pending:3})
  assert.deepEqual(dashboardCounts([]),{projects:0,running:0,reports:0,pending:0})
})
