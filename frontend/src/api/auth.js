import { shallowRef } from 'vue'
import service, { setCsrf, clearCsrf } from './index'

export const activeUser = shallowRef(null)
let loaded = false
let pending = null

export async function loadSession(force = false) {
  if (loaded && !force) return activeUser.value
  if (pending) return pending
  pending = service.get('/api/auth/me').then(result => {
    activeUser.value = result.data.user
    setCsrf(result.data.csrf)
    loaded = true
    return activeUser.value
  }).catch(() => {
    activeUser.value = null
    clearCsrf()
    loaded = true
    return null
  }).finally(() => { pending = null })
  return pending
}

export async function loginUser(username, password) {
  const response = await service.post('/api/auth/login', { username, password })
  activeUser.value = response.data.user
  setCsrf(response.data.csrf)
  loaded = true
  return activeUser.value
}

export async function logoutUser() {
  try { await service.post('/api/auth/logout') } finally {
    activeUser.value = null
    clearCsrf()
    loaded = true
  }
}

export async function updateOwnPassword(current_password, new_password) {
  const result = await service.post('/api/auth/password', { current_password, new_password })
  activeUser.value = null
  clearCsrf()
  loaded = true
  return result
}

window.addEventListener('tenondera-session-expired', () => {
  activeUser.value = null
  loaded = false
  clearCsrf()
  if (window.location.pathname !== '/login') window.location.assign('/login')
})
