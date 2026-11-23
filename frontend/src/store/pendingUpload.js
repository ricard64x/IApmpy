/**
 * 临时存储待上传的文件和需求
 * 用于首页点击启动引擎后立即跳转，在Process页面再进行API调用
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  simulationRequirement: '',
  projectName: '',
  submissionKey: '',
  isPending: false
})

export function setPendingUpload(files, requirement, name = '') {
  state.files = files
  state.simulationRequirement = requirement
  state.projectName = name
  state.submissionKey = crypto.randomUUID().replace(/-/g, '')
  sessionStorage.setItem('tenondera-pending-upload-key',state.submissionKey)
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    projectName: state.projectName,
    submissionKey: state.submissionKey,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.projectName = ''
  state.submissionKey = ''
  sessionStorage.removeItem('tenondera-pending-upload-key')
  state.isPending = false
}

export default state
