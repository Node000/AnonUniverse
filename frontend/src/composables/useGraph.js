import { ref, computed, watch } from 'vue'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import axios from 'axios'

export function useGraph(apiBase, currentUser, isDarkMode, callbacks) {
  // callbacks: { cancelEdit, triggerNotificationCheck, applyFilters, activeFilters, isEditing, isAdding, isConnectionEditMode: unused (we own it) }

  const vizContainer = ref(null)
  const loading = ref(true)
  const selectedNode = ref(null)
  const isPanelOpen = ref(false)
  const focusedNodeId = ref(null)
  const showFamous = ref(false)
  const showNewNodes = ref(false)
  const isConnectionEditMode = ref(false)
  let isDraggingNode = false

  let network = null
  let nodesData = new DataSet([])
  let edgesData = new DataSet([])

  const getNetwork = () => network
  const getNodesData = () => nodesData
  const getEdgesData = () => edgesData

  // --- Computed properties ---

  const canDeleteSelectedNode = computed(() => {
    if (!selectedNode.value || !currentUser.logged_in || currentUser.role === 'banned') return false
    const isRoot = selectedNode.value.id === 1 || selectedNode.value.id === '1'
    if (isRoot && nodesData.get().length > 1) return false
    if (selectedNode.value.extension && selectedNode.value.extension.length > 0) return false
    if (currentUser.role !== 'admin') {
      if (!currentUser.quota || (currentUser.quota.deletes >= 1)) return false
    }
    return true
  })

  const deleteDisabledReason = computed(() => {
    if (!selectedNode.value) return ''
    if (!currentUser.logged_in) return '请登录后操作'
    if (currentUser.role === 'banned') return '账号已被封禁'
    const isRoot = selectedNode.value.id === 1 || selectedNode.value.id === '1'
    if (isRoot && nodesData.get().length > 1) return '根节点受保护，在有其他爱音存在时不可删除'
    if (selectedNode.value.extension && selectedNode.value.extension.length > 0) return '此节点尚有子分支，请先删除子图谱节点'
    if (currentUser.role !== 'admin' && currentUser.quota && currentUser.quota.deletes >= 1) return '今日删除配额已用完'
    return '删除该形象'
  })

  const canEditSelectedNode = computed(() => {
    if (!selectedNode.value || !currentUser.logged_in || currentUser.role === 'banned') return false
    if (currentUser.role === 'admin') return true
    return currentUser.quota && currentUser.quota.edits < 10
  })

  const canAddNode = computed(() => {
    if (!currentUser.logged_in || currentUser.role === 'banned') return false
    if (currentUser.role === 'admin') return true
    return currentUser.quota && currentUser.quota.adds < 10
  })

  const editButtonsDisabledReason = computed(() => {
    if (!currentUser.logged_in) return '请登录后操作'
    if (currentUser.role === 'banned') return '账号已被封禁'
    if (currentUser.role !== 'admin') {
      if (callbacks.isAdding && callbacks.isAdding.value && currentUser.quota.adds >= 10) return '今日新增配额已用完'
      if (callbacks.isAdding && !callbacks.isAdding.value && currentUser.quota.edits >= 10) return '今日修改配额已用完'
    }
    return ''
  })

  // --- Core functions ---

  const renderNodes = (data) => {
    if (!data) return

    const connectionCounts = {}
    data.forEach(node => {
      if (!connectionCounts[node.id]) connectionCounts[node.id] = 0
      if (node.extension && Array.isArray(node.extension)) {
        node.extension.forEach(targetId => {
          connectionCounts[node.id]++
          connectionCounts[targetId] = (connectionCounts[targetId] || 0) + 1
        })
      }
    })

    const nodes = data.map(node => {
      let source = node.source
      if (typeof source === 'string') {
        try { source = JSON.parse(source) } catch (e) { source = { name: source, link: '' } }
      }

      let related = node.related
      if (typeof related === 'string') {
        try { related = JSON.parse(related) } catch (e) { related = [] }
      }

      const imageUrl = node.image
        ? (node.image.startsWith('http') ? node.image : `${apiBase}${node.image}`)
        : `${apiBase}/images/default.webp`
      const nodeSize = 34 + Math.min(36, (connectionCounts[node.id] || 0) * 4)

      return {
        ...node,
        source,
        related,
        introduction: node.introduction || '',
        id: node.id,
        label: node.name,
        shape: 'circularImage',
        image: imageUrl,
        size: nodeSize,
        originalSize: nodeSize,
        brokenImage: `${apiBase}/images/default.webp`,
        color: {
          border: '#ff69b4',
          background: isDarkMode.value ? '#1a1a2e' : '#ffffff'
        },
        shapeProperties: { useBorderWithImage: true },
        mass: (connectionCounts[node.id] || 0) + 1,
        fixed: node.id === 1 || node.id === '1'
      }
    })

    const nodeIds = new Set(data.map(n => n.id))
    const edges = []
    data.forEach(node => {
      if (node.extension) {
        node.extension.forEach(targetId => {
          if (nodeIds.has(targetId)) {
            let baseLength = 250
            const rootId = (node.id === 1 || node.id === '1')
            const isMobileGameNode = (node.id === 4 || node.id === '4')
            if (rootId) baseLength = 450
            else if (isMobileGameNode) baseLength = 400
            const jitter = Math.floor(Math.random() * (baseLength * 0.15))
            edges.push({
              id: `${node.id}-${targetId}`,
              from: node.id,
              to: targetId,
              length: baseLength + jitter
            })
          }
        })
      }
    })

    nodesData.update(nodesData.getIds().filter(id => !nodeIds.has(id)).map(id => ({ id, _deleted: true })))
    nodesData.remove(nodesData.getIds().filter(id => !nodeIds.has(id)))
    nodesData.update(nodes)
    edgesData.clear()
    edgesData.add(edges)
    callbacks.applyFilters()
  }

  const fetchGraphData = async () => {
    try {
      const response = await axios.get(`${apiBase}/api/nodes`)
      const data = response.data.nodes
      renderNodes(data)
    } catch (error) {
      console.error('Failed to fetch data:', error)
      loading.value = false
    }
  }

  const focusNode = (nodeId) => {
    const node = nodesData.get(nodeId)
    if (node) {
      if (focusedNodeId.value && focusedNodeId.value !== nodeId) {
        const prevNode = nodesData.get(focusedNodeId.value)
        if (prevNode) nodesData.update({ id: focusedNodeId.value, size: prevNode.originalSize, borderWidth: 3 })
      }
      focusedNodeId.value = nodeId
      isConnectionEditMode.value = false
      nodesData.update({ id: nodeId, size: node.originalSize * 1.5, borderWidth: 6 })
      selectedNode.value = node
      isPanelOpen.value = true
      if (network) {
        network.focus(nodeId, {
          scale: 1,
          offset: { x: 0, y: 0 },
          animation: { duration: 530, easingFunction: 'easeInOutCubic' }
        })
      }
    }
  }

  const resetView = () => {
    if (network) {
      if (focusedNodeId.value) {
        const n = nodesData.get(focusedNodeId.value)
        if (n) nodesData.update({ id: focusedNodeId.value, size: n.originalSize, borderWidth: 3 })
        focusedNodeId.value = null
      }
      const node1 = nodesData.get(1)
      if (node1) {
        network.focus(1, {
          scale: 1,
          animation: { duration: 530, easingFunction: 'easeInOutCubic' }
        })
      } else {
        network.fit({
          animation: { duration: 660, easingFunction: 'easeInOutCubic' }
        })
      }
      isPanelOpen.value = false
      callbacks.activeFilters.value = []
      callbacks.applyFilters()
    }
  }

  const toggleConnectionEditMode = () => {
    isConnectionEditMode.value = !isConnectionEditMode.value
  }

  const handleNodeConnection = async (targetId) => {
    if (!selectedNode.value || currentUser.role !== 'admin') return

    const currentExtensions = selectedNode.value.extension || []
    const isRemoving = currentExtensions.includes(targetId)

    const formData = new FormData()
    formData.append('target_id', targetId)
    formData.append('action', isRemoving ? 'remove' : 'add')
    formData.append('user_id', currentUser.user_id)
    formData.append('nickname', currentUser.nickname)

    try {
      const response = await axios.patch(`${apiBase}/api/nodes/${selectedNode.value.id}/extension`, formData)
      const newExtension = response.data.extension

      nodesData.update({ id: selectedNode.value.id, extension: newExtension })
      selectedNode.value.extension = newExtension

      const edgeId = `${selectedNode.value.id}-${targetId}`
      const reverseEdgeId = `${targetId}-${selectedNode.value.id}`
      const existingEdge = edgesData.get(edgeId) || edgesData.get(reverseEdgeId)

      if (isRemoving) {
        if (existingEdge) edgesData.remove(existingEdge.id)
      } else {
        if (!existingEdge) {
          edgesData.add({
            id: edgeId,
            from: selectedNode.value.id,
            to: targetId,
            color: { color: '#ff69b4', highlight: '#ff1493' },
            width: 2,
            opacity: 0.6
          })
        }
      }

      if (network) {
        network.setOptions({ physics: { enabled: true } })
        network.startSimulation()
        setTimeout(() => {
          if (network) network.setOptions({ physics: { enabled: false } })
        }, 3000)
      }
    } catch (error) {
      console.error(error)
      alert(error.response?.data?.detail || '修改连线失败')
    }
  }

  const saveNodePosition = async () => {
    if (!selectedNode.value || !network) return

    const pos = network.getPositions([selectedNode.value.id])[selectedNode.value.id]
    if (!pos) return

    const formData = new FormData()
    formData.append('x', pos.x)
    formData.append('y', pos.y)
    formData.append('user_id', currentUser.user_id)
    formData.append('nickname', currentUser.nickname)

    try {
      await axios.patch(`${apiBase}/api/nodes/${selectedNode.value.id}/position`, formData)
      alert('位置保存成功')
    } catch (error) {
      alert(error.response?.data?.detail || '保存位置失败')
    }
  }

  // --- initNetwork ---

  const initNetwork = () => {
    const data = { nodes: nodesData, edges: edgesData }
    const options = {
      nodes: {
        borderWidth: 3,
        size: 40,
        color: {
          border: '#ff69b4',
          background: isDarkMode.value ? '#1a1a2e' : '#ffffff',
          highlight: { border: '#ff1493', background: isDarkMode.value ? '#1a1a2e' : '#ffffff' }
        },
        font: {
          color: isDarkMode.value ? '#ffffff' : '#000000',
          size: 14,
          strokeWidth: 2,
          strokeColor: isDarkMode.value ? '#000000' : '#ffffff'
        },
        shapeProperties: { useBorderWithImage: true }
      },
      edges: {
        color: { color: '#ff69b4', highlight: '#ff1493', opacity: 0.6 },
        width: 2,
        arrows: { to: { enabled: false } },
        arrowStrikethrough: false,
        smooth: { enabled: true, type: 'continuous', roundness: 0.5 }
      },
      physics: {
        enabled: true,
        solver: 'barnesHut',
        barnesHut: {
          gravitationalConstant: -2000,
          centralGravity: 0.1,
          springLength: 200,
          springConstant: 0.04,
          damping: 0.5,
          avoidOverlap: 0.2
        },
        stabilization: {
          enabled: true,
          iterations: 500,
          updateInterval: 25,
          fit: true
        },
        adaptiveTimestep: true,
        minVelocity: 0.5
      },
      layout: { randomSeed: 42 },
      interaction: { hover: true, tooltipDelay: 200 }
    }

    if (vizContainer.value) {
      network = new Network(vizContainer.value, data, options)

      network.once('stabilizationIterationsDone', () => {
        loading.value = false
        network.setOptions({ physics: { enabled: false } })
        callbacks.triggerNotificationCheck()
      })

      network.on('dragStart', () => {
        isDraggingNode = true
        network.setOptions({ physics: { enabled: true } })
        network.startSimulation()
      })

      network.on('dragEnd', () => {
        isDraggingNode = false
        network.startSimulation()
      })

      network.on('stabilized', () => {
        if (!isDraggingNode) {
          network.setOptions({ physics: { enabled: false } })
        }
      })
    } else {
      console.error('Viz container is not available')
      return
    }

    // Famous / New nodes animation
    let famousRotationAngle = 0
    let newNodesRotationAngle = 0
    let lastFrameTime = 0
    const FPS_LIMIT = 30
    const FRAME_INTERVAL = 1000 / FPS_LIMIT
    let isZoomingOrPanning = false

    const animateFamousNodes = (timestamp) => {
      if (!lastFrameTime) lastFrameTime = timestamp
      const elapsed = timestamp - lastFrameTime

      if (elapsed > FRAME_INTERVAL) {
        if ((showFamous.value || showNewNodes.value) && network) {
          const timeScale = elapsed / FRAME_INTERVAL
          famousRotationAngle += 0.03 * timeScale
          newNodesRotationAngle += 0.036 * timeScale
          if (!isZoomingOrPanning) {
            network.redraw()
          }
        }
        lastFrameTime = timestamp - (elapsed % FRAME_INTERVAL)
      }
      requestAnimationFrame(animateFamousNodes)
    }
    requestAnimationFrame(animateFamousNodes)

    watch([showFamous, showNewNodes], () => {
      if (network) network.redraw()
    })

    watch(isPanelOpen, (newVal) => {
      if (!newVal) isConnectionEditMode.value = false
    })

    // Zoom/drag optimization
    network.on('zoom', () => {
      isZoomingOrPanning = true
      if (window.zoomTimeout) clearTimeout(window.zoomTimeout)
      window.zoomTimeout = setTimeout(() => { isZoomingOrPanning = false }, 100)
    })

    network.on('dragStart', () => { isZoomingOrPanning = true })
    network.on('dragEnd', () => { isZoomingOrPanning = false })

    // afterDrawing: famous/new node circles
    network.on('afterDrawing', (ctx) => {
      if (!showFamous.value && !showNewNodes.value) return
      const nodes = nodesData.get()
      nodes.forEach(node => {
        const pos = network.getPositions([node.id])[node.id]
        if (!pos) return

        if (showFamous.value && node.is_famous) {
          ctx.save()
          ctx.translate(pos.x, pos.y)
          ctx.rotate(famousRotationAngle)
          ctx.beginPath()
          const radius = (node.size || 40) + 15
          const circumference = 2 * Math.PI * radius
          const dashLen = circumference / 12
          ctx.arc(0, 0, radius, 0, 2 * Math.PI)
          ctx.strokeStyle = '#87CEEB'
          ctx.lineWidth = 6
          ctx.setLineDash([dashLen, dashLen])
          ctx.stroke()
          ctx.restore()
        }

        if (showNewNodes.value && node.new) {
          ctx.save()
          ctx.translate(pos.x, pos.y)
          ctx.rotate(newNodesRotationAngle)
          ctx.beginPath()
          const radius = (node.size || 40) + (node.is_famous && showFamous.value ? 25 : 15)
          const circumference = 2 * Math.PI * radius
          const dashLen = circumference / 12
          ctx.arc(0, 0, radius, 0, 2 * Math.PI)
          ctx.strokeStyle = '#FFA500'
          ctx.lineWidth = 6
          ctx.setLineDash([dashLen, dashLen])
          ctx.stroke()
          ctx.restore()
        }
      })
    })

    // View drag inertia
    let lastTime = 0
    let lastPos = { x: 0, y: 0 }
    let velocity = { x: 0, y: 0 }
    let inertiaFrame = null

    network.on('dragStart', () => {
      if (inertiaFrame) cancelAnimationFrame(inertiaFrame)
      velocity = { x: 0, y: 0 }
    })

    network.on('dragging', () => {
      const now = Date.now()
      const currentView = network.getViewPosition()
      if (lastTime > 0) {
        const dt = now - lastTime
        if (dt > 0) {
          velocity.x = (currentView.x - lastPos.x) / dt
          velocity.y = (currentView.y - lastPos.y) / dt
        }
      }
      lastPos = { ...currentView }
      lastTime = now
    })

    network.on('dragEnd', () => {
      let friction = 0.985
      const step = () => {
        if (Math.abs(velocity.x) < 0.01 && Math.abs(velocity.y) < 0.01) return
        const currentView = network.getViewPosition()
        network.moveTo({
          position: {
            x: currentView.x + velocity.x,
            y: currentView.y + velocity.y
          },
          animation: false
        })
        velocity.x *= friction
        velocity.y *= friction
        inertiaFrame = requestAnimationFrame(step)
      }
      inertiaFrame = requestAnimationFrame(step)
      lastTime = 0
    })

    // Click handler
    network.on('click', (params) => {
      if (params.nodes.length > 0) {
        if (callbacks.isEditing.value || callbacks.isAdding.value) {
          callbacks.cancelEdit()
        }

        const nodeId = params.nodes[0]

        if (isConnectionEditMode.value) {
          if (nodeId !== selectedNode.value.id) {
            handleNodeConnection(nodeId)
          }
          return
        }

        if (focusedNodeId.value === nodeId) {
          const n = nodesData.get(nodeId)
          nodesData.update({ id: nodeId, size: n.originalSize, borderWidth: 3 })
          focusedNodeId.value = null
          isPanelOpen.value = false
        } else {
          focusNode(nodeId)
        }
      } else {
        if (focusedNodeId.value) {
          const n = nodesData.get(focusedNodeId.value)
          if (n) nodesData.update({ id: focusedNodeId.value, size: n.originalSize, borderWidth: 3 })
          focusedNodeId.value = null
        }
        isPanelOpen.value = false
        callbacks.cancelEdit()
      }
    })

    // Hover effects
    network.on('hoverNode', (params) => {
      if (isZoomingOrPanning) return
      const nodeId = params.node
      const n = nodesData.get(nodeId)
      nodesData.update({ id: nodeId, size: n.originalSize * 1.3 })
      document.body.style.cursor = 'pointer'
    })

    network.on('blurNode', (params) => {
      setTimeout(() => {
        const nodeId = params.node
        const n = nodesData.get(nodeId)
        if (n && focusedNodeId.value !== nodeId) {
          nodesData.update({ id: nodeId, size: n.originalSize })
        }
        document.body.style.cursor = 'default'
      }, 0)
    })
  }

  return {
    vizContainer,
    loading,
    selectedNode,
    isPanelOpen,
    focusedNodeId,
    showFamous,
    showNewNodes,
    isConnectionEditMode,
    canDeleteSelectedNode,
    deleteDisabledReason,
    canEditSelectedNode,
    canAddNode,
    editButtonsDisabledReason,
    getNetwork,
    getNodesData,
    getEdgesData,
    fetchGraphData,
    focusNode,
    resetView,
    toggleConnectionEditMode,
    handleNodeConnection,
    saveNodePosition,
    initNetwork
  }
}
