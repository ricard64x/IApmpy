import service from './index'

/** No secrets exposed; indicates which processing stages can actually run. */
export function getProcessingCapabilities() {
  return service.get('/api/graph/capabilities', { timeout: 10000 })
}

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
/** Durable Cloud progress for a knowledge-graph build, across web-server restarts. */
export function getProjectBuildStatus(projectId) {
  return service.get(`/api/graph/project/${encodeURIComponent(projectId)}/build-status`)
}

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
export function getGraphData(graphId) {
  return service({
    url: `/api/graph/data/${graphId}`,
    method: 'get'
  })
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

/** Fast durable submission: the LLM runs after the server has returned an ID. */
export function submitOntology(formData) {
  return service({
    url:'/api/graph/ontology/submit',method:'post',data:formData,
    timeout:90000,headers:{'Content-Type':'multipart/form-data'}
  })
}
/** Read state on the persistent volume, after refresh or network reconnection. */
export function getOntologyStatus(projectId) {
  return service.get('/api/graph/project/'+encodeURIComponent(projectId)+'/ontology-status',
                     {timeout:12000})
}
export function retryOntology(projectId) {
  return service.post('/api/graph/project/'+encodeURIComponent(projectId)+'/ontology-retry')
}
