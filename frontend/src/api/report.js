import service from './index'

/**
 * 开始报告生成
 * @param {Object} data - { simulation_id, force_regenerate? }
 */
export const generateReport = (data) => {
  return service.post('/api/report/generate', data)
}

/**
 * 获取报告生成状态
 * @param {string} reportId
 */
export const getReportStatus = (reportId) => {
  return service.get(`/api/report/generate/status`, { params: { report_id: reportId } })
}

/**
 * 获取 Agent 日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getAgentLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/agent-log`, { params: { from_line: fromLine } })
}

/**
 * 获取控制台日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getConsoleLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/console-log`, { params: { from_line: fromLine } })
}

/**
 * 获取报告详情
 * @param {string} reportId
 */
export const getReport = (reportId) => {
  return service.get(`/api/report/${reportId}`)
}

/**
 * 与 Report Agent 对话
 * @param {Object} data - { simulation_id, message, chat_history? }
 */
export const chatWithReport = (data) => {
  return service.post('/api/report/chat', data)
}

/** Consulta una respuesta sintética posterior basada en el informe persistente. */
export const createReportInteraction = (data) =>
  service.post('/api/report/interactions', data)

/** Recupera conversaciones y encuestas privadas del informe. */
export const getReportInteractions = (reportId, simulationId) =>
  service.get('/api/report/interactions', { params: { report_id: reportId, simulation_id: simulationId } })

/** URL relativa de exportación autenticada con cookie de sesión. */
export const reportExportUrl = (reportId, format = 'md') =>
  `/api/report/${encodeURIComponent(reportId)}/export?format=${encodeURIComponent(format)}`

/** Recupera capítulos guardados para volver a abrir un informe sin depender de logs. */
export const getSavedReportSections = (reportId) =>
  service.get(`/api/report/${encodeURIComponent(reportId)}/sections`)
