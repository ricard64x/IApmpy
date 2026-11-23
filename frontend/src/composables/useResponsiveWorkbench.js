import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'

/**
 * One active workspace on phones, desktop split remains available.
 * Device changes are local UI state only; no simulation writes or extra API calls.
 */
export function useResponsiveWorkbench(defaultMode = 'split') {
  const viewMode = ref(defaultMode)
  const isMobile = ref(false)
  let media = null

  const refresh = () => {
    const mobile = Boolean(media?.matches)
    isMobile.value = mobile
    if (mobile && viewMode.value === 'split') viewMode.value = 'workbench'
  }
  const setViewMode = (mode) => {
    if (!['graph', 'split', 'workbench'].includes(mode)) return
    viewMode.value = isMobile.value && mode === 'split' ? 'workbench' : mode
  }
  const toggleMaximize = (target) => {
    setViewMode(viewMode.value === target
      ? (isMobile.value ? 'workbench' : 'split')
      : target)
  }
  const revealGraph = () => setViewMode('graph')
  const revealWork = () => setViewMode('workbench')

  onMounted(() => {
    media = window.matchMedia('(max-width: 767px)')
    refresh()
    media.addEventListener?.('change', refresh)
  })
  onUnmounted(() => {
    media?.removeEventListener?.('change', refresh)
  })

  // D3 needs correct dimensions after its previously hidden pane is shown.
  watch(viewMode, async () => {
    await nextTick()
    if (typeof window !== 'undefined') window.dispatchEvent(new Event('resize'))
  })
  return { viewMode, isMobile, setViewMode, toggleMaximize, revealGraph, revealWork }
}
