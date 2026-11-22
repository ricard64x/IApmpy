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
      simulation_id: simId, status: 'completed', project_id: null
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

    await page.goto(BASE + '/interaction/' + reportId, { waitUntil: 'domcontentloaded' })
    await page.locator('.report-content-wrapper .main-title').waitFor({ timeout: 25000 })
    await page.locator('.action-bar-tabs .survey-pill').waitFor({ timeout: 20000 })
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
