import service from './index'

/**
 * 生成本体（上传文档和模拟需求）
 * @param {Object} data - 包含files, simulation_requirement, project_name等
 * @returns {Promise}
 */
export function generateOntology(formData) {
  return service({
    url: '/api/graph/ontology/generate',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 构建图谱
 * @param {Object} data - 包含project_id, graph_name等
 * @returns {Promise}
 */
export function buildGraph(data) {
  return service({
    url: '/api/graph/build',
    method: 'post',
    data
  })
}

/**
 * 查询任务状态
 * @param {String} taskId - 任务ID
 * @returns {Promise}
 */
export function getTaskStatus(taskId) {
  return service({
    url: `/api/graph/task/${taskId}`,
    method: 'get'
  })
}

/**
 * 获取图谱数据
 * @param {String} graphId - 图谱ID
 * @returns {Promise}
 */
// A graph read can take many Zep pages. Share any in-flight request so that
// polling, refresh and navigation do not multiply expensive requests.
const inFlightGraphReads = new Map()
const RETRYABLE_HTTP_STATUSES = new Set([408, 429, 502, 503, 504])

function isRetryableGraphReadError(error) {
  const status = error?.response?.status
  if (status != null) return RETRYABLE_HTTP_STATUSES.has(status)
  return ['ERR_NETWORK', 'ECONNABORTED', 'ETIMEDOUT'].includes(error?.code)
}

function graphRetryDelayMs(error, attempt) {
  const raw = error?.response?.headers?.['retry-after']
  const seconds = Number(raw)
  if (raw != null && Number.isFinite(seconds) && seconds >= 0) {
    return Math.min(seconds * 1000, 10000)
  }
  return attempt * 2500
}

export function getGraphData(graphId) {
  if (!graphId) return Promise.reject(new Error('Graph ID is required'))

  const active = inFlightGraphReads.get(graphId)
  if (active) return active

  // Retries are restricted to this idempotent GET, never graph mutations.
  const request = (async () => {
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        return await service({
          url: `/api/graph/data/${encodeURIComponent(graphId)}`,
          method: 'get'
        })
      } catch (error) {
        if (attempt === 3 || !isRetryableGraphReadError(error)) throw error
        await new Promise(resolve => setTimeout(resolve, graphRetryDelayMs(error, attempt)))
      }
    }
  })()

  inFlightGraphReads.set(graphId, request)
  const clear = () => {
    if (inFlightGraphReads.get(graphId) === request) inFlightGraphReads.delete(graphId)
  }
  request.then(clear, clear)
  return request
}

/**
 * 获取项目信息
 * @param {String} projectId - 项目ID
 * @returns {Promise}
 */
export function getProject(projectId) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'get'
  })
}
