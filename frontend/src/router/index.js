import { createRouter, createWebHistory } from 'vue-router'
import { activeUser, loadSession } from '../api/auth'
import Dashboard from '../views/Dashboard.vue'
import Home from '../views/Home.vue'
import Login from '../views/Login.vue'
import MainView from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'

const routes = [
  { path: '/login', name: 'Login', component: Login, meta: { public: true } },
  { path: '/cambiar-clave', name: 'ChangePassword', component: () => import('../views/ChangePassword.vue') },
  { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/administracion', name: 'Administration', component: Dashboard, meta: { admin: true } },
  { path: '/workspace', name: 'Home', component: Home },
  { path: '/process/:projectId', name: 'Process', component: MainView, props: true },
  { path: '/simulation/:simulationId', name: 'Simulation', component: SimulationView, props: true },
  { path: '/simulation/:simulationId/start', name: 'SimulationRun', component: SimulationRunView, props: true },
  { path: '/report/:reportId', name: 'Report', component: ReportView, props: true },
  { path: '/interaction/:reportId', name: 'Interaction', component: InteractionView, props: true },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach(async to => {
  const current = await loadSession()
  if (to.meta.public) return current ? { name: 'Dashboard' } : true
  if (!current) return { name: 'Login', query: { redirect: to.fullPath } }
  if (current.must_change_password && to.name !== 'ChangePassword') return { name: 'ChangePassword' }
  // Any authenticated user may rotate their own password at any time.
  // The backend still requires the current password and a valid CSRF token.
  if (to.meta.admin && current.role !== 'administrator') return { name: 'Dashboard' }
  return true
})
export default router
