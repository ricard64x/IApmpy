/* Real Chromium visual smoke for Tenonderã's browser UI.
   Uses the disposable CI login and intercepted synthetic report data.
   No production credentials, reports or user content are accessed. */
const { chromium } = require('playwright')
const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert/strict')

const BASE = process.env.VISUAL_BASE_URL || 'http://127.0.0.1:3000'
const DIR = path.resolve('artifacts/ui-qa')
fs.mkdirSync(DIR, { recursive: true })
const reportId = 'report_visualqa'
const simId = 'sim_visualqa'
const records = []
const issues = []
const screenshots = []
const geometry = {}
const success = (data) => ({ success: true, data })
const json = (route, data) => route.fulfill({ status: 200, contentType: 'application/json; charset=utf-8', body: JSON.stringify(data) })
const chrome = process.env.CHROME_BIN || ['/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium'].find(candidate => fs.existsSync(candidate)) || chromium.executablePath()
const browserArgs = ['--no-sandbox', '--disable-setuid-sandbox']

async function run() {
  const browser = await chromium.launch({ headless: true, executablePath: chrome, args: browserArgs })
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true, locale: 'es-PY' })
  const page = await context.newPage()
  page.on('pageerror', err => issues.push('Browser JS: ' + err.message))
  try {
    await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' })
    await page.locator('#login-user').fill('admin')
    await page.locator('#login-password').fill('dummy-ci-password-rotated')
    await page.screenshot({ path: path.join(DIR, '01-login-desktop.png'), fullPage: true })
    screenshots.push('01-login-desktop.png')
    await page.locator('button[type="submit"]').click()
    await page.waitForURL(url => url.pathname === '/', { timeout: 20000 })
    const dashboardText = await page.locator('body').innerText()
    assert(dashboardText.includes('Tenonderã') || dashboardText.includes('TENONDERÃ'))
    assert(!/OASIS|Fly\.io|GraphRAG|agentes sintéticos/i.test(dashboardText), 'Dashboard shows engineering jargon')
    await page.screenshot({ path: path.join(DIR, '02-dashboard-desktop.png'), fullPage: true })
    screenshots.push('02-dashboard-desktop.png')

    // Any authenticated administrator can rotate credentials after the initial
    // required change. Never submit real passwords in browser QA.
    const passwordButton = page.getByRole('button', {name: 'Cambiar mi contraseña'})
    await passwordButton.waitFor({timeout: 12000})
    await passwordButton.click()
    await page.waitForURL(url => url.pathname === '/cambiar-clave', {timeout: 12000})
    assert(await page.locator('#current').isVisible())
    assert(await page.locator('#next').isVisible())
    assert(await page.locator('#repeat').isVisible())
    await page.locator('#current').fill('dummy-ci-password-rotated')
    await page.locator('#next').fill('different-dummy-ci-password-2026')
    await page.locator('#repeat').fill('different-dummy-ci-password-wrong')
    await page.getByRole('button',{name:/Guardar nueva contraseña/}).click()
    await page.getByText('Las contraseñas no coinciden.').waitFor({timeout: 12000})
    await page.locator('#repeat').fill('different-dummy-ci-password-2026')
    await page.locator('#next').fill('dummy-ci-password-rotated')
    await page.locator('#repeat').fill('dummy-ci-password-rotated')
    await page.getByRole('button',{name:/Guardar nueva contraseña/}).click()
    await page.getByText('Elegí una contraseña diferente de la actual.').waitFor({timeout: 12000})
    await page.screenshot({path: path.join(DIR,'02a-cambiar-clave-administrador.png'),fullPage:true})
    screenshots.push('02a-cambiar-clave-administrador.png')
    await page.goto(BASE+'/',{waitUntil:'domcontentloaded'})

    // An existing project has no simulation until its graph has been built.
    // The history must still show it, and allow returning to its own process.
    const savedProject = {
      project_id: 'proj_visualqa', name: 'Caso guardado sin simulación',
      status: 'failed', zep_batch_id: 'batch_visualqa',
      created_at: '2026-11-22T14:00:00', owner_id: 'ci-admin',
      files: [{filename: 'expediente-ejemplo.md'}],
      simulation_requirement: 'Simulación ficticia para verificar proyectos guardados.'
    }
    let processedFragments = 20
    await page.route('**/api/graph/project/proj_visualqa/build-status', route =>
      json(route, success({
        status: 'processing', project_status: 'failed',
        processed: processedFragments, total: 80, processing: 10, failed: 0,
        percent: Math.round(processedFragments / 80 * 1000) / 10,
        local_task_active: false, needs_recovery: false
      })))
    await page.route('**/api/graph/project/proj_visualqa', route =>
      json(route, success({
        ...savedProject, graph_id: 'graph_visualqa', graph_build_task_id: null,
        ontology: { entity_types: [], edge_types: [] }
      })))
    await page.route('**/api/graph/project/list**', route => json(route, success([savedProject])))
    await page.route('**/api/simulation/history**', route => json(route, success([])))
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' })
    const projectRow = page.locator('.simulation-item').filter({hasText: 'Caso guardado sin simulación'})
    await projectRow.waitFor({timeout: 20000})
    await projectRow.locator('.project-live-inline > span').getByText('Procesando 20 de 80').waitFor({timeout: 15000})
    assert((await projectRow.innerText()).includes('25.0 %'), 'Dashboard has no live remote progress')
    await page.screenshot({path: path.join(DIR, '02b-proyectos-guardados.png'), fullPage: true})
    screenshots.push('02b-proyectos-guardados.png')
    await projectRow.locator('.link-open').click()
    await page.waitForURL(url => url.pathname === '/process/proj_visualqa', {timeout: 12000})
    await page.locator('.tracking-banner').getByText('20 de 80 fragmentos procesados').waitFor({timeout: 15000})
    assert(await page.locator('.tracking-banner').getByText('Actualización automática cada 12 segundos').isVisible())
    assert(await page.locator('.tracking-banner').getByRole('button', { name: 'Mis proyectos' }).isVisible())
    await page.screenshot({path: path.join(DIR, '02d-progreso-cabecera.png'), fullPage: true})
    screenshots.push('02d-progreso-cabecera.png')
    processedFragments = 40
    await page.locator('.tracking-banner .tracking-refresh').first().click()
    await page.locator('.tracking-banner').getByText('40 de 80 fragmentos procesados').waitFor({timeout: 15000})
    await page.reload({waitUntil: 'domcontentloaded'})
    await page.locator('.tracking-banner').getByText('40 de 80 fragmentos procesados').waitFor({timeout: 15000})
    await page.setViewportSize({width: 390, height: 844})
    await page.reload({waitUntil: 'domcontentloaded'})
    await page.locator('.tracking-banner').getByText('40 de 80 fragmentos procesados').waitFor({timeout: 15000})
    const mobileLeft = await page.locator('.panel-wrapper.left').evaluate(e => getComputedStyle(e).display)
    const mobileRight = await page.locator('.panel-wrapper.right').boundingBox()
    const mobileHeaderLeft = await page.locator('.app-header .header-left').boundingBox()
    const mobileHeaderRight = await page.locator('.app-header .header-right').boundingBox()
    assert.equal(mobileLeft, 'none', 'Mobile graph should not take half the screen')
    assert(mobileRight && mobileRight.width >= 375 && mobileRight.x >= 0 &&
      mobileRight.x + mobileRight.width <= 391, 'Mobile workbench must use the available width')
    assert(mobileHeaderLeft && mobileHeaderRight &&
      mobileHeaderLeft.x + mobileHeaderLeft.width <= mobileHeaderRight.x + 5,
      'Mobile top header overlaps language and navigation')
    await page.screenshot({path: path.join(DIR, '02e-progreso-movil.png'), fullPage: true})
    screenshots.push('02e-progreso-movil.png')
    await page.locator('.view-switcher .switch-btn').first().click()
    const mobileGraph = await page.locator('.panel-wrapper.left').boundingBox()
    assert(mobileGraph && mobileGraph.width >= 375 &&
      mobileGraph.x + mobileGraph.width <= 391, 'Mobile graph must take full width when selected')
    assert.equal(await page.locator('.panel-wrapper.right').evaluate(e => getComputedStyle(e).display),
      'none', 'Mobile graph view must not leave workbench squeezed alongside')
    await page.screenshot({path: path.join(DIR, '02f-grafo-movil.png'), fullPage: true})
    screenshots.push('02f-grafo-movil.png')
    await page.locator('.view-switcher .switch-btn').last().click()
    assert.equal(await page.locator('.panel-wrapper.left').evaluate(e => getComputedStyle(e).display),
      'none', 'Switching back to workbench must hide graph')
    await page.setViewportSize({width: 1440, height: 900})

    await page.goto(BASE + '/workspace', {waitUntil: 'domcontentloaded'})
    const historyCard = page.locator('.project-card').filter({hasText: 'Caso guardado sin simulación'})
    await historyCard.waitFor({timeout: 20000})
    await historyCard.locator('.history-live strong').getByText('Procesando 40 de 80').waitFor({timeout: 15000})
    await historyCard.click()
    assert(await page.locator('.modal-btn.btn-simulation').isDisabled(),
      'An unstarted project must not offer a nonexistent simulation')
    assert(await page.locator('.modal-btn.btn-project').isEnabled())
    await page.screenshot({path: path.join(DIR, '02c-historial-proyecto-pendiente.png'), fullPage: true})
    screenshots.push('02c-historial-proyecto-pendiente.png')
    await page.locator('.modal-btn.btn-project').click()
    await page.waitForURL(url => url.pathname === '/process/proj_visualqa', {timeout: 12000})

    await page.route('**/api/report/report_visualqa/sections', route => json(route, success({
      sections: [{ section_index: 1, content: '## Hallazgos\nEl escenario es **sintético** y se desarrolla en español.' }]
    })))
    await page.route('**/api/report/report_visualqa/export**', route => route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/markdown; charset=utf-8', 'content-disposition': 'attachment; filename="Tenondera_visualqa.md"' },
      body: '# Informe de prueba visual\nContenido exportado.'
    }))
    await page.route('**/api/report/report_visualqa', route => json(route, success({
      report_id: reportId,
      simulation_id: simId,
      status: 'completed',
      outline: {
        title: 'Informe sintético de prueba visual',
        summary: 'Contenido ficticio de ejemplo para verificar la interfaz.',
        sections: [{ title: 'Hallazgos', content: '' }]
      },
      markdown_content: '# Informe sintético de prueba visual\n## Hallazgos\nEl escenario es ficticio.'
    })))
    await page.route('**/api/simulation/sim_visualqa/profiles/realtime**', route => json(route, success({
      profiles: [
        { username: 'Comerciante de prueba', profession: 'Comercio', bio: 'Prioriza seguridad.' },
        { username: 'Estudiante de prueba', profession: 'Estudios', bio: 'Prioriza rapidez.' }
      ]
    })))
    await page.route('**/api/simulation/sim_visualqa', route => json(route, success({
      simulation_id: simId, status: 'completed', project_id: 'proj_visual_graph'
    })))
    // Isolated graph fixture with long, real-world-like entity descriptions.
    // Never load a user's private report or project in visual QA.
    await page.route('**/api/graph/project/proj_visual_graph', route => json(route, success({
      project_id: 'proj_visual_graph', status: 'graph_completed',
      graph_id: 'graph_visualqa', name: 'Proyecto de prueba visual',
    })))
    await page.route('**/api/graph/data/graph_visualqa', route => json(route, success({
      nodes: [
        {uuid:'node_company',name:'LM Consultmed',labels:['Organization'],
          summary:'Organización ficticia dedicada a la consultoría clínica, con planificación de espacios accesibles y servicios profesionales.',
          attributes:{country:'Paraguay',sector:'Consultoría clínica',
            description:'Diseño de espacios accesibles y funcionales para instituciones de salud.'}},
        {uuid:'node_architect',name:'Andrea Quevedo',labels:['Person'],
          attributes:{country:'Paraguay',profession:'Arquitectura'}}
      ],
      edges:[{
        uuid:'link_company_architect',
        source_node_uuid:'node_company',target_node_uuid:'node_architect',
        name:'COLLABORATES_WITH',fact:'Colaboración ficticia en proyectos de accesibilidad.'
      }]
    })))
    await page.route('**/api/report/interactions**', async route => {
      if (route.request().method() === 'GET') return json(route, success({ records }))
      const body = JSON.parse(route.request().postData() || '{}')
      const record = {
        id: 'test_' + (records.length + 1), kind: body.kind,
        question: body.message, target: body.target || 'report',
        agent_id: body.agent_id ?? null,
        created_at: new Date().toISOString(),
        source_mode: 'sintetico_posterior'
      }
      if (body.kind === 'survey') record.results = body.agent_ids.map(id => ({
        agent_id: id, agent_name: id === 0 ? 'Comerciante de prueba' : 'Estudiante de prueba',
        profession: id === 0 ? 'Comercio' : 'Estudios',
        question: body.message, answer: 'Respuesta simulada del participante ' + (id + 1) + '.'
      }))
      else record.response = 'Respuesta sintética en español para la prueba del chat.'
      records.push(record)
      return json(route, success(record))
    })

    // Synthetic metrics fixture validates the explainable visual layer in Chromium.
    await page.route('**/api/report/report_visualqa/metrics', route => json(route, success({
      source:'registros de prueba', metric_basis:'actividad sintética persistida',
      total_actions:6, message_actions:5, active_participants:2,
      recorded_interaction_pairs:2, cross_agent_messages:2, available:true,partial:false,
      last_event:'2026-11-23T12:04:00Z',
      interaction_quality:{
        status:'acceptable',label:'Interacción aceptable',issues:[],
        valid_multiagent_interaction:true,maximum_action_share_percent:66.7,
        diversity:'media'
      },
      population:{detected_profiles:2,selected_participants:2,synthetic_additions:0},
      participants:[
        {id:'0',name:'Comerciante de prueba',actions:4,messages:3},
        {id:'1',name:'Estudiante de prueba',actions:2,messages:2}
      ],
      interactions:[{from:'0',to:'1',count:1},{from:'1',to:'0',count:1}],
      by_round:[{round:'1',count:2},{round:'2',count:4}],
      by_day:[{date:'2026-11-23',count:6}],
      by_hour:Array.from({length:24},(_,hour)=>({hour:String(hour).padStart(2,'0'),count:hour===12?6:0})),
      by_type:[{type:'CREATE_POST',count:3},{type:'CREATE_COMMENT',count:2}],
      by_platform:[{platform:'reddit',count:3},{platform:'twitter',count:3}],
      messages:[
        {participant:'Comerciante de prueba',participant_id:'0',platform:'reddit',
          round:1,type:'CREATE_POST',excerpt:'Los costos del proveedor deben ser claros.',
          timestamp:'2026-11-23T12:01:00Z',target_id:null,synthetic:true},
        {participant:'Estudiante de prueba',participant_id:'1',platform:'reddit',
          round:2,type:'CREATE_COMMENT',excerpt:'Respondería con una propuesta más transparente.',
          timestamp:'2026-11-23T12:02:00Z',target_id:'0',synthetic:true}
      ],
      followups:{available:false},messages_sample_limit:250,messages_sample_truncated:false
    })))
    // Validate mobile graph *and* full-width node details at realistic phone width.
    await page.setViewportSize({width:390,height:844})
    await page.goto(BASE + '/report/' + reportId, {waitUntil:'domcontentloaded'})
    await page.locator('.view-switcher .switch-btn[data-mode="graph"]').click()
    const graphCanvas = page.locator('.graph-panel .graph-svg')
    await graphCanvas.waitFor({timeout:18000})
    const canvasBox = await graphCanvas.boundingBox()
    assert(canvasBox && canvasBox.width>=370 && canvasBox.x>=0 &&
      canvasBox.x+canvasBox.width<=391,'Mobile graph must fill the available viewport')
    assert.equal(await page.locator('.panel-wrapper.right').evaluate(e=>getComputedStyle(e).display),'none',
      'Mobile graph cannot display an adjacent desktop column')
    const legend = page.locator('.graph-legend .legend-toggle')
    await legend.waitFor({timeout:18000})
    await legend.click()
    assert.equal(await legend.getAttribute('aria-expanded'),'true')
    const nodeCircle = page.locator('.graph-panel .nodes circle').first()
    await nodeCircle.waitFor({timeout:18000})
    await nodeCircle.click({force:true})
    const detail = page.getByRole('dialog',{name:/Detalle de/})
    await detail.waitFor({timeout:12000})
    const detailBox = await detail.boundingBox()
    assert(detailBox && detailBox.width>=370 && detailBox.x>=0 &&
      detailBox.x+detailBox.width<=391 && detailBox.y<=1 && detailBox.height>=824,
      'Mobile node detail must cover the entire viewport, not remain a narrow side overlay')
    assert((await detail.innerText()).includes('Consultmed'),'Mobile detail must show the full entity name')
    const readable = await page.locator('.detail-content').boundingBox()
    assert(readable && readable.width>=350,'Mobile detail is unreadably narrow')
    assert(await page.locator('.detail-panel .mobile-back-button').isVisible())
    await page.screenshot({path:path.join(DIR,'03c-detalle-grafo-movil.png'),fullPage:true})
    screenshots.push('03c-detalle-grafo-movil.png')
    await page.locator('.detail-panel .mobile-back-button').click()
    assert.equal(await page.locator('.detail-panel').count(),0,'Returning to graph must close details')
    await page.locator('.view-switcher .switch-btn[data-mode="workbench"]').click()
    assert.equal(await page.locator('.panel-wrapper.left').evaluate(e=>getComputedStyle(e).display),'none',
      'Mobile results must not share a column with the graph')
    await page.setViewportSize({width:1440,height:900})

    // A completed case with only two original profiles must allow the user to
    // request ten participants without first deciphering the OASIS limit.
    let chosenFork = null
    await page.route('**/api/capacity/status',route=>json(route,success({
      machine_memory_mb:2048,lightweight_engine_available:true,
      lightweight_max_profiles:120,recommended_max_profiles:45,
    })))
    await page.route('**/api/simulation/sim_visualqa/execution-settings',route=>json(route,success({
      platform:'parallel',engine_mode:'oasis',interaction_mode:'posts',
      auto_finalize:true,max_rounds:10,locked:true,has_saved_settings:true,
    })))
    await page.route('**/api/simulation/sim_visualqa/population',route=>json(route,success({
      detected_profiles:2,selected_participants:2,synthetic_additions:0,
      max_lightweight:120,max_oasis:2,maximum_for_engine:2,locked:true,
    })))
    await page.route('**/api/simulation/sim_visualqa/config/realtime',route=>json(route,success({
      status:'completed',config_generated:true,
      config:{
        simulation_id:simId,agent_configs:[{agent_id:0},{agent_id:1}],
        time_config:{total_simulation_hours:72,minutes_per_round:30,
          agents_per_hour_min:1,agents_per_hour_max:2},
        event_config:{initial_posts:[]}
      },
      summary:{total_agents:2,simulation_hours:72,initial_posts_count:0}
    })))
    await page.route('**/api/simulation/sim_visualqa/fork',async route=>{
      chosenFork=JSON.parse(route.request().postData()||'{}')
      return json(route,success({
        simulation_id:'sim_visualqa_new_version',
        parent_simulation_id:simId,selected_participants:chosenFork.participants_count,
        synthetic_additions:Math.max(0,chosenFork.participants_count-2),
        status:'ready'
      }))
    })
    await page.goto(BASE + '/simulation/' + simId,{waitUntil:'domcontentloaded'})
    await page.getByText('¿Cuántos participantes querés simular?').waitFor({timeout:20000})
    assert((await page.locator('.population-control').innerText()).includes('2 es el mínimo'),
      'Participant minimum must be distinguishable from the maximum')
    await page.locator('.participant-preset').filter({hasText:/^10$/}).click()
    assert.equal(await page.locator('#participant-target').inputValue(),'10')
    assert((await page.locator('.population-control').innerText()).includes('8 participantes adicionales'),
      'The synthetic-versus-detected profile breakdown must be understandable')
    assert(await page.locator('.engine-option.chosen').filter({hasText:'Modo eficiente'}).isVisible(),
      'Selecting ten profiles should automatically enable available efficient mode')
    await page.screenshot({path:path.join(DIR,'03d-elegir-10-participantes.png'),fullPage:true})
    screenshots.push('03d-elegir-10-participantes.png')
    await page.getByRole('button',{name:/Crear nueva versión editable/}).click()
    await page.waitForURL(url=>url.pathname.includes('sim_visualqa_new_version'),{timeout:12000})
    assert(chosenFork && chosenFork.participants_count===10,'Fork must persist 10 participants')
    assert(chosenFork.settings.engine_mode==='lightweight',
      'Fork must save efficient mode when requesting more profiles than detected')
    await page.goto(BASE + '/interaction/' + reportId, { waitUntil: 'domcontentloaded' })
    await page.locator('.report-content-wrapper .main-title').waitFor({ timeout: 25000 })
    await page.locator('.action-bar-tabs .survey-pill').waitFor({ timeout: 20000 })
    // Verify that a client can explain numbers and drill down to actual sample records.
    await page.getByRole('heading',{name:'Entendé lo que ocurrió en la simulación'}).waitFor({timeout:20000})
    assert((await page.locator('.results-hub').innerText()).includes('Respuestas entre perfiles'))
    await page.locator('.results-hub [role="tab"]').filter({hasText:'Conversaciones'}).click()
    await page.locator('.results-hub .conversation-card').first().waitFor({timeout:12000})
    await page.locator('.results-hub input[type="search"]').fill('proveedor')
    assert.equal(await page.locator('.results-hub .conversation-card').count(),1)
    assert((await page.locator('.results-hub .conversation-card').first().innerText()).includes('costos del proveedor'))
    await page.screenshot({path:path.join(DIR,'03b-centro-resultados-filtrado.png'),fullPage:true})
    screenshots.push('03b-centro-resultados-filtrado.png')
    await page.locator('.results-hub [role="tab"]').filter({hasText:'Resumen'}).click()

    await page.locator('.agent-dropdown').waitFor({ timeout: 20000 })
    const text = await page.locator('.interaction-panel').innerText()
    assert(text.includes('Informe sintético de prueba visual'))
    assert(!/[\u3400-\u9fff]/u.test(text), 'Visible report UI contains Chinese script')
    assert((await page.locator('.survey-pill').innerText()).includes('Encuestas'), 'Survey action is not concise in Spanish')
    const chat = await page.locator('.action-bar-tabs button.tab-pill').first().boundingBox()
    const survey = await page.locator('.survey-pill').boundingBox()
    assert(chat && survey, 'Chat or survey button has no browser layout')
    geometry.desktop = { chat, survey, spacingPx: Math.round(survey.x - (chat.x + chat.width)), rowDifferencePx: Math.round(survey.y - chat.y) }
    assert(Math.abs(survey.y - chat.y) <= 5, 'Survey not in the same horizontal row as chat on desktop')
    assert(survey.x - (chat.x + chat.width) < 45, 'Survey button is too far from chat')
    await page.screenshot({ path: path.join(DIR, '03-interaccion-desktop.png'), fullPage: true })
    screenshots.push('03-interaccion-desktop.png')

    await page.locator('.chat-input').fill('¿Qué representa este escenario?')
    await page.locator('.send-btn').click()
    await page.getByText('Respuesta sintética en español para la prueba del chat.').waitFor({ timeout: 12000 })
    await page.screenshot({ path: path.join(DIR, '04-chat-funcionando.png'), fullPage: true })
    screenshots.push('04-chat-funcionando.png')

    await page.locator('.survey-pill').click()
    await page.locator('.agent-checkbox').first().click()
    assert(await page.locator('.agent-checkbox').first().evaluate(el => el.classList.contains('checked')), 'Visible participant selection did not toggle')
    await page.locator('.survey-input').fill('¿Usarías esta solución hipotética?')
    await page.locator('.survey-submit-btn').click()
    await page.locator('.result-card').first().waitFor({ timeout: 12000 })
    assert.equal(await page.locator('.result-card').count(), 1)
    const selectionCard = await page.locator('.agent-checkbox').first().boundingBox()
    assert(selectionCard && selectionCard.height >= 38, 'Survey options collapse after receiving results')
    await page.screenshot({ path: path.join(DIR, '05-encuesta-funcionando.png'), fullPage: true })
    screenshots.push('05-encuesta-funcionando.png')

    const downloadPromise = page.waitForEvent('download', { timeout: 12000 })
    await page.locator('.report-export-toolbar button').first().click()
    const download = await downloadPromise
    assert(download.suggestedFilename().endsWith('.md'), 'Report export did not start a Markdown download')

    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.locator('.chat-message.assistant').filter({ hasText: 'Respuesta sintética en español para la prueba del chat.' }).waitFor({ timeout: 20000 })
    await page.locator('.survey-pill').click()
    await page.locator('.result-card').first().waitFor({ timeout: 12000 })

    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: path.join(DIR, '06-interaccion-movil.png'), fullPage: true })
    screenshots.push('06-interaccion-movil.png')
    const mobileSurvey = await page.locator('.survey-pill').boundingBox()
    geometry.mobile = { survey: mobileSurvey, viewportWidth: 390 }
    if (!mobileSurvey || mobileSurvey.x < 0 || mobileSurvey.x + mobileSurvey.width > 390) {
      issues.push('Mobile survey button extends outside the viewport')
    }
    const mobileBrand = await page.locator('.app-header .brand').boundingBox()
    const mobileHeaderControls = await page.locator('.app-header .header-right').boundingBox()
    assert(mobileBrand && mobileHeaderControls && mobileBrand.x + mobileBrand.width <= mobileHeaderControls.x + 4,
      'The mobile header overlaps its brand and account/language controls')
    await page.locator('.result-card').first().scrollIntoViewIfNeeded()
    await page.screenshot({ path: path.join(DIR, '07-encuesta-resultados-movil.png'), fullPage: true })
    screenshots.push('07-encuesta-resultados-movil.png')

    const results = { passed: issues.length === 0, login: true, chat: true, survey: true, reportRestore: true, markdownExport: true, screenshots, geometry, issues }
    fs.writeFileSync(path.join(DIR, 'results.json'), JSON.stringify(results, null, 2))
    console.log('BROWSER_VISUAL_RESULTS ' + JSON.stringify(results))
    assert.equal(issues.length, 0, 'Browser visual smoke detected issues: ' + issues.join('; '))
  } catch (error) {
    try { await page.screenshot({ path: path.join(DIR, 'failure.png'), fullPage: true }) } catch {}
    fs.writeFileSync(path.join(DIR, 'failure.txt'), String(error.stack || error))
    throw error
  } finally {
    await browser.close()
  }
}

run().catch(err => { console.error(err); process.exitCode = 1 })
