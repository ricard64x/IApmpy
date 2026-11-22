import i18n from '../i18n'
import { translateReportPart } from '../api/report'

// Only legacy reports with Chinese content require an LLM translation.
// Translated chapters are persisted by the server and cost nothing on reload.
const containsChinese = value => /[\u3400-\u9fff]/.test(typeof value === 'string' ? value : JSON.stringify(value || ''))

export async function ensureSpanishReport(reportId, outline, sections, onProgress = () => {}) {
  const source = { outline, sections: { ...sections } }
  if (i18n.global.locale.value !== 'es') return source
  const numbered = Object.entries(source.sections)
    .map(([index, content]) => ({ index: Number(index), content }))
    .filter(x => Number.isInteger(x.index) && x.index > 0 && x.content)
    .sort((a, b) => a.index - b.index)
  if (!containsChinese(outline) && !numbered.some(x => containsChinese(x.content))) {
    return source
  }
  const parts = ['outline', ...numbered.map(x => 'section_' + x.index)]
  let done = 0
  for (const part of parts) {
    onProgress(done, parts.length)
    const result = await translateReportPart(reportId, part)
    if (!result?.success || !result.data) throw new Error(result?.error || 'No se pudo traducir el informe.')
    if (part === 'outline' && result.data.outline) source.outline = result.data.outline
    else if (part !== 'outline' && typeof result.data.content === 'string') {
      source.sections[Number(part.replace('section_', ''))] = result.data.content
    }
    done++
  }
  onProgress(done, parts.length)
  return source
}
export { containsChinese }
