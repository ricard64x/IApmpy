<template>
  <div class="graph-panel" :class="{ 'mobile-detail-open': isMobileGraph && selectedItem }">
    <div class="panel-header">
      <span class="panel-title">{{ displayMode==='dialogue' ? 'Red de conversaciones' : $t('graph.panelTitle') }}</span>
      <div v-if="simulationId" class="graph-type-switch" aria-label="Tipo de grafo">
        <button type="button" :class="{active:displayMode==='entities'}" :aria-pressed="displayMode==='entities'"
                @click="displayMode='entities'">Entidades</button>
        <button type="button" :class="{active:displayMode==='dialogue'}" :aria-pressed="displayMode==='dialogue'"
                @click="displayMode='dialogue'">Conversaciones</button>
      </div>
      <!-- 顶部工具栏 (Internal Top Right) -->
      <div class="header-tools">
        <button type="button" class="tool-btn" @click="$emit('refresh')" :disabled="loading" :aria-label="$t('graph.refreshGraph')" :title="$t('graph.refreshGraph')">
          <span class="icon-refresh" :class="{ 'spinning': loading }">↻</span>
          <span class="btn-text">{{ $t('graph.refreshLabel') }}</span>
        </button>
        <button type="button" class="tool-btn maximize-tool" @click="$emit('toggle-maximize')" :title="$t('graph.toggleMaximize')">
          <span class="icon-maximize">⛶</span>
        </button>
      </div>
    </div>
    
    <div class="graph-container" ref="graphContainer">
      <!-- 图谱可视化 -->
      <CharacterConversationGraph v-if="displayMode==='dialogue' && simulationId"
                                 :simulation-id="simulationId" />
      <div v-if="displayMode==='entities' && graphData" class="graph-view">
        <svg ref="graphSvg" class="graph-svg" role="img" aria-label="Grafo de relaciones. Tocá un elemento para ver su ficha."></svg>
        <p v-if="isMobileGraph && !selectedItem" class="mobile-graph-hint">Tocá un círculo para ver sus detalles. Separá dos dedos para acercar.</p>
        
        <!-- 构建中/模拟中提示 -->
        <div v-if="currentPhase === 1 || isSimulating" class="graph-building-hint">
          <div class="memory-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="memory-icon">
              <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-4.04z" />
              <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-4.04z" />
            </svg>
          </div>
          {{ isSimulating ? $t('graph.graphMemoryRealtime') : $t('graph.realtimeUpdating') }}
        </div>
        
        <!-- 模拟结束后的提示 -->
        <div v-if="showSimulationFinishedHint" class="graph-building-hint finished-hint">
          <div class="hint-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="hint-icon">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="16" x2="12" y2="12"></line>
              <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
          </div>
          <span class="hint-text">{{ $t('graph.pendingContentHint') }}</span>
          <button class="hint-close-btn" @click="dismissFinishedHint" :title="$t('graph.closeHint')">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        
        <!-- 节点/边详情面板 -->
        <div v-if="selectedItem" class="detail-panel" :role="isMobileGraph ? 'dialog' : undefined" :aria-modal="isMobileGraph ? 'true' : undefined" :aria-label="selectedItem.type === 'node' ? 'Detalle de ' + selectedItem.data.name : 'Detalle de relación'">
          <div class="detail-panel-header">
            <div class="detail-header-label">
              <span class="detail-title">{{ selectedItem.type === 'node' ? $t('graph.nodeDetails') : $t('graph.relationship') }}</span>
              <strong v-if="isMobileGraph" class="detail-mobile-name">{{ selectedItem.type === 'node' ? selectedItem.data.name : (selectedItem.data.source_name || 'Relación') }}</strong>
            </div>
            <span v-if="selectedItem.type === 'node'" class="detail-type-badge" :style="{ background: selectedItem.color, color: '#fff' }">
              {{ friendlyGraphType(selectedItem.entityType) }}
            </span>
            <button type="button" class="detail-close" @click="closeDetailPanel" aria-label="Cerrar detalle y volver al grafo">×</button>
          </div>
          
          <!-- 节点详情 -->
          <div v-if="selectedItem.type === 'node'" class="detail-content">
            <div class="detail-row">
              <span class="detail-label">{{ $t('graph.detailsName') }}:</span>
              <span class="detail-value">{{ selectedItem.data.name }}</span>
            </div>
            <div v-if="!isMobileGraph || showTechnicalDetails" class="detail-row technical-row">
              <span class="detail-label">{{ $t('graph.detailsId') }}:</span>
              <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
            </div>
            <div class="detail-row" v-if="selectedItem.data.created_at">
              <span class="detail-label">{{ $t('graph.detailsCreated') }}:</span>
              <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
            </div>
            
            <!-- Properties -->
            <div class="detail-section" v-if="selectedItem.data.attributes && Object.keys(selectedItem.data.attributes).length > 0">
              <div class="section-title">{{ $t('graph.detailsProperties') }}:</div>
              <div class="properties-list">
                <div v-for="(value, key) in selectedItem.data.attributes" :key="key" class="property-item">
                  <span class="property-key">{{ key }}:</span>
                  <span class="property-value">{{ value || $t('common.none') }}</span>
                </div>
              </div>
            </div>
            
            <!-- Summary -->
            <div class="detail-section" v-if="selectedItem.data.summary">
              <div class="section-title">{{ $t('graph.detailsSummary') }}:</div>
              <div class="summary-text">{{ selectedItem.data.summary }}</div>
            </div>
            
            <!-- Labels -->
            <div class="detail-section" v-if="selectedItem.data.labels && selectedItem.data.labels.length > 0">
              <div class="section-title">{{ $t('graph.detailsLabels') }}:</div>
              <div class="labels-list">
                <span v-for="label in selectedItem.data.labels" :key="label" class="label-tag">
                  {{ label }}
                </span>
              </div>
            </div>
          </div>
          
          <!-- 边详情 -->
          <div v-else class="detail-content">
            <!-- 自环组详情 -->
            <template v-if="selectedItem.data.isSelfLoopGroup">
              <div class="edge-relation-header self-loop-header">
                {{ selectedItem.data.source_name }} · {{ $t('graph.selfRelations') }}
                <span class="self-loop-count">{{ selectedItem.data.selfLoopCount }} {{ $t('graph.elementsCountLabel') }}</span>
              </div>
              
              <div class="self-loop-list">
                <div 
                  v-for="(loop, idx) in selectedItem.data.selfLoopEdges" 
                  :key="loop.uuid || idx" 
                  class="self-loop-item"
                  :class="{ expanded: expandedSelfLoops.has(loop.uuid || idx) }"
                >
                  <div 
                    class="self-loop-item-header"
                    @click="toggleSelfLoop(loop.uuid || idx)"
                  >
                    <span class="self-loop-index">#{{ idx + 1 }}</span>
                    <span class="self-loop-name">{{ loop.name || loop.fact_type || 'RELATED' }}</span>
                    <span class="self-loop-toggle">{{ expandedSelfLoops.has(loop.uuid || idx) ? '−' : '+' }}</span>
                  </div>
                  
                  <div class="self-loop-item-content" v-show="expandedSelfLoops.has(loop.uuid || idx)">
                    <div class="detail-row" v-if="loop.uuid">
                      <span class="detail-label">{{ $t('graph.detailsId') }}:</span>
                      <span class="detail-value uuid-text">{{ loop.uuid }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact">
                      <span class="detail-label">{{ $t('graph.detailsFact') }}:</span>
                      <span class="detail-value fact-text">{{ loop.fact }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact_type">
                      <span class="detail-label">{{ $t('graph.detailsType') }}:</span>
                      <span class="detail-value">{{ loop.fact_type }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.created_at">
                      <span class="detail-label">{{ $t('graph.detailsCreated') }}:</span>
                      <span class="detail-value">{{ formatDateTime(loop.created_at) }}</span>
                    </div>
                    <div v-if="loop.episodes && loop.episodes.length > 0" class="self-loop-episodes">
                      <span class="detail-label">{{ $t('graph.detailsEpisodes') }}:</span>
                      <div class="episodes-list compact">
                        <span v-for="ep in loop.episodes" :key="ep" class="episode-tag small">{{ ep }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            
            <!-- 普通边详情 -->
            <template v-else>
              <div class="edge-relation-header">
                {{ selectedItem.data.source_name }} → {{ friendlyGraphType(selectedItem.data.name || 'RELATED_TO') }} → {{ selectedItem.data.target_name }}
              </div>
              
              <div v-if="!isMobileGraph || showTechnicalDetails" class="detail-row technical-row">
                <span class="detail-label">{{ $t('graph.detailsId') }}:</span>
                <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">{{ $t('graph.detailsLabels') }}:</span>
                <span class="detail-value">{{ friendlyGraphType(selectedItem.data.name || 'RELATED_TO') }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">{{ $t('graph.detailsType') }}:</span>
                <span class="detail-value">{{ selectedItem.data.fact_type || 'Unknown' }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.fact">
                <span class="detail-label">{{ $t('graph.detailsFact') }}:</span>
                <span class="detail-value fact-text">{{ selectedItem.data.fact }}</span>
              </div>
              
              <!-- Episodes -->
              <div class="detail-section" v-if="selectedItem.data.episodes && selectedItem.data.episodes.length > 0">
                <div class="section-title">{{ $t('graph.detailsEpisodes') }}:</div>
                <div class="episodes-list">
                  <span v-for="ep in selectedItem.data.episodes" :key="ep" class="episode-tag">
                    {{ ep }}
                  </span>
                </div>
              </div>
              
              <div class="detail-row" v-if="selectedItem.data.created_at">
                <span class="detail-label">{{ $t('graph.detailsCreated') }}:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.valid_at">
                <span class="detail-label">{{ $t('graph.detailsValidFrom') }}:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.valid_at) }}</span>
              </div>
            </template>
          </div>
          <footer v-if="isMobileGraph" class="mobile-detail-footer">
            <button type="button" class="mobile-back-button" @click="closeDetailPanel">← Volver al grafo</button>
            <button type="button" class="mobile-technical-button" @click="showTechnicalDetails = !showTechnicalDetails" :aria-pressed="showTechnicalDetails">
              {{ showTechnicalDetails ? 'Ocultar datos técnicos' : 'Datos técnicos' }}
            </button>
          </footer>
        </div>
      </div>
      
      <!-- 加载状态 -->
      <div v-else-if="loading" class="graph-state">
        <div class="loading-spinner"></div>
        <p>{{ $t('graph.graphDataLoading') }}</p>
      </div>
      
      <!-- 等待/空状态 -->
      <div v-else-if="idle" class="graph-state" role="status">
        <div class="empty-icon">❖</div>
        <p class="empty-text">{{ idleMessage || 'Sin procesamiento activo. Cargá documentos para preparar el grafo.' }}</p>
      </div>

      <div v-else class="graph-state">
        <div class="empty-icon">❖</div>
        <p class="empty-text">{{ $t('graph.waitingOntology') }}</p>
      </div>
    </div>

    <!-- 底部图例 (Bottom Left) -->
    <div v-if="displayMode==='entities' && graphData && entityTypes.length" class="graph-legend" :class="{ 'legend-expanded': legendExpanded }">
      <button type="button" class="legend-toggle" @click="legendExpanded = !legendExpanded" :aria-expanded="legendExpanded">
        Tipos de elementos <span aria-hidden="true">{{ legendExpanded ? '⌄' : '⌃' }}</span>
      </button>
      <span class="legend-title">{{ $t('graph.entityTypesLabel') }}</span>
      <div v-show="!isMobileGraph || legendExpanded" class="legend-items">
        <div class="legend-item" v-for="type in entityTypes" :key="type.name">
          <span class="legend-dot" :style="{ background: type.color }"></span>
          <span class="legend-label">{{ friendlyGraphType(type.name) }}</span>
        </div>
      </div>
    </div>
    
    <!-- 显示边标签开关 -->
    <div v-if="displayMode==='entities' && graphData" class="edge-labels-toggle">
      <label class="toggle-switch">
        <input type="checkbox" v-model="showEdgeLabels" />
        <span class="slider"></span>
      </label>
      <span class="toggle-label">{{ isMobileGraph ? 'Etiquetas' : $t('graph.edgeLabelsLabel') }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import * as d3 from 'd3'
import CharacterConversationGraph from './CharacterConversationGraph.vue'
import { useI18n } from 'vue-i18n'
const { locale } = useI18n()

const props = defineProps({
  graphData: Object,
  simulationId: {type:String,default:''},
  loading: Boolean,
  currentPhase: Number,
  idle: Boolean,
  idleMessage: { type: String, default: '' },
  isSimulating: Boolean
})

const emit = defineEmits(['refresh', 'toggle-maximize'])

const graphContainer = ref(null)
const graphSvg = ref(null)
const selectedItem = ref(null)
const showEdgeLabels = ref(true)
const displayMode = ref('entities')
watch(displayMode, mode => {
  if(mode==='dialogue' && currentSimulation) currentSimulation.stop()
  if(mode==='entities') nextTick(renderGraph)
  selectedItem.value=null
})
const isMobileGraph = ref(false)
const legendExpanded = ref(false)
const showTechnicalDetails = ref(false)
let mobileMediaQuery = null
const updateMobileGraph = () => {
  const nextMobile = Boolean(mobileMediaQuery?.matches)
  if (nextMobile === isMobileGraph.value) return
  isMobileGraph.value = nextMobile
  showEdgeLabels.value = !nextMobile
  legendExpanded.value = false
  nextTick(renderGraph)
}
const expandedSelfLoops = ref(new Set()) // 展开的自环项
const showSimulationFinishedHint = ref(false) // 模拟结束后的提示
const wasSimulating = ref(false) // 追踪之前是否在模拟中

// 关闭模拟结束提示
const dismissFinishedHint = () => {
  showSimulationFinishedHint.value = false
}

// 监听 isSimulating 变化，检测模拟结束
watch(() => props.isSimulating, (newValue, oldValue) => {
  if (wasSimulating.value && !newValue) {
    // 从模拟中变为非模拟状态，显示结束提示
    showSimulationFinishedHint.value = true
  }
  wasSimulating.value = newValue
}, { immediate: true })

// 切换自环项展开/折叠状态
const toggleSelfLoop = (id) => {
  const newSet = new Set(expandedSelfLoops.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  expandedSelfLoops.value = newSet
}

// 计算实体类型用于图例
const entityTypes = computed(() => {
  if (!props.graphData?.nodes) return []
  const typeMap = {}
  // 美观的颜色调色板
  const colors = ['#FF6B35', '#004E89', '#7B2D8E', '#1A936F', '#C5283D', '#E9724C', '#3498db', '#9b59b6', '#27ae60', '#f39c12']
  
  props.graphData.nodes.forEach(node => {
    const type = node.labels?.find(l => l !== 'Entity') || 'Entity'
    if (!typeMap[type]) {
      typeMap[type] = { name: type, count: 0, color: colors[Object.keys(typeMap).length % colors.length] }
    }
    typeMap[type].count++
  })
  return Object.values(typeMap)
})

const friendlyGraphType = (value) => {
  const key = String(value || '')
  if (locale.value !== 'es') return key
  const replacements = {
    Entity:'Elemento',Person:'Persona',Organization:'Organización',Institution:'Institución',
    Project:'Proyecto',Community:'Comunidad',Resident:'Residente',Student:'Estudiante',
    Professor:'Profesor',University:'Universidad',ExternalProvider:'Proveedor externo',
    MaintenanceStaff:'Personal de mantenimiento',SecurityPersonnel:'Personal de seguridad',
    Service:'Servicio',Document:'Documento',Budget:'Presupuesto',Employee:'Empleado',
    RELATED_TO:'Se relaciona con',HAS_STAKEHOLDER:'Tiene partes interesadas',
    SUPPORTS:'Apoya',MEMBER_OF:'Forma parte de',INTERESTED_IN:'Se interesa por'
  }
  return replacements[key] || key.replace(/_/g, ' ')
}

// Fecha en el idioma elegido.
const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleString(locale.value === 'es' ? 'es-PY' : 'en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true 
    })
  } catch {
    return dateStr
  }
}

const closeDetailPanel = () => {
  selectedItem.value = null
  showTechnicalDetails.value = false
  expandedSelfLoops.value = new Set() // 重置展开状态
}

let currentSimulation = null
let linkLabelsRef = null
let linkLabelBgRef = null

const renderGraph = () => {
  if (displayMode.value !== 'entities' || !graphSvg.value || !props.graphData) return
  
  // 停止之前的仿真
  if (currentSimulation) {
    currentSimulation.stop()
  }
  
  const container = graphContainer.value
  const width = container?.clientWidth || 0
  const height = container?.clientHeight || 0
  if (width < 24 || height < 24) return
  
  const svg = d3.select(graphSvg.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    
  svg.selectAll('*').remove()
  
  const nodesData = props.graphData.nodes || []
  const edgesData = props.graphData.edges || []
  
  if (nodesData.length === 0) return

  // Prep data
  const nodeMap = {}
  nodesData.forEach(n => nodeMap[n.uuid] = n)
  
  const nodes = nodesData.map(n => ({
    id: n.uuid,
    name: n.name || 'Unnamed',
    type: n.labels?.find(l => l !== 'Entity') || 'Entity',
    rawData: n
  }))
  
  const nodeIds = new Set(nodes.map(n => n.id))
  
  // 处理边数据，计算同一对节点间的边数量和索引
  const edgePairCount = {}
  const selfLoopEdges = {} // 按节点分组的自环边
  const tempEdges = edgesData
    .filter(e => nodeIds.has(e.source_node_uuid) && nodeIds.has(e.target_node_uuid))
  
  // 统计每对节点之间的边数量，收集自环边
  tempEdges.forEach(e => {
    if (e.source_node_uuid === e.target_node_uuid) {
      // 自环 - 收集到数组中
      if (!selfLoopEdges[e.source_node_uuid]) {
        selfLoopEdges[e.source_node_uuid] = []
      }
      selfLoopEdges[e.source_node_uuid].push({
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      })
    } else {
      const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
      edgePairCount[pairKey] = (edgePairCount[pairKey] || 0) + 1
    }
  })
  
  // 记录当前处理到每对节点的第几条边
  const edgePairIndex = {}
  const processedSelfLoopNodes = new Set() // 已处理的自环节点
  
  const edges = []
  
  tempEdges.forEach(e => {
    const isSelfLoop = e.source_node_uuid === e.target_node_uuid
    
    if (isSelfLoop) {
      // 自环边 - 每个节点只添加一条合并的自环
      if (processedSelfLoopNodes.has(e.source_node_uuid)) {
        return // 已处理过，跳过
      }
      processedSelfLoopNodes.add(e.source_node_uuid)
      
      const allSelfLoops = selfLoopEdges[e.source_node_uuid]
      const nodeName = nodeMap[e.source_node_uuid]?.name || 'Unknown'
      
      edges.push({
        source: e.source_node_uuid,
        target: e.target_node_uuid,
        type: 'SELF_LOOP',
        name: `Self Relations (${allSelfLoops.length})`,
        curvature: 0,
        isSelfLoop: true,
        rawData: {
          isSelfLoopGroup: true,
          source_name: nodeName,
          target_name: nodeName,
          selfLoopCount: allSelfLoops.length,
          selfLoopEdges: allSelfLoops // 存储所有自环边的详细信息
        }
      })
      return
    }
    
    const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
    const totalCount = edgePairCount[pairKey]
    const currentIndex = edgePairIndex[pairKey] || 0
    edgePairIndex[pairKey] = currentIndex + 1
    
    // 判断边的方向是否与标准化方向一致（源UUID < 目标UUID）
    const isReversed = e.source_node_uuid > e.target_node_uuid
    
    // 计算曲率：多条边时分散开，单条边为直线
    let curvature = 0
    if (totalCount > 1) {
      // 均匀分布曲率，确保明显区分
      // 曲率范围根据边数量增加，边越多曲率范围越大
      const curvatureRange = Math.min(1.2, 0.6 + totalCount * 0.15)
      curvature = ((currentIndex / (totalCount - 1)) - 0.5) * curvatureRange * 2
      
      // 如果边的方向与标准化方向相反，翻转曲率
      // 这样确保所有边在同一参考系下分布，不会因方向不同而重叠
      if (isReversed) {
        curvature = -curvature
      }
    }
    
    edges.push({
      source: e.source_node_uuid,
      target: e.target_node_uuid,
      type: e.fact_type || e.name || 'RELATED',
      name: e.name || e.fact_type || 'RELATED',
      curvature,
      isSelfLoop: false,
      pairIndex: currentIndex,
      pairTotal: totalCount,
      rawData: {
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      }
    })
  })
    
  // Color scale
  const colorMap = {}
  entityTypes.value.forEach(t => colorMap[t.name] = t.color)
  const getColor = (type) => colorMap[type] || '#999'

  // Simulation - 根据边数量动态调整节点间距
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(d => {
      // 根据这对节点之间的边数量动态调整距离
      // 基础距离 150，每多一条边增加 40
      const baseDistance = 150
      const edgeCount = d.pairTotal || 1
      return baseDistance + (edgeCount - 1) * 50
    }))
    .force('charge', d3.forceManyBody().strength(isMobileGraph.value ? -260 : -400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(50))
    // 添加向中心的引力，让独立的节点群聚集到中心区域
    .force('x', d3.forceX(width / 2).strength(0.04))
    .force('y', d3.forceY(height / 2).strength(0.04))
  
  // Settle mobile layouts sooner, reducing unnecessary force ticks.
  if (isMobileGraph.value) simulation.alphaDecay(0.065)
  currentSimulation = simulation

  const g = svg.append('g')
  
  // Zoom
  svg.call(d3.zoom().extent([[0, 0], [width, height]]).scaleExtent([0.1, 4]).on('zoom', (event) => {
    g.attr('transform', event.transform)
  }))

  // Links - 使用 path 支持曲线
  const linkGroup = g.append('g').attr('class', 'links')
  
  // 计算曲线路径
  const getLinkPath = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // 检测自环
    if (d.isSelfLoop) {
      // 自环：绘制一个圆弧从节点出发再返回
      const loopRadius = 30
      // 从节点右侧出发，绕一圈回来
      const x1 = sx + 8  // 起点偏移
      const y1 = sy - 4
      const x2 = sx + 8  // 终点偏移
      const y2 = sy + 4
      // 使用圆弧绘制自环（sweep-flag=1 顺时针）
      return `M${x1},${y1} A${loopRadius},${loopRadius} 0 1,1 ${x2},${y2}`
    }
    
    if (d.curvature === 0) {
      // 直线
      return `M${sx},${sy} L${tx},${ty}`
    }
    
    // 计算曲线控制点 - 根据边数量和距离动态调整
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    // 垂直于连线方向的偏移，根据距离比例计算，保证曲线明显可见
    // 边越多，偏移量占距离的比例越大
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05 // 基础25%，每多一条边增加5%
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
  }
  
  // 计算曲线中点（用于标签定位）
  const getLinkMidpoint = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // 检测自环
    if (d.isSelfLoop) {
      // 自环标签位置：节点右侧
      return { x: sx + 70, y: sy }
    }
    
    if (d.curvature === 0) {
      return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
    }
    
    // 二次贝塞尔曲线的中点 t=0.5
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    // 二次贝塞尔曲线公式 B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2, t=0.5
    const midX = 0.25 * sx + 0.5 * cx + 0.25 * tx
    const midY = 0.25 * sy + 0.5 * cy + 0.25 * ty
    
    return { x: midX, y: midY }
  }
  
  const link = linkGroup.selectAll('path')
    .data(edges)
    .enter().append('path')
    .attr('stroke', '#C0C0C0')
    .attr('stroke-width', 1.5)
    .attr('fill', 'none')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      // 重置之前选中边的样式
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      // 高亮当前选中的边
      d3.select(event.target).attr('stroke', '#3498db').attr('stroke-width', 3)
      
      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })

  // Link labels background (白色背景使文字更清晰)
  const linkLabelBg = linkGroup.selectAll('rect')
    .data(edges)
    .enter().append('rect')
    .attr('fill', 'rgba(255,255,255,0.95)')
    .attr('rx', 3)
    .attr('ry', 3)
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      // 高亮对应的边
      link.filter(l => l === d).attr('stroke', '#3498db').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', 'rgba(52, 152, 219, 0.1)')
      
      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })

  // Link labels
  const linkLabels = linkGroup.selectAll('text')
    .data(edges)
    .enter().append('text')
    .text(d => d.name)
    .attr('font-size', '9px')
    .attr('fill', '#666')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('font-family', 'system-ui, sans-serif')
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      // 高亮对应的边
      link.filter(l => l === d).attr('stroke', '#3498db').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', '#3498db')
      
      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })
  
  // 保存引用供外部控制显隐
  linkLabelsRef = linkLabels
  linkLabelBgRef = linkLabelBg

  // Nodes group
  const nodeGroup = g.append('g').attr('class', 'nodes')
  
  // Node circles
  const node = nodeGroup.selectAll('circle')
    .data(nodes)
    .enter().append('circle')
    .attr('r', isMobileGraph.value ? 18 : 10)
    .attr('fill', d => getColor(d.type))
    .attr('tabindex', 0)
    .attr('role', 'button')
    .attr('aria-label', d => 'Ver detalles de ' + d.name)
    .attr('stroke', '#fff')
    .attr('stroke-width', 2.5)
    .style('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (event, d) => {
        // 只记录位置，不重启仿真（区分点击和拖拽）
        d.fx = d.x
        d.fy = d.y
        d._dragStartX = event.x
        d._dragStartY = event.y
        d._isDragging = false
      })
      .on('drag', (event, d) => {
        // 检测是否真正开始拖拽（移动超过阈值）
        const dx = event.x - d._dragStartX
        const dy = event.y - d._dragStartY
        const distance = Math.sqrt(dx * dx + dy * dy)
        
        if (!d._isDragging && distance > 3) {
          // 首次检测到真正拖拽，才重启仿真
          d._isDragging = true
          simulation.alphaTarget(0.3).restart()
        }
        
        if (d._isDragging) {
          d.fx = event.x
          d.fy = event.y
        }
      })
      .on('end', (event, d) => {
        // 只有真正拖拽过才让仿真逐渐停止
        if (d._isDragging) {
          simulation.alphaTarget(0)
        }
        d.fx = null
        d.fy = null
        d._isDragging = false
      })
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      // 重置所有节点样式
      node.attr('stroke', '#fff').attr('stroke-width', 2.5)
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      // 高亮选中节点
      d3.select(event.target).attr('stroke', '#E91E63').attr('stroke-width', 4)
      // 高亮与此节点相连的边
      link.filter(l => l.source.id === d.id || l.target.id === d.id)
        .attr('stroke', '#E91E63')
        .attr('stroke-width', 2.5)
      
      selectedItem.value = {
        type: 'node',
        data: d.rawData,
        entityType: d.type,
        color: getColor(d.type)
      }
    })
    .on('mouseenter', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.uuid !== d.rawData.uuid) {
        d3.select(event.target).attr('stroke', '#333').attr('stroke-width', 3)
      }
    })
    .on('mouseleave', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.uuid !== d.rawData.uuid) {
        d3.select(event.target).attr('stroke', '#fff').attr('stroke-width', 2.5)
      }
    })

  if (isMobileGraph.value) node.on('.drag', null)

  // Keyboard and screen reader users can select the same graph nodes.
  node.on('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      event.currentTarget.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    }
  })

  // Node Labels
  const nodeLabels = nodeGroup.selectAll('text')
    .data(nodes)
    .enter().append('text')
    .text(d => d.name.length > (isMobileGraph.value ? 11 : 8)
      ? d.name.substring(0, isMobileGraph.value ? 11 : 8) + '…' : d.name)
    .style('display', isMobileGraph.value && nodes.length > 18 ? 'none' : null)
    .attr('font-size', '11px')
    .attr('fill', '#333')
    .attr('font-weight', '500')
    .attr('dx', 14)
    .attr('dy', 4)
    .style('pointer-events', 'none')
    .style('font-family', 'system-ui, sans-serif')

  simulation.on('tick', () => {
    // 更新曲线路径
    link.attr('d', d => getLinkPath(d))
    
    // 更新边标签位置（无旋转，水平显示更清晰）
    linkLabels.each(function(d) {
      const mid = getLinkMidpoint(d)
      d3.select(this)
        .attr('x', mid.x)
        .attr('y', mid.y)
        .attr('transform', '') // 移除旋转，保持水平
    })
    
    // 更新边标签背景
    linkLabelBg.each(function(d, i) {
      const mid = getLinkMidpoint(d)
      const textEl = linkLabels.nodes()[i]
      const bbox = textEl.getBBox()
      d3.select(this)
        .attr('x', mid.x - bbox.width / 2 - 4)
        .attr('y', mid.y - bbox.height / 2 - 2)
        .attr('width', bbox.width + 8)
        .attr('height', bbox.height + 4)
        .attr('transform', '') // 移除旋转
    })

    node
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)

    nodeLabels
      .attr('x', d => d.x)
      .attr('y', d => d.y)
  })
  
  // 点击空白处关闭详情面板
  svg.on('click', () => {
    selectedItem.value = null
    node.attr('stroke', '#fff').attr('stroke-width', 2.5)
    linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
    linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
    linkLabels.attr('fill', '#666')
  })
}

watch(() => props.graphData, () => {
  nextTick(renderGraph)
}, { deep: true })

// 监听边标签显示开关
watch(showEdgeLabels, (newVal) => {
  if (linkLabelsRef) {
    linkLabelsRef.style('display', newVal ? 'block' : 'none')
  }
  if (linkLabelBgRef) {
    linkLabelBgRef.style('display', newVal ? 'block' : 'none')
  }
})

let resizeFrame = null
const handleResize = () => {
  if (resizeFrame !== null) return
  resizeFrame = window.requestAnimationFrame(() => {
    resizeFrame = null
    nextTick(renderGraph)
  })
}
const onGraphKeydown = (event) => {
  if (event.key === 'Escape' && selectedItem.value) closeDetailPanel()
}
onMounted(() => {
  mobileMediaQuery = window.matchMedia('(max-width: 767px)')
  isMobileGraph.value = mobileMediaQuery.matches
  showEdgeLabels.value = !isMobileGraph.value
  mobileMediaQuery.addEventListener?.('change', updateMobileGraph)
  window.addEventListener('resize', handleResize)
  window.addEventListener('keydown', onGraphKeydown)
  nextTick(renderGraph)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('keydown', onGraphKeydown)
  mobileMediaQuery?.removeEventListener?.('change', updateMobileGraph)
  if (resizeFrame !== null) window.cancelAnimationFrame(resizeFrame)
  if (currentSimulation) {
    currentSimulation.stop()
  }
})
</script>

<style scoped>
.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #FAFAFA;
  background-image: radial-gradient(#D0D0D0 1.5px, transparent 1.5px);
  background-size: 24px 24px;
  overflow: hidden;
}

.panel-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 16px 20px;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(to bottom, rgba(255,255,255,0.95), rgba(255,255,255,0));
  pointer-events: none;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  pointer-events: auto;
}

.header-tools {
  pointer-events: auto;
  display: flex;
  gap: 10px;
  align-items: center;
}

.tool-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid #E0E0E0;
  background: #FFF;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  color: #666;
  transition: all 0.2s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  font-size: 13px;
}

.tool-btn:hover {
  background: #F5F5F5;
  color: #000;
  border-color: #CCC;
}

.tool-btn .btn-text {
  font-size: 12px;
}

.icon-refresh.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.graph-container {
  width: 100%;
  height: 100%;
}

.graph-view, .graph-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.graph-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #999;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.2;
}

/* Entity Types Legend - Bottom Left */
.graph-legend {
  position: absolute;
  bottom: 24px;
  left: 24px;
  background: rgba(255,255,255,0.95);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #EAEAEA;
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  z-index: 10;
}

.legend-title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #E91E63;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  max-width: 320px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #555;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-label {
  white-space: nowrap;
}

/* Edge Labels Toggle - Top Right */
.edge-labels-toggle {
  position: absolute;
  top: 60px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: #FFF;
  padding: 8px 14px;
  border-radius: 20px;
  border: 1px solid #E0E0E0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  z-index: 10;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #E0E0E0;
  border-radius: 22px;
  transition: 0.3s;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  border-radius: 50%;
  transition: 0.3s;
}

input:checked + .slider {
  background-color: #7B2D8E;
}

input:checked + .slider:before {
  transform: translateX(18px);
}

.toggle-label {
  font-size: 12px;
  color: #666;
}

/* Detail Panel - Right Side */
.detail-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 320px;
  max-height: calc(100% - 100px);
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
  overflow: hidden;
  font-family: 'Noto Sans SC', system-ui, sans-serif;
  font-size: 13px;
  z-index: 20;
  display: flex;
  flex-direction: column;
}

.detail-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: #FAFAFA;
  border-bottom: 1px solid #EEE;
  flex-shrink: 0;
}

.detail-title {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.detail-type-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  margin-left: auto;
  margin-right: 12px;
}

.detail-close {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #999;
  line-height: 1;
  padding: 0;
  transition: color 0.2s;
}

.detail-close:hover {
  color: #333;
}

.detail-content {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.detail-row {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.detail-label {
  color: #888;
  font-size: 12px;
  font-weight: 500;
  min-width: 80px;
}

.detail-value {
  color: #333;
  flex: 1;
  word-break: break-word;
}

.detail-value.uuid-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #666;
}

.detail-value.fact-text {
  line-height: 1.5;
  color: #444;
}

.detail-section {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #F0F0F0;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin-bottom: 10px;
}

.properties-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.property-item {
  display: flex;
  gap: 8px;
}

.property-key {
  color: #888;
  font-weight: 500;
  min-width: 90px;
}

.property-value {
  color: #333;
  flex: 1;
}

.summary-text {
  line-height: 1.6;
  color: #444;
  font-size: 12px;
}

.labels-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.label-tag {
  display: inline-block;
  padding: 4px 12px;
  background: #F5F5F5;
  border: 1px solid #E0E0E0;
  border-radius: 16px;
  font-size: 11px;
  color: #555;
}

.episodes-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.episode-tag {
  display: inline-block;
  padding: 6px 10px;
  background: #F8F8F8;
  border: 1px solid #E8E8E8;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #666;
  word-break: break-all;
}

/* Edge relation header */
.edge-relation-header {
  background: #F8F8F8;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  line-height: 1.5;
  word-break: break-word;
}

/* Building hint */
.graph-building-hint {
  position: absolute;
  bottom: 160px; /* Moved up from 80px */
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(8px);
  color: #fff;
  padding: 10px 20px;
  border-radius: 30px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-weight: 500;
  letter-spacing: 0.5px;
  z-index: 100;
}

.memory-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  animation: breathe 2s ease-in-out infinite;
}

.memory-icon {
  width: 18px;
  height: 18px;
  color: #4CAF50;
}

@keyframes breathe {
  0%, 100% { opacity: 0.7; transform: scale(1); filter: drop-shadow(0 0 2px rgba(76, 175, 80, 0.3)); }
  50% { opacity: 1; transform: scale(1.15); filter: drop-shadow(0 0 8px rgba(76, 175, 80, 0.6)); }
}

/* 模拟结束后的提示样式 */
.graph-building-hint.finished-hint {
  background: rgba(0, 0, 0, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.finished-hint .hint-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
}

.finished-hint .hint-icon {
  width: 18px;
  height: 18px;
  color: #FFF;
}

.finished-hint .hint-text {
  flex: 1;
  white-space: nowrap;
}

.hint-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  color: #FFF;
  transition: all 0.2s;
  margin-left: 8px;
  flex-shrink: 0;
}

.hint-close-btn:hover {
  background: rgba(255, 255, 255, 0.35);
  transform: scale(1.1);
}

/* Loading spinner */
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #E0E0E0;
  border-top-color: #7B2D8E;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

/* Self-loop styles */
.self-loop-header {
  display: flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, #E8F5E9 0%, #F1F8E9 100%);
  border: 1px solid #C8E6C9;
}

.self-loop-count {
  margin-left: auto;
  font-size: 11px;
  color: #666;
  background: rgba(255,255,255,0.8);
  padding: 2px 8px;
  border-radius: 10px;
}

.self-loop-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.self-loop-item {
  background: #FAFAFA;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
}

.self-loop-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #F5F5F5;
  cursor: pointer;
  transition: background 0.2s;
}

.self-loop-item-header:hover {
  background: #EEEEEE;
}

.self-loop-item.expanded .self-loop-item-header {
  background: #E8E8E8;
}

.self-loop-index {
  font-size: 10px;
  font-weight: 600;
  color: #888;
  background: #E0E0E0;
  padding: 2px 6px;
  border-radius: 4px;
}

.self-loop-name {
  font-size: 12px;
  font-weight: 500;
  color: #333;
  flex: 1;
}

.self-loop-toggle {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #888;
  background: #E0E0E0;
  border-radius: 4px;
  transition: all 0.2s;
}

.self-loop-item.expanded .self-loop-toggle {
  background: #D0D0D0;
  color: #666;
}

.self-loop-item-content {
  padding: 12px;
  border-top: 1px solid #EAEAEA;
}

.self-loop-item-content .detail-row {
  margin-bottom: 8px;
}

.self-loop-item-content .detail-label {
  font-size: 11px;
  min-width: 60px;
}

.self-loop-item-content .detail-value {
  font-size: 12px;
}

.self-loop-episodes {
  margin-top: 8px;
}

.episodes-list.compact {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 4px;
}

.episode-tag.small {
  padding: 3px 6px;
  font-size: 9px;
}

/* Graph details are read-first on phones. Desktop keeps the familiar side card. */
.legend-toggle, .mobile-detail-footer, .mobile-graph-hint, .detail-mobile-name { display: none; }
@media (max-width: 767px) {
  .graph-panel {
    background-color: #f7fafc;
    background-image: radial-gradient(#d5e3ed 1.05px, transparent 1.05px);
    background-size: 26px 26px;
  }
  .graph-panel .panel-header {
    padding: 12px 13px;
    min-height: 62px;
    background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(255,255,255,.82) 80%, rgba(255,255,255,0));
    align-items: flex-start;
  }
  .graph-panel .panel-title {
    font: 750 13px/1.4 system-ui, sans-serif;
    max-width: 170px;
    color: #193f5c;
    padding-top: 9px;
  }
  .graph-panel .header-tools { gap: 7px; }
  .graph-panel .tool-btn {
    min-width: 44px; min-height: 44px;
    border: 1px solid #d4e3ec;
    border-radius: 12px;
    background: rgba(255,255,255,.96);
    color: #235c7d;
    box-shadow: 0 2px 12px rgba(22,57,86,.07);
    padding: 8px;
    font-size: 17px;
  }
  .graph-panel .tool-btn .btn-text { display: none; }
  .graph-panel .maximize-tool { display: none; }
  .graph-panel .graph-svg { touch-action: none; }
  .graph-panel .mobile-graph-hint {
    display: block;
    position: absolute;
    z-index: 9;
    bottom: max(70px, calc(env(safe-area-inset-bottom, 0px) + 70px));
    left: 50%;
    transform: translateX(-50%);
    width: max-content;
    max-width: calc(100% - 30px);
    text-align: center;
    border-radius: 999px;
    padding: 9px 13px;
    background: rgba(20, 60, 84, .91);
    color: white;
    box-shadow: 0 6px 18px rgba(12,42,60,.17);
    font: 500 11px/1.4 system-ui, sans-serif;
    pointer-events: none;
  }
  .graph-panel .graph-legend {
    z-index: 12;
    left: 12px;
    bottom: max(11px, env(safe-area-inset-bottom, 0px));
    right: auto;
    max-width: min(80vw, 260px);
    padding: 5px 7px;
    border-radius: 12px;
    background: rgba(255,255,255,.98);
    border: 1px solid #d1e0ea;
    box-shadow: 0 4px 20px rgba(20,54,78,.10);
  }
  .graph-panel .legend-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    width: 100%;
    min-height: 40px;
    border: 0;
    padding: 6px 8px;
    border-radius: 9px;
    background: transparent;
    color: #23536f;
    font: 700 12px/1.35 system-ui, sans-serif;
    text-align: left;
    cursor: pointer;
  }
  .graph-panel .legend-title { display: none; }
  .graph-panel .legend-items {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    max-height: 175px;
    overflow: auto;
    gap: 9px;
    padding: 7px 10px 9px;
  }
  .graph-panel .legend-label {
    white-space: normal;
    overflow-wrap: anywhere;
    font-size: 12px;
  }
  .graph-panel .edge-labels-toggle {
    z-index: 12;
    top: 69px;
    right: 12px;
    width: auto;
    max-width: 150px;
    padding: 7px 10px;
    gap: 8px;
    border: 1px solid #d1e0ea;
    box-shadow: 0 3px 15px rgba(20,54,78,.09);
    border-radius: 11px;
    background: rgba(255,255,255,.96);
  }
  .graph-panel .toggle-label { font-size: 11px; font-weight: 650; }
  .graph-panel .detail-panel {
    position: fixed;
    inset: 0;
    width: 100vw;
    max-width: 100vw;
    height: 100dvh;
    max-height: 100dvh;
    margin: 0;
    border: 0;
    border-radius: 0;
    background: #fff;
    box-shadow: none;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    z-index: 1200;
    font-family: system-ui, sans-serif;
  }
  .graph-panel .detail-panel-header {
    min-height: 88px;
    padding: max(15px, env(safe-area-inset-top, 0px)) 19px 14px;
    background: linear-gradient(135deg, #eef7fc, #fff);
    border-bottom: 1px solid #e0ebf2;
    gap: 9px;
    align-items: center;
  }
  .graph-panel .detail-header-label {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 3px;
    flex: 1;
  }
  .graph-panel .detail-title {
    color: #537590;
    font: 700 11px/1.35 system-ui,sans-serif;
    text-transform: uppercase;
    letter-spacing: .7px;
  }
  .graph-panel .detail-mobile-name {
    display: block;
    color: #143e5b;
    font: 800 clamp(19px, 5vw, 24px)/1.2 system-ui,sans-serif;
    overflow-wrap: anywhere;
    letter-spacing: -.4px;
  }
  .graph-panel .detail-type-badge {
    margin: 0 6px 0 0;
    padding: 5px 9px;
    font-size: 10px;
    border-radius: 999px;
    max-width: 110px;
    overflow-wrap: anywhere;
  }
  .graph-panel .detail-close {
    width: 44px; height: 44px;
    flex: 0 0 44px;
    display: grid; place-items: center;
    background: #f2f6f9;
    color: #234c69;
    font-size: 27px;
    border: 1px solid #dde8ef;
    border-radius: 12px;
    margin: 0;
  }
  .graph-panel .detail-content {
    min-width: 0;
    padding: 20px 18px 26px;
    display: block;
    flex: 1;
    overflow: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
  }
  .graph-panel .detail-row {
    display: grid;
    grid-template-columns: minmax(0,1fr);
    gap: 5px;
    margin: 0 0 15px;
    padding: 0 0 14px;
    border-bottom: 1px solid #ecf1f5;
  }
  .graph-panel .detail-label {
    font: 750 11px/1.3 system-ui,sans-serif;
    color: #688096;
    text-transform: uppercase;
    letter-spacing: .5px;
  }
  .graph-panel .detail-value {
    min-width: 0;
    font: 500 16px/1.6 system-ui,sans-serif;
    color: #1f3e56;
    overflow-wrap: anywhere;
    word-break: normal;
  }
  .graph-panel .detail-section {
    border-top: 0;
    padding-top: 4px;
    margin-top: 15px;
    margin-bottom: 22px;
  }
  .graph-panel .section-title {
    font: 800 14px/1.4 system-ui,sans-serif;
    margin-bottom: 11px;
    color: #164967;
  }
  .graph-panel .properties-list { gap: 8px; }
  .graph-panel .property-item {
    display: grid; grid-template-columns: 1fr; gap: 4px;
    border: 1px solid #e1ebf1;
    background: #f8fbfd;
    border-radius: 11px;
    padding: 11px 12px;
    min-width: 0;
  }
  .graph-panel .property-key {
    font: 750 11px/1.3 system-ui,sans-serif;
    text-transform: none;
    color: #627a91;
  }
  .graph-panel .property-value {
    min-width: 0;
    font: 500 15px/1.6 system-ui,sans-serif;
    color: #234257;
    overflow-wrap: anywhere;
    word-break: normal;
    white-space: pre-wrap;
  }
  .graph-panel .summary-text,
  .graph-panel .fact-text {
    font: 500 16px/1.7 system-ui,sans-serif;
    color: #28465a;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .graph-panel .label-tag {
    font-size: 12px;
    padding: 7px 10px;
    border-radius: 999px;
    background: #f0f6f9;
    color: #285a76;
  }
  .graph-panel .mobile-detail-footer {
    display: grid;
    grid-template-columns: minmax(0,1fr) auto;
    gap: 9px;
    flex: none;
    padding: 12px 16px max(15px, env(safe-area-inset-bottom, 0px));
    border-top: 1px solid #e0eaf0;
    background: #fff;
    box-shadow: 0 -3px 18px rgba(20,53,79,.05);
  }
  .graph-panel .mobile-detail-footer button {
    min-height: 48px;
    border-radius: 11px;
    font: 750 13px/1.2 system-ui,sans-serif;
    padding: 10px 13px;
    cursor: pointer;
  }
  .graph-panel .mobile-back-button {
    color: #fff;
    border: 1px solid #0c6a90;
    background: #116e94;
  }
  .graph-panel .mobile-technical-button {
    background: #f4f8fb;
    border: 1px solid #d6e5ed;
    color: #315a76;
  }
  .graph-panel .graph-building-hint {
    bottom: 110px;
    max-width: calc(100% - 28px);
    border-radius: 13px;
    font-size: 11px;
    white-space: normal;
  }
  .graph-panel .edge-relation-header {
    font-size: 15px;
    line-height: 1.6;
    overflow-wrap: anywhere;
  }
  .graph-panel button:focus-visible,
  .graph-panel [role="button"]:focus-visible {
    outline: 3px solid #10a2ba;
    outline-offset: 2px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .graph-panel * { animation-duration: .01ms !important; transition-duration: .01ms !important; }
}

/* Keep document entities and fictional conversations unmistakably separate. */
.graph-type-switch{display:flex;gap:4px;padding:4px;border:1px solid #dce7ef;background:#f0f6fa;border-radius:12px;margin-left:auto;margin-right:10px}
.graph-type-switch button{background:transparent;color:#536f82;border:0;border-radius:8px;min-height:34px;padding:7px 12px;font:750 12px/1.25 system-ui,sans-serif;cursor:pointer}
.graph-type-switch button.active{background:#fff;color:#145e80;box-shadow:0 1px 7px #214d7218}
.graph-type-switch button:focus-visible{outline:2px solid #11a1c1;outline-offset:2px}
@media(max-width:767px){
  .graph-panel .panel-header{flex-wrap:wrap;gap:5px}
  .graph-type-switch{order:3;width:100%;margin:4px 0 0}
  .graph-type-switch button{flex:1;min-height:42px}
  .graph-panel .panel-title{max-width:none}
}
</style>
