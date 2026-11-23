/* Chromium E2E: verify the new local simulation panel in Spanish with
   synthetic intercepted data and a real CI login, no private evidence. */
const {chromium}=require('playwright')
const fs=require('node:fs')
const path=require('node:path')
const assert=require('node:assert/strict')
const BASE=process.env.VISUAL_BASE_URL||'http://127.0.0.1:3000'
const DIR=path.resolve('artifacts/ui-qa')
const project='proj_0123456789ab'
const graph='gtg_aaaaaaaaaaaaaaaaaaaaaaaa'
const sim='lsim_aaaaaaaaaaaaaaaaaaaaaaaa'
const chrome=process.env.CHROME_BIN||'/usr/bin/google-chrome'
const ok=data=>({success:true,data})
const fulfill=(route,data)=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)})
async function main(){
 fs.mkdirSync(DIR,{recursive:true})
 const browser=await chromium.launch({headless:true,executablePath:chrome,args:['--no-sandbox','--disable-setuid-sandbox']})
 const page=await browser.newPage({viewport:{width:1440,height:900}})
 const faults=[]
 page.on('pageerror',e=>faults.push(e.message))
 try{
  await page.goto(BASE+'/login')
  await page.locator('#login-user').fill('admin')
  await page.locator('#login-password').fill('dummy-ci-password-rotated')
  await page.locator('button[type="submit"]').click()
  await page.waitForURL(url=>url.pathname==='/',{timeout:20000})
  const doc={
    project_id:project,name:'Simulación Getangiru QA',
    status:'graph_completed',graph_id:graph,
    simulation_requirement:'Ejercicio ficticio de respuesta a accesos anómalos',
    ontology:{entity_types:[{name:'SocTeam'},{name:'SecurityTeam'}],edge_types:[]},
    files:[{original_filename:'simulacion-ficticia.txt'}]
  }
  const result={
    simulation_id:sim,project_id:project,graph_id:graph,status:'completed',phase:4,
    total_phases:4,progress_pct:100,mode_requested:'hybrid',mode_effective:'qwen_local',
    feedback:{accept:0,reject:0},
    report:{actions:8,evidence_coverage_pct:100,external_model_requests:0,
      local_llm_requests:1,execution_ms:3250,
      disclaimer:'Acciones simuladas; no confirman incidentes reales.',
      local_model_fallback:false,
      plan:{basis:'qwen_local'}},
    actions:[{phase:1,actor_uuid:'n1',actor_type:'SocTeam',
      action_text:'Revisar alertas de forma simulada.',
      evidence_source:'doc:qa',evidence:'El SOC participa en un escenario ficticio.'}]
  }
  await page.route('**/api/graph/capabilities',route=>fulfill(route,ok({
    ontology_enabled:true,graph_enabled:true,graph_backend:'getangiru_local',
    simulation_enabled:false,native_simulation_enabled:true
  })))
  await page.route('**/api/graph/project/'+project,route=>fulfill(route,ok(doc)))
  await page.route('**/api/graph/data/'+graph,route=>fulfill(route,ok({
    graph_id:graph,node_count:2,edge_count:1,
    nodes:[{uuid:'n1',name:'SOC',labels:['SocTeam'],summary:'Rol ficticio',attributes:{}},
           {uuid:'n2',name:'Seguridad',labels:['SecurityTeam'],summary:'Rol ficticio',attributes:{}}],
    edges:[{uuid:'e1',name:'CO_MENTIONED',fact:'Solo co-mención',
            source_node_uuid:'n1',target_node_uuid:'n2',attributes:{}}]
  })))
  await page.route('**/api/native-simulation/capabilities',route=>fulfill(route,ok({
    graph_local_enabled:true,independent_of_zep:true,
    external_research_enabled:false
  })))
  await page.route('**/api/native-simulation/project/'+project+'/latest',route=>fulfill(route,ok(null)))
  await page.route('**/api/native-simulation/start',route=>fulfill(route,{
    success:true,data:{simulation_id:sim,status:'queued',project_id:project}
  }))
  await page.route('**/api/native-simulation/'+sim,route=>fulfill(route,ok(result)))
  await page.goto(BASE+'/process/'+project,{waitUntil:'domcontentloaded'})
  await page.getByText('Simulación multiactor local').first().waitFor({timeout:20000})
  const run=page.getByRole('button',{name:'Ejecutar simulación local'})
  assert(await run.isEnabled())
  await run.click()
  await page.getByText('Simulación finalizada').waitFor({timeout:12000})
  await page.getByText('Consultas IA externa').waitFor({timeout:12000})
  assert((await page.locator('.local-sim-panel').innerText()).includes('32')===false,
        'Synthetic stub should have eight actions, not hardcoded 32')
  assert((await page.locator('.local-sim-panel').innerText()).includes('Exportar informe (.md)'))
  await page.screenshot({path:path.join(DIR,'08-getangiru-simulacion-local.png'),fullPage:true})
  await page.setViewportSize({width:390,height:844})
  await page.reload({waitUntil:'domcontentloaded'})
  await page.getByText('Simulación multiactor local').first().waitFor({timeout:15000})
  assert((await page.locator('.local-sim-panel').boundingBox())?.width<=390)
  await page.screenshot({path:path.join(DIR,'09-getangiru-simulacion-movil.png'),fullPage:true})
  assert.equal(faults.length,0,'Unhandled browser script errors: '+faults.join('; '))
  console.log('native Getangiru graph panel responsive; workflow, metrics and action export visualized')
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1})
