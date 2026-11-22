import axios from 'axios'
import i18n from '../i18n'

// Same-origin cookie sessions; CSRF remains in memory, never localStorage.
let csrfToken = ''
export function setCsrf(value) { csrfToken = typeof value === 'string' ? value : '' }
export function clearCsrf() { csrfToken = '' }

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  withCredentials: true,
  timeout: 300000,
  headers: { 'Content-Type': 'application/json' }
})

service.interceptors.request.use(config => {
  config.headers['Accept-Language'] = i18n.global.locale.value
  if (!['get', 'head', 'options'].includes(config.method?.toLowerCase()) && csrfToken) {
    config.headers['X-CSRF-Token'] = csrfToken
  }
  return config
})

service.interceptors.response.use(response => {
  const result = response.data
  if (result?.success === false) {
    return Promise.reject(new Error(result.error || result.message || 'Error de solicitud'))
  }
  return result
}, error => {
  if (error.response?.status === 401 && !error.config?.url?.endsWith('/api/auth/login')) {
    clearCsrf()
    window.dispatchEvent(new Event('tenondera-session-expired'))
  }
  const message = error.response?.data?.error || error.response?.data?.message
  if (typeof message === 'string' && message) error.message = message
  return Promise.reject(error)
})

export default service
