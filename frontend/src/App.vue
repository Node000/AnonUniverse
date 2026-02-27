<script setup>
import { onMounted, onUnmounted, ref, reactive, nextTick, computed } from 'vue'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import axios from 'axios'

const apiBase = import.meta.env.DEV ? 'http://localhost:8000' : ''
const vizContainer = ref(null)
const fileInput = ref(null)
const loading = ref(true)
const selectedNode = ref(null)
const isPanelOpen = ref(false)
const isDropdownOpen = ref(false)
let isDraggingNode = false // Track dragging state for physics optimization
const currentUser = reactive({
  user_id: 'guest',
  nickname: '游客',
  logged_in: false,
  role: 'visitor',
  quota: null
})

const fetchUserInfo = async (userId = 'guest', nickname = '游客') => {
  try {
    const url = `${apiBase}/api/user/info?user_id=${userId}&nickname=${encodeURIComponent(nickname)}`
    console.log('Fetching user info from:', url)
    const response = await axios.get(url)
    Object.assign(currentUser, response.data)
    if (currentUser.role === 'admin') {
      fetchPendingApplications()
    }
  } catch (error) {
    console.error('Failed to fetch user info:', error)
    // If fetch fails but we have stored credentials (not guest),
    // we should still mark user as logged in even if quota/role info is missing
    if (userId !== 'guest') {
       currentUser.user_id = userId
       currentUser.nickname = nickname
       currentUser.logged_in = true
       // Default fallback for failed network calls
       if (!currentUser.role) currentUser.role = 'visitor'
       if (!currentUser.quota) currentUser.quota = { adds: 0, edits: 0, deletes: 0 }
    }
    
    if (error.response) {
      console.error('Data:', error.response.data)
      console.error('Status:', error.response.status)
    }
  }
}

const isEditing = ref(false)
const isAdding = ref(false)
const searchQuery = ref('')
const searchResults = ref([])
const activeFilters = ref([])

// History state
const showHistory = ref(false)
const historyData = ref([])
const historyType = ref('global') // 'global' or 'node'

// Famous Fanwork state
const showFamous = ref(false)
const pendingApplications = ref([])
const showApplyFamousModal = ref(false)
const showPendingApplicationsModal = ref(false)

const canApplyFamous = computed(() => {
  if (!currentUser.logged_in) return false
  if (currentUser.role === 'admin') return true
  return currentUser.quota && currentUser.quota.applies < 1
})

// Site info state
const showSiteInfo = ref(false)

const isHistoryLoading = ref(false)

const editForm = reactive({
  id: null,
  name: '',
  source: { name: '', link: '' },
  related: [],
  tags: '',
  extension: [],
  introduction: '',
  imageFile: null,
  imagePreview: null
})

let network = null
let nodesData = new DataSet([])
let edgesData = new DataSet([])

// Track focused node to handle enlargement state
const focusedNodeId = ref(null)

const canDeleteSelectedNode = computed(() => {
  if (!selectedNode.value || !currentUser.logged_in) return false
  
  // 1. Root node protection (id: 1)
  // Logic: if it is node 1 and there is more than 1 node total, it's the root and can't be deleted.
  const isRoot = selectedNode.value.id === 1 || selectedNode.value.id === '1'
  if (isRoot && nodesData.get().length > 1) return false
  
  // 2. Leaf node check (if it has children in extension array)
  if (selectedNode.value.extension && selectedNode.value.extension.length > 0) return false
  
  // 3. Quota check (for non-admins)
  if (currentUser.role !== 'admin') {
    if (!currentUser.quota || (currentUser.quota.deletes >= 1)) return false
  }
  
  return true
})

const deleteDisabledReason = computed(() => {
  if (!selectedNode.value) return ''
  if (!currentUser.logged_in) return '请登录后操作'
  
  const isRoot = selectedNode.value.id === 1 || selectedNode.value.id === '1'
  if (isRoot && nodesData.get().length > 1) return '根节点受保护，在有其他爱音存在时不可删除'
  if (selectedNode.value.extension && selectedNode.value.extension.length > 0) return '此节点尚有子分支，请先删除子图谱节点'
  
  if (currentUser.role !== 'admin' && currentUser.quota && currentUser.quota.deletes >= 1) return '今日删除配额已用完'
  
  return '删除该形象'
})

const canEditSelectedNode = computed(() => {
  if (!selectedNode.value || !currentUser.logged_in) return false
  if (currentUser.role === 'admin') return true
  return currentUser.quota && currentUser.quota.edits < 1
})

const canAddNode = computed(() => {
  if (!currentUser.logged_in) return false
  if (currentUser.role === 'admin') return true
  return currentUser.quota && currentUser.quota.adds < 1
})

const editButtonsDisabledReason = computed(() => {
  if (!currentUser.logged_in) return '请登录后操作'
  if (currentUser.role !== 'admin') {
    if (isAdding.value && currentUser.quota.adds >= 1) return '今日新增配额已用完'
    if (!isAdding.value && currentUser.quota.edits >= 1) return '今日修改配额已用完'
  }
  return ''
})

const fetchGraphData = async () => {
  try {
    const response = await axios.get(`${apiBase}/api/nodes`)
    const data = response.data.nodes

    renderNodes(data)
    // loading.value = false // Moves to network stabilization event
  } catch (error) {
    console.error('Failed to fetch data:', error)
    loading.value = false
  }
}

const isDarkMode = ref(localStorage.getItem('theme') !== 'light')

// Mouse effect states
const mousePos = reactive({ x: 0, y: 0 })
const rippleActive = ref(false)
const ripples = ref([])
let lastRippleTime = 0 // Track last ripple creation

const handleMouseMove = (e) => {
  mousePos.x = e.clientX
  mousePos.y = e.clientY
  
  // Continuous small ripples on movement - Throttled
  const now = Date.now()
  if (now - lastRippleTime > 40) { // Only create ripple every 80ms
    const id = now + Math.random()
    ripples.value.push({
      id,
      x: e.clientX,
      y: e.clientY,
      type: 'small'
    })
    lastRippleTime = now
    setTimeout(() => {
      ripples.value = ripples.value.filter(r => r.id !== id)
    }, 600)
  }
}

const handleClickRipple = (e) => {
  const id = Date.now()
  ripples.value.push({
    id,
    x: e.clientX,
    y: e.clientY,
    type: 'large'
  })
  // Remove ripple after animation
  setTimeout(() => {
    ripples.value = ripples.value.filter(r => r.id !== id)
  }, 1000)
}

const toggleDarkMode = () => {
  isDarkMode.value = !isDarkMode.value
  localStorage.setItem('theme', isDarkMode.value ? 'dark' : 'light')
  
  if (network) {
    network.setOptions({
      nodes: {
        font: { color: isDarkMode.value ? '#ffffff' : '#000000', strokeColor: isDarkMode.value ? '#000000' : '#ffffff' },
        color: { 
          background: isDarkMode.value ? '#1a1a2e' : '#ffffff', 
          border: '#ff69b4',
          highlight: { background: isDarkMode.value ? '#1a1a2e' : '#ffffff', border: '#ff1493' }
        }
      }
    })
    // Re-render nodes to update per-node background colors
    const updates = nodesData.get().map(n => ({
      id: n.id,
      color: { 
        background: isDarkMode.value ? '#1a1a2e' : '#ffffff', 
        border: '#ff69b4',
        highlight: { background: isDarkMode.value ? '#1a1a2e' : '#ffffff', border: '#ff1493' }
      }
    }))
    nodesData.update(updates)
  }
}

const renderNodes = (data) => {
  if (!data) return; // Guard against empty data

  // Pre-calculate connection counts to determine node size
  const connectionCounts = {}
  data.forEach(node => {
     if (!connectionCounts[node.id]) connectionCounts[node.id] = 0;
     if (node.extension && Array.isArray(node.extension)) {
        node.extension.forEach(targetId => {
           connectionCounts[node.id]++;
           connectionCounts[targetId] = (connectionCounts[targetId] || 0) + 1;
        });
     }
  });
  
  const nodes = data.map(node => {
    // Process potentially stringified JSON data from server
    let source = node.source;
    if (typeof source === 'string') {
      try { source = JSON.parse(source); } catch (e) { source = { name: source, link: '' }; }
    }
    
    let related = node.related;
    if (typeof related === 'string') {
      try { related = JSON.parse(related); } catch (e) { related = []; }
    }

    const imageUrl = node.image ? (node.image.startsWith('http') ? node.image : `${apiBase}${node.image}`) : `${apiBase}/images/default.png`;
    
    // Calculate size based on connections
    const nodeSize = 35 + Math.min(25, (connectionCounts[node.id] || 0) * 2.5);

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
      originalSize: nodeSize, // Store for hover/blur and other effects
      brokenImage: `${apiBase}/images/default.png`,
      color: {
        border: '#ff69b4',
        background: isDarkMode.value ? '#1a1a2e' : '#ffffff'
      },
      shapeProperties: {
         useBorderWithImage: true
      },
      // Give nodes more mass based on their connections to stabilize them
      mass: (connectionCounts[node.id] || 0) + 1,
      // Fix root node at 0,0 to anchor the galaxy
      fixed: node.id === 1 || node.id === '1'
    };
  })

  // Create edges but filter out any that point to non-existent nodes
  const nodeIds = new Set(data.map(n => n.id));
  const edges = []
  data.forEach(node => {
    if (node.extension) {
      node.extension.forEach(targetId => {
        if (nodeIds.has(targetId)) {
          // Increase lengths to match the manual (x,y) layout scale
          let baseLength = 250;
          const rootId = (node.id === 1 || node.id === '1');
          
          // 手游立绘爱音 (id=4)
          const isMobileGameNode = (node.id === 4 || node.id === '4');
          
          if (rootId) baseLength = 450;                 // 核心向外推得更远
          else if (isMobileGameNode) baseLength = 400;  // 手游立绘分支需要更多空间散开

          // 加入 15% 的随机扰动
          const jitter = Math.floor(Math.random() * (baseLength * 0.15));
          
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

  // Clear and update DataSet
  nodesData.update(nodesData.getIds().filter(id => !nodeIds.has(id)).map(id => ({id, _deleted: true}))) // Mark for deletion
  nodesData.remove(nodesData.getIds().filter(id => !nodeIds.has(id))) // Hard remove
  
  nodesData.update(nodes) // Update/Add new ones
  
  edgesData.clear()
  edgesData.add(edges)
  
  applyFilters()
}

const handleSearch = () => {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }
  const q = searchQuery.value.toLowerCase()
  const results = []
  
  // Search nodes
  nodesData.get().forEach(node => {
    if (node.name.toLowerCase().includes(q)) {
      results.push({ type: 'node', id: node.id, name: node.name })
    }
    node.tags.forEach(tag => {
      if (tag.toLowerCase().includes(q) && !results.some(r => r.type === 'tag' && r.name === tag)) {
        results.push({ type: 'tag', name: tag })
      }
    })
  })
  searchResults.value = results.slice(0, 10)
}

const selectSearchResult = (res) => {
  if (res.type === 'node') {
    focusNode(res.id)
    searchQuery.value = ''
    searchResults.value = []
  } else {
    if (!activeFilters.value.includes(res.name)) {
      activeFilters.value.push(res.name)
    }
    searchQuery.value = ''
    searchResults.value = []
    applyFilters()
  }
}

const removeFilter = (tag) => {
  activeFilters.value = activeFilters.value.filter(t => t !== tag)
  applyFilters()
}

const applyFilters = () => {
  if (activeFilters.value.length === 0) {
    nodesData.update(nodesData.get().map(n => ({ id: n.id, opacity: 1 })))
    edgesData.update(edgesData.get().map(e => ({ id: e.id, opacity: 0.6 })))
    return
  }
  
  const visibleNodeIds = new Set()
  const nodeUpdates = nodesData.get().map(node => {
    const matchesAll = activeFilters.value.every(f => node.tags.includes(f))
    if (matchesAll) visibleNodeIds.add(node.id)
    return { id: node.id, opacity: matchesAll ? 1 : 0.2 }
  })
  nodesData.update(nodeUpdates)

  const edgeUpdates = edgesData.get().map(edge => {
    const isVisible = visibleNodeIds.has(edge.from) && visibleNodeIds.has(edge.to)
    return { id: edge.id, opacity: isVisible ? 0.6 : 0.1 }
  })
  edgesData.update(edgeUpdates)
}

const focusNode = (nodeId) => {
  const node = nodesData.get(nodeId)
  if (node) {
    if (focusedNodeId.value && focusedNodeId.value !== nodeId) {
       const prevNode = nodesData.get(focusedNodeId.value)
       if (prevNode) nodesData.update({ id: focusedNodeId.value, size: prevNode.originalSize, borderWidth: 3 })
    }
    focusedNodeId.value = nodeId
    // Highlight focused node by increasing size and border width
    nodesData.update({ id: nodeId, size: node.originalSize * 1.5, borderWidth: 6 })
    
    selectedNode.value = node
    isPanelOpen.value = true
    if (network) {
      network.focus(nodeId, {
        scale: 1,
        animation: { duration: 600, easingFunction: 'easeInOutQuad' }
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
        animation: { duration: 600, easingFunction: 'easeInOutQuad' }
      })
    } else {
      network.fit({ animation: true })
    }
    isPanelOpen.value = false
    activeFilters.value = []
    applyFilters()
  }
}

// Edit / Add Actions
const startEdit = () => {
  isEditing.value = true
  
  // Clean up source if it's a string (due to potential corruption)
  let rawSource = selectedNode.value.source
  if (typeof rawSource === 'string') {
    try { rawSource = JSON.parse(rawSource); } 
    catch(e) { rawSource = { name: rawSource, link: '' }; }
  }
  
  // Clean up related if it's a string or has invalid items
  let rawRelated = selectedNode.value.related || []
  if (typeof rawRelated === 'string') {
    try { rawRelated = JSON.parse(rawRelated); }
    catch(e) { rawRelated = []; }
  }
  if (!Array.isArray(rawRelated)) rawRelated = [];

  Object.assign(editForm, {
    id: selectedNode.value.id,
    name: selectedNode.value.name,
    source: JSON.parse(JSON.stringify(rawSource)),
    related: JSON.parse(JSON.stringify(rawRelated)),
    tags: selectedNode.value.tags.join(','),
    extension: selectedNode.value.extension || [],
    introduction: selectedNode.value.introduction || '',
    imagePreview: selectedNode.value.image
  })
}

const parentIdForNewNode = ref(null)

const startAdd = () => {
  parentIdForNewNode.value = selectedNode.value ? selectedNode.value.id : null
  isAdding.value = true
  isPanelOpen.value = true
  Object.assign(editForm, {
    id: null,
    name: '',
    source: { name: '', link: '' },
    related: [],
    tags: '',
    introduction: '',
    imagePreview: null
  })
}

const cancelEdit = () => {
  isEditing.value = false
  isAdding.value = false
  parentIdForNewNode.value = null
}

// Image Cropping logic
const showCropModal = ref(false)
const rawImageBuf = ref(null)
const cropCanvas = ref(null)
const cropperState = reactive({
  img: new Image(),
  x: 0,
  y: 0,
  scale: 1,
  dragging: false,
  startX: 0,
  startY: 0
})

const handleImageUpload = (e) => {
  const file = e.target.files[0]
  if (file) {
    if (file.size > 2 * 1024 * 1024) {
      alert('图片大小不能超过 2MB')
      return
    }
    const reader = new FileReader()
    reader.onload = (event) => {
      rawImageBuf.value = event.target.result
      cropperState.img = new Image() // Ensure new instance
      cropperState.img.src = event.target.result
      cropperState.img.onload = () => {
        cropperState.x = 0
        cropperState.y = 0
        cropperState.scale = 1
        showCropModal.value = true
        nextTick(() => drawCropCanvas())
      }
    }
    reader.readAsDataURL(file)
  }
  // Reset input value so same file can be uploaded again
  e.target.value = ''
}

const drawCropCanvas = () => {
  const canvas = cropCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const size = 300
  canvas.width = size
  canvas.height = size
  
  ctx.clearRect(0, 0, size, size)
  
  const img = cropperState.img
  const aspect = img.width / img.height
  let drawW, drawH
  if (aspect > 1) {
    drawW = size * cropperState.scale * aspect
    drawH = size * cropperState.scale
  } else {
    drawW = size * cropperState.scale
    drawH = size * cropperState.scale / aspect
  }
  
  ctx.drawImage(img, cropperState.x - drawW/2 + size/2, cropperState.y - drawH/2 + size/2, drawW, drawH)
  
  // Mask
  ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
  ctx.beginPath()
  ctx.rect(0, 0, size, size)
  ctx.arc(size/2, size/2, size/2 * 0.9, 0, Math.PI * 2, true)
  ctx.fill()
  
  // Border
  ctx.strokeStyle = '#ff69b4'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.arc(size/2, size/2, size/2 * 0.9, 0, Math.PI * 2)
  ctx.stroke()
}

const handleCropMouseDown = (e) => {
  cropperState.dragging = true
  cropperState.startX = e.clientX - cropperState.x
  cropperState.startY = e.clientY - cropperState.y
}

const handleCropMouseMove = (e) => {
  if (cropperState.dragging) {
    cropperState.x = e.clientX - cropperState.startX
    cropperState.y = e.clientY - cropperState.startY
    drawCropCanvas()
  }
}

const handleCropMouseUp = () => {
  cropperState.dragging = false
}

const handleCropWheel = (e) => {
  e.preventDefault()
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  cropperState.scale *= delta
  drawCropCanvas()
}

const confirmCrop = () => {
  const canvas = document.createElement('canvas')
  const size = 400
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  
  const img = cropperState.img
  const aspect = img.width / img.height
  let drawW, drawH
  if (aspect > 1) {
    drawW = size * cropperState.scale * aspect
    drawH = size * cropperState.scale
  } else {
    drawW = size * cropperState.scale
    drawH = size * cropperState.scale / aspect
  }
  
  ctx.drawImage(img, (cropperState.x * (size/300)) - drawW/2 + size/2, (cropperState.y * (size/300)) - drawH/2 + size/2, drawW, drawH)
  
  canvas.toBlob((blob) => {
    editForm.imageFile = new File([blob], "avatar.png", { type: "image/png" })
    editForm.imagePreview = URL.createObjectURL(blob)
    showCropModal.value = false
  }, 'image/png')
}

const cancelCrop = () => {
  showCropModal.value = false
}

const addRelated = () => {
  editForm.related.push({ name: '', link: '' })
}

const removeRelated = (index) => {
  editForm.related.splice(index, 1)
}

// Side Panel Drag-to-Scroll Logic
const panelContent = ref(null)
const panelState = reactive({ isDragging: false, startY: 0, scrollStart: 0 })

const handlePanelMouseDown = (e) => {
  panelState.isDragging = true
  panelState.startY = e.pageY - panelContent.value.offsetTop
  panelState.scrollStart = panelContent.value.scrollTop
}

const handlePanelMouseMove = (e) => {
  if (!panelState.isDragging) return
  e.preventDefault()
  const y = e.pageY - panelContent.value.offsetTop
  const walk = (y - panelState.startY) * 1.5
  panelContent.value.scrollTop = panelState.scrollStart - walk
}

const handlePanelMouseUp = () => {
  panelState.isDragging = false
}

const submitForm = async () => {
  if (!editForm.name.trim()) {
    alert('请输入形象名字')
    return
  }
  if (!editForm.source.name.trim()) {
    alert('请输入出处作品名字')
    return
  }

  const formData = new FormData()
  formData.append('name', editForm.name)
  
  // Clean empty links or names from related
  const cleanedRelated = editForm.related.filter(item => item.name.trim() !== '')
  
  formData.append('source', JSON.stringify(editForm.source))
  formData.append('related', JSON.stringify(cleanedRelated))
  formData.append('tags', JSON.stringify(editForm.tags.split(',').map(t => t.trim())))
  formData.append('extension', JSON.stringify(isAdding.value ? [] : editForm.extension))
  formData.append('introduction', editForm.introduction)
  formData.append('user_id', currentUser.user_id)
  formData.append('nickname', currentUser.nickname)
  if (parentIdForNewNode.value) {
    formData.append('parent_id', parentIdForNewNode.value)
    if (isAdding.value && network) {
      const parentPos = network.getPositions([parentIdForNewNode.value])[parentIdForNewNode.value]
      if (parentPos) {
        const angle = Math.random() * 2 * Math.PI
        const distance = 150
        formData.append('x', parentPos.x + Math.cos(angle) * distance)
        formData.append('y', parentPos.y + Math.sin(angle) * distance)
      }
    }
  }
  if (editForm.imageFile) {
    formData.append('image', editForm.imageFile)
  }

  try {
    let resultNode;
    if (isAdding.value) {
      const resp = await axios.post(`${apiBase}/api/nodes`, formData)
      resultNode = resp.data;
      // For adding, we might need to refresh to get correct layout/edges, or we can manually add it.
      // Refreshing is safer for new nodes to ensure links are correct.
      await fetchGraphData()
    } else {
      const resp = await axios.put(`${apiBase}/api/nodes/${editForm.id}`, formData)
      resultNode = resp.data;
      
      // Update local data without full refresh
      nodesData.update({
        id: resultNode.id,
        label: resultNode.name,
        image: resultNode.image.startsWith('http') ? resultNode.image : `${apiBase}${resultNode.image}`,
        // Keep other properties that might be used by vis-network or internal logic
        // We also need to update the data source for the detail panel which reads from selectedNode
      })
      
      // Update selectedNode which updates the side panel
      if (selectedNode.value && selectedNode.value.id === resultNode.id) {
         Object.assign(selectedNode.value, resultNode);
      }
      
      // If we edited relations, edges might need update.
      // Simple edit of name/image doesn't change edges.
      // If 'related' or 'extension' changed, we might need to update edges?
      // The backend 'update_node' takes 'extension'. 
      // If extension changed, edges change.
      // Let's check if extension changed.
      // For now, to meet "update name and image", this is enough. 
      // Use full refresh if edges might have changed? 
      // The user said "update name and image". Assuming structure didn't change heavily.
      // If structure changed, we probably entered 'isAdding' or specific logic.
      // But let's be safe: only avoid fetchGraphData if we just want to update content.
      // To properly handle edge changes locally is complex.
      // Let's assume for "Edit" we just update node data. 
      // If edges need update, a full refresh is safer, but user asked to avoid it.
      // Let's try to update logic: 
      // The server returns the updated node. 
      // If we only update rendering, we update `nodesData`.
      
      // Note: renderNodes calls 'nodesData.update' which merges.
      // But renderNodes also re-calculates edges.
      
      // Let's stick to user request: "Modify detail -> update name and image".
      // We'll update the node in `nodesData` and `selectedNode`.
    }
    
    await fetchUserInfo(currentUser.user_id, currentUser.nickname)
    isEditing.value = false
    isAdding.value = false
    isPanelOpen.value = false
  } catch (error) {
    alert(error.response?.data?.detail || '保存失败')
  }
}

const deleteNode = async () => {
  const confirmName = prompt(`你确定要删除 ${selectedNode.value.name} 吗？请输入名字确认删除`)
  if (confirmName === selectedNode.value.name) {
    try {
      await axios.delete(`${apiBase}/api/nodes/${selectedNode.value.id}?user_id=${currentUser.user_id}&nickname=${currentUser.nickname}`)
      await fetchGraphData()
      await fetchUserInfo(currentUser.user_id, currentUser.nickname)
      isPanelOpen.value = false
    } catch (error) {
      alert(error.response?.data?.detail || '删除失败')
    }
  } else if (confirmName !== null) {
    alert('名字不一致，取消删除')
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
    // Update local dataset position to prevent 'jumping' back if we don't refresh
    // actually vis-network already has the new position since we got it from network.getPositions
    // so we just need to suppress the fetchGraphData
    
    // However, if we don't save to backend, it reverts on reload. We did save.
    // The user doesn't want full re-render.
    alert('位置保存成功')
    // await fetchGraphData() // Removed to prevent re-render
  } catch (error) {
    alert(error.response?.data?.detail || '保存位置失败')
  }
}

const loginWithBangumi = async () => {
  try {
    const response = await axios.get(`${apiBase}/api/auth/login`)
    window.location.href = response.data.url
  } catch (error) {
    alert('无法获取登录链接')
  }
}

const logout = () => {
  localStorage.removeItem('user_id')
  localStorage.removeItem('nickname')
  fetchUserInfo('guest', '游客')
  isDropdownOpen.value = false
}

const toggleDropdown = (e) => {
  e.stopPropagation()
  if (isDropdownOpen.value) {
    isDropdownOpen.value = false
  } else {
    isDropdownOpen.value = true
  }
}

const toggleHistory = async (nodeId = null) => {
  if (showHistory.value) {
    showHistory.value = false
    return
  }
  showHistory.value = true // Show modal immediately
  await fetchHistory(nodeId)
}

const fetchHistory = async (nodeId = null) => {
  isHistoryLoading.value = true
  try {
    const url = nodeId ? `${apiBase}/api/history?node_id=${nodeId}` : `${apiBase}/api/history`
    const response = await axios.get(url)
    historyData.value = response.data
    historyType.value = nodeId ? 'node' : 'global'
  } catch (error) {
    console.error('Failed to fetch history:', error)
  } finally {
    isHistoryLoading.value = false
  }
}

const fetchPendingApplications = async () => {
  if (currentUser.role !== 'admin') return
  try {
    const response = await axios.get(`${apiBase}/api/applications`, {
      params: { user_id: currentUser.user_id }
    })
    pendingApplications.value = response.data
  } catch (error) {
    console.error('Failed to fetch applications:', error)
  }
}

const openPendingApplications = () => {
  fetchPendingApplications()
  showPendingApplicationsModal.value = true
}

const submitFamousApplication = async () => {
  if (!selectedNode.value) return
  
  const formData = new FormData()
  formData.append('node_id', selectedNode.value.id)
  formData.append('user_id', currentUser.user_id)
  formData.append('nickname', currentUser.nickname)
  
  try {
    await axios.post(`${apiBase}/api/applications`, formData)
    alert('申请已提交')
    showApplyFamousModal.value = false
    await fetchUserInfo(currentUser.user_id, currentUser.nickname)
  } catch (error) {
    alert(error.response?.data?.detail || '申请失败')
  }
}

const processApplication = async (appId, action) => {
  const app = pendingApplications.value.find(a => a.id === appId)
  const nodeId = app ? app.node_id : null
  
  const formData = new FormData()
  formData.append('action', action)
  formData.append('user_id', currentUser.user_id)
  formData.append('nickname', currentUser.nickname)
  
  try {
    await axios.post(`${apiBase}/api/applications/${appId}/process`, formData)
    await fetchPendingApplications()
    if (action === 'approve' && nodeId) {
      const updatedNode = nodesData.get(nodeId)
      if (updatedNode) {
        nodesData.update({ id: nodeId, is_famous: true })
        if (selectedNode.value && selectedNode.value.id === nodeId) {
          selectedNode.value.is_famous = true
        }
      }
    }
  } catch (error) {
    alert(error.response?.data?.detail || '处理失败')
  }
}

const toggleFamousStatus = async () => {
  if (!selectedNode.value || currentUser.role !== 'admin') return
  
  const newStatus = !selectedNode.value.is_famous
  const formData = new FormData()
  formData.append('is_famous', newStatus)
  formData.append('user_id', currentUser.user_id)
  formData.append('nickname', currentUser.nickname)
  
  try {
    await axios.patch(`${apiBase}/api/nodes/${selectedNode.value.id}/famous`, formData)
    nodesData.update({ id: selectedNode.value.id, is_famous: newStatus })
    selectedNode.value.is_famous = newStatus
  } catch (error) {
    alert(error.response?.data?.detail || '修改失败')
  }
}

const toggleSiteInfo = (e) => {
  if (e) e.stopPropagation()
  showSiteInfo.value = !showSiteInfo.value
}

const closePopups = () => {
  showHistory.value = false
  showSiteInfo.value = false
}

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
      font: { color: isDarkMode.value ? '#ffffff' : '#000000', size: 14, strokeWidth: 2, strokeColor: isDarkMode.value ? '#000000' : '#ffffff' },
      shapeProperties: {
         useBorderWithImage: true
      }
    },
    edges: {
      color: { color: '#ff69b4', highlight: '#ff1493', opacity: 0.6 },
      width: 2,
      arrows: { to: { enabled: false } },
      arrowStrikethrough: false,
      smooth: {
        enabled: true,
        type: 'continuous',
        roundness: 0.5
      }
    },
    physics: {
      enabled: true,
      solver: 'barnesHut',
      barnesHut: {
        gravitationalConstant: -2000,
        centralGravity: 0.1, // Increase slightly to help convergence
        springLength: 200,
        springConstant: 0.04,
        damping: 0.5,
        avoidOverlap: 0.2 // Increase slightly
      },
      stabilization: {
        enabled: true,
        iterations: 500, // Reduced from 1000 for faster load
        updateInterval: 25,
        fit: true
      },
      adaptiveTimestep: true,
      minVelocity: 0.5 // Stop sooner
    },
    layout: {
      randomSeed: 42
    },
    interaction: {
      hover: true,
      tooltipDelay: 200
    }
  }

  if (vizContainer.value) {
    network = new Network(vizContainer.value, data, options)
    
    // 性能优化：稳定后关闭物理引擎，并隐藏加载动画
    network.once("stabilizationIterationsDone", () => {
      loading.value = false
      network.setOptions({ physics: { enabled: false } })
    })
    
    // 拖拽时标记状态并开启物理引擎，通过 simulation 确保即使微小移动也激活
    network.on("dragStart", (params) => {
       isDraggingNode = true
       network.setOptions({ physics: { enabled: true } })
       network.startSimulation();
    })
    
    // 拖拽结束时重置状态，物理引擎会在稳定后自动关闭
    network.on("dragEnd", (params) => {
       isDraggingNode = false
       // Force a re-simulation to ensure settling animation plays out
       network.startSimulation();
    })

    // 仅当非拖拽状态且网络趋于稳定时才关闭物理引擎
    network.on("stabilized", () => {
       if (!isDraggingNode) {
          network.setOptions({ physics: { enabled: false } })
       }
    })

  } else {
    console.error('Viz container is not available')
    return
  }

  let famousRotationAngle = 0;
  let lastFrameTime = 0;
  const FPS_LIMIT = 30;
  const FRAME_INTERVAL = 1000 / FPS_LIMIT;
  
  let isZoomingOrPanning = false; // Flag to skip redraw during interaction

  const animateFamousNodes = (timestamp) => {
    // Basic throttling
    if (!lastFrameTime) lastFrameTime = timestamp;
    const elapsed = timestamp - lastFrameTime;

    if (elapsed > FRAME_INTERVAL) {
      if (showFamous.value && network) {
        // Increment angle based on time to be smooth regardless of frame rate
        famousRotationAngle += 0.03 * (elapsed / FRAME_INTERVAL);
        
        // Only trigger redraw if NOT zooming/panning to avoid fighting for resources
        if (!isZoomingOrPanning) {
           network.redraw();
        }
        // If zooming/panning, vis-network redraws itself, which triggers afterDrawing anyway, so we just update the angle.
      }
      lastFrameTime = timestamp - (elapsed % FRAME_INTERVAL);
    }
    
    requestAnimationFrame(animateFamousNodes);
  };
  requestAnimationFrame(animateFamousNodes);

  // Optimize: Listen to zoom/drag to prevent redundant redraws
  network.on("zoom", () => {
    isZoomingOrPanning = true;
    if (window.zoomTimeout) clearTimeout(window.zoomTimeout);
    window.zoomTimeout = setTimeout(() => {
      isZoomingOrPanning = false;
    }, 100);
  });
  
  network.on("dragStart", () => {
     isZoomingOrPanning = true;
  });
  
  network.on("dragEnd", () => {
     isZoomingOrPanning = false; // Resume managed redraws
  });

  network.on("afterDrawing", (ctx) => {
    if (!showFamous.value) return;
    const nodes = nodesData.get();
    nodes.forEach(node => {
      if (node.is_famous) {
        const pos = network.getPositions([node.id])[node.id];
        if (pos) {
          ctx.save();
          ctx.translate(pos.x, pos.y);
          ctx.rotate(famousRotationAngle);
          ctx.beginPath();
          const radius = (node.size || 40) + 15;
          const circumference = 2 * Math.PI * radius;
          const dashLen = circumference / 12; // 6 segments, each with 1 solid and 1 gap
          ctx.arc(0, 0, radius, 0, 2 * Math.PI);
          ctx.strokeStyle = '#87CEEB';
          ctx.lineWidth = 6;
          ctx.setLineDash([dashLen, dashLen]);
          ctx.stroke();
          ctx.restore();
        }
      }
    });
  });

  // View Drag Inertia Logic
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
        // Calculate velocity (change in view position per ms)
        velocity.x = (currentView.x - lastPos.x) / dt
        velocity.y = (currentView.y - lastPos.y) / dt
      }
    }
    lastPos = { ...currentView }
    lastTime = now
  })

  network.on('dragEnd', () => {
    let friction = 0.985 // High friction (less speed loss per frame)
    const step = () => {
      // Stop when speed is very low
      if (Math.abs(velocity.x) < 0.01 && Math.abs(velocity.y) < 0.01) {
        return
      }
      
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
    lastTime = 0 // Reset for next drag
  })

  network.on('click', (params) => {
    if (params.nodes.length > 0) {
      if (isEditing.value || isAdding.value) {
        cancelEdit()
      }
      
      const nodeId = params.nodes[0]
      if (focusedNodeId.value === nodeId) {
        // Deselect if clicking the same node
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
      cancelEdit()
    }
  })
  
  network.on('hoverNode', (params) => {
     // 优化：缩放或拖动时禁用悬停效果，避免重绘导致卡顿
     if (isZoomingOrPanning) return;
     const nodeId = params.node
     const n = nodesData.get(nodeId)
     // Increase size slightly on hover based on its own original size
     nodesData.update({id: nodeId, size: n.originalSize * 1.3})
     document.body.style.cursor = 'pointer'
  })
  
  network.on('blurNode', (params) => {
      // 优化：允许恢复节点大小，并将此操作放入下一个宏任务，避免与缩放事件冲突
      setTimeout(() => {
        const nodeId = params.node
        const n = nodesData.get(nodeId)
        // Return back to its own original size (only if not focused)
        if (n && focusedNodeId.value !== nodeId) {
          nodesData.update({id: nodeId, size: n.originalSize})
        }
        document.body.style.cursor = 'default'
      }, 0);
  })
}

onMounted(async () => {
  // Check URL for callback params
  const params = new URLSearchParams(window.location.search)
  const userIdFromUrl = params.get('user_id')
  const nicknameFromUrl = params.get('nickname')

  if (userIdFromUrl && nicknameFromUrl) {
    console.log("Found auth params in URL, saving to storage:", userIdFromUrl, nicknameFromUrl);
    localStorage.setItem('user_id', userIdFromUrl)
    localStorage.setItem('nickname', nicknameFromUrl)
    
    // Update local state immediately before fetching to ensure UI reflects login status
    // independent of network latency or potential fetch failures
    currentUser.user_id = userIdFromUrl
    currentUser.nickname = nicknameFromUrl
    currentUser.logged_in = true
    
    // IMPORTANT: Fetch info using the URL values directly to avoid any race condition
    await fetchUserInfo(userIdFromUrl, nicknameFromUrl)
    
    // Clean up URL securely without causing a reload or navigation
    // Only replace state if we are sure we've processed the login
    try {
      const url = new URL(window.location.href);
      url.searchParams.delete('user_id');
      url.searchParams.delete('nickname');
      window.history.replaceState({}, '', url.toString());
    } catch (e) {
      console.error("Failed to clean URL params", e);
    }
  } else {
    // Normal load from storage
    const savedUserId = localStorage.getItem('user_id') || 'guest'
    const savedNickname = localStorage.getItem('nickname') || '游客'
    await fetchUserInfo(savedUserId, savedNickname)
  }
  
  await fetchGraphData()
  initNetwork()

  window.addEventListener('click', (e) => {
    isDropdownOpen.value = false
    closePopups()
    handleClickRipple(e)
  })
  
  window.addEventListener('mousemove', handleMouseMove)
})

onUnmounted(() => {
  window.removeEventListener('mousemove', handleMouseMove)
})
</script>

<template>
  <div class="app-container" :class="{ 'light-mode': !isDarkMode }">
    <!-- Mouse Effects -->
    <div v-for="ripple in ripples" :key="ripple.id" 
         class="click-ripple" 
         :class="ripple.type"
         :style="{ left: ripple.x + 'px', top: ripple.y + 'px' }">
    </div>

    <!-- Loading Animation -->
    <div v-if="loading" class="loading-overlay">
      <div class="loader"></div>
      <p>正在加载千早爱音宇宙...</p>
    </div>

    <!-- UI Buttons -->
    <div class="ui-layer top-left">
      <div class="left-controls-container" style="display: flex; flex-direction: column; gap: 10px;">
        <div class="left-controls">
          <button class="home-btn pink-btn" @click="resetView">回到中心</button>
          <button class="history-btn pink-btn" @click.stop="toggleHistory()">全站历史</button>
          <button class="theme-toggle" @click="toggleDarkMode" :class="{ 'dark-mode-btn': isDarkMode }">
            <!-- Sun (Light Mode) Icon -->
            <svg v-if="!isDarkMode" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="5" />
              <path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M17.66 6.34l1.42-1.42" />
            </svg>
            <!-- Moon (Dark Mode) Icon -->
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
            </svg>
          </button>
        </div>
        <div class="left-controls-row2" style="display: flex; gap: 10px;">
          <button 
            class="famous-toggle-btn" 
            :class="{ active: showFamous }" 
            @click="showFamous = !showFamous"
          >
            知名二创显示
          </button>
          <button 
            v-if="currentUser.role === 'admin'" 
            class="famous-pending-btn" 
            @click="openPendingApplications"
          >
            待认证：{{ pendingApplications.length }}
          </button>
        </div>
      </div>
    </div>

    <div class="ui-layer top-right">
      <div class="header-controls">
        <div 
          class="user-status" 
          :class="[currentUser.logged_in ? 'login-active' : 'login-guest', isDropdownOpen ? 'dropdown-active' : '']" 
          @click="toggleDropdown"
        >
          {{ currentUser.logged_in ? `已登录：${currentUser.nickname}` : '未登录' }}
          <Transition name="fade">
            <div class="user-dropdown" v-if="isDropdownOpen" @click.stop>
              <template v-if="!currentUser.logged_in">
                <button 
                  class="login-action-btn" 
                  @click="loginWithBangumi"
                  title="使用 Bangumi 账号授权登录以获得更多权限"
                >使用 Bangumi 账号登录</button>
              </template>
              <template v-else>
                <div class="user-role-badge" :class="currentUser.role">
                  {{ currentUser.role === 'admin' ? '管理员' : '普通用户' }}
                </div>
                <div class="quota-info">
                  <div class="quota-item">
                    <span>新增</span>
                    <span class="quota-num">{{ currentUser.role === 'admin' ? '∞' : (1 - currentUser.quota.adds) }}</span>
                  </div>
                  <div class="quota-item">
                    <span>修改</span>
                    <span class="quota-num">{{ currentUser.role === 'admin' ? '∞' : (1 - currentUser.quota.edits) }}</span>
                  </div>
                  <div class="quota-item">
                    <span>删除</span>
                    <span class="quota-num">{{ currentUser.role === 'admin' ? '∞' : (1 - currentUser.quota.deletes) }}</span>
                  </div>
                  <div class="quota-item">
                    <span>申请</span>
                    <span class="quota-num">{{ currentUser.role === 'admin' ? '∞' : (1 - (currentUser.quota.applies || 0)) }}</span>
                  </div>
                </div>
                <button @click="logout" class="logout-btn">退出登录</button>
              </template>
            </div>
          </Transition>
        </div>
      </div>
    </div>

    <div class="ui-layer bottom-left" :class="{ 'panel-up': showSiteInfo }">
      <div class="search-container">
        <div class="active-filters">
          <span v-for="tag in activeFilters" :key="tag" class="filter-tag">
            {{ tag }}
            <i @click="removeFilter(tag)">×</i>
          </span>
        </div>
        <input 
          v-model="searchQuery" 
          placeholder="搜索形象或标签..." 
          @input="handleSearch"
        >
        <div v-if="searchResults.length > 0" class="search-results">
          <div 
            v-for="res in searchResults" 
            :key="res.id" 
            class="search-item"
            @click="selectSearchResult(res)"
          >
            <span class="res-type">{{ res.type === 'node' ? '形象' : '标签' }}</span>
            <span class="res-name">{{ res.name }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="ui-layer bottom-right" :class="{ 'panel-up': showSiteInfo }">
      <button class="info-btn pink-btn" @click.stop="toggleSiteInfo">网站信息</button>
    </div>

    <!-- Graph Container -->
    <div 
      ref="vizContainer" 
      class="graph-container" 
      :class="{ 'shifted': isPanelOpen }"
    ></div>

    <!-- Right Panel -->
    <Transition name="slide">
      <div v-if="isPanelOpen" class="side-panel">
        
        <div 
          class="panel-content"
          ref="panelContent"
          @mousedown="handlePanelMouseDown"
          @mousemove="handlePanelMouseMove"
          @mouseup="handlePanelMouseUp"
          @mouseleave="handlePanelMouseUp"
        >
          <!-- Node History Button (Pink, Round, SVG Icon) - Moved inside to scroll with content -->
          <button 
            v-if="!isEditing && !isAdding" 
            class="node-update-history-btn-round" 
            title="更新记录"
            @click.stop="toggleHistory(selectedNode.id)"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>

          <!-- Apply Famous Button -->
          <button 
            v-if="!isEditing && !isAdding && selectedNode && !selectedNode.is_famous" 
            class="node-apply-famous-btn-round" 
            :class="{ disabled: !canApplyFamous }"
            title="申请知名二创"
            @click.stop="canApplyFamous ? showApplyFamousModal = true : null"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
          </button>
          
          <!-- View Mode -->
          <template v-if="!isEditing && !isAdding && selectedNode">
            <!-- Close Button (Moved inside to scroll with content) -->
            <button class="panel-inner-close-btn" @click="isPanelOpen = false" title="关闭面板">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>

            <div class="image-container">
              <img 
                :src="selectedNode.image.startsWith('http') ? selectedNode.image : `${apiBase}${selectedNode.image}`" 
                :alt="selectedNode.name"
                onerror="this.src='https://via.placeholder.com/200/ff69b4/ffffff?text=?'"
              >
            </div>
            
            <h2 class="node-name">
              <span v-if="selectedNode.is_famous" title="已认证知名二创" style="color: #ff69b4; margin-right: 5px; cursor: help;">★</span>
              {{ selectedNode.name }}
            </h2>
            
            <div class="info-item">
              <label>出处：</label>
              <a v-if="selectedNode.source.link" :href="selectedNode.source.link" target="_blank" class="info-link">{{ selectedNode.source.name }}</a>
              <span v-else>{{ selectedNode.source.name }}</span>
            </div>

            <div class="info-item" v-if="selectedNode.introduction">
              <label>介绍：</label>
              <span class="info-intro">{{ selectedNode.introduction }}</span>
            </div>
            
            <div class="info-item" v-if="selectedNode.tags && selectedNode.tags.length > 0">
              <label>标签：</label>
              <div class="tag-list">
                <span v-for="tag in selectedNode.tags" :key="tag" class="tag">{{ tag }}</span>
              </div>
            </div>
            
            <div class="info-item" v-if="selectedNode.related && selectedNode.related.length > 0">
              <label>相关作品：</label>
              <div class="related-list">
                <div v-for="(item, idx) in selectedNode.related" :key="idx" class="related-item">
                  <a v-if="item.link" :href="item.link" target="_blank" class="info-link">{{ item.name }}</a>
                  <span v-else>{{ item.name }}</span>
                </div>
              </div>
            </div>

            <div class="action-buttons-container" style="display: flex; flex-direction: column; gap: 10px; margin-top: 20px;">
              <div class="action-buttons" style="margin-top: 0;">
                <button 
                  class="btn edit" 
                  :disabled="!canEditSelectedNode" 
                  :title="!canEditSelectedNode ? '今日修改配额已用完' : ''"
                  @click="startEdit"
                >修改</button>
                <button 
                  class="btn add" 
                  :disabled="!canAddNode"
                  :title="!canAddNode ? '今日新增配额已用完' : ''"
                  @click="startAdd"
                >新增</button>
                <button 
                  class="btn delete" 
                  :class="{ 'disabled-btn': !canDeleteSelectedNode }" 
                  :disabled="!canDeleteSelectedNode"
                  @click="deleteNode"
                  :title="deleteDisabledReason"
                >删除</button>
              </div>
              <div class="action-buttons" v-if="currentUser.role === 'admin'" style="margin-top: 0;">
                <button 
                  class="btn save-pos" 
                  @click="saveNodePosition"
                  title="保存当前节点位置"
                >保存位置</button>
                <button 
                  class="btn famous-toggle" 
                  @click="toggleFamousStatus"
                  title="切换知名二创状态"
                  style="background: #87CEEB;"
                >{{ selectedNode.is_famous ? '取消知名二创' : '设为知名二创' }}</button>
              </div>
            </div>
          </template>

          <!-- Edit/Add Mode -->
          <template v-else>
            <h2 class="node-name">{{ isAdding ? '新增形象' : '修改形象' }}</h2>
            
            <div class="image-container editable" @click="fileInput.click()">
              <template v-if="editForm.imagePreview">
                <img :src="editForm.imagePreview">
                <div class="hover-mask">
                  <span>上传图片</span>
                </div>
              </template>
              <div v-else class="upload-placeholder">
                <span>暂无图片</span>
                <small>点击上传</small>
              </div>
              <input type="file" ref="fileInput" hidden @change="handleImageUpload" accept="image/*">
            </div>

            <div class="input-group">
              <label>形象名字</label>
              <input v-model="editForm.name" placeholder="名字">
            </div>

            <div class="input-group">
              <label>出处</label>
              <div class="pair-input">
                <input v-model="editForm.source.name" placeholder="作品名字">
                <input v-model="editForm.source.link" placeholder="链接 (可选)">
              </div>
            </div>

            <div class="input-group">
              <label>介绍</label>
              <textarea v-model="editForm.introduction" placeholder="简单介绍一下这个版本/形象..." rows="3"></textarea>
            </div>

            <div class="input-group">
              <label>标签 (逗号分隔)</label>
              <input v-model="editForm.tags" placeholder="标签1, 标签2">
            </div>

            <div class="input-group">
              <label>相关作品</label>
              <div v-for="(item, index) in editForm.related" :key="index" class="pair-input-row">
                <div class="pair-input">
                  <input v-model="item.name" placeholder="名字">
                  <input v-model="item.link" placeholder="链接 (可选)">
                </div>
                <button class="remove-btn" @click="removeRelated(index)">×</button>
              </div>
              <button class="add-btn" @click="addRelated">+ 添加作品</button>
            </div>

            <div class="form-actions">
              <button class="btn confirm" @click="submitForm">确认</button>
              <button class="btn cancel" @click="cancelEdit">取消</button>
            </div>
          </template>
        </div>
      </div>
    </Transition>

    <!-- History Modal -->
    <Transition name="fade">
      <div v-if="showHistory" class="modal-overlay" @click="showHistory = false">
        <div class="history-modal" @click.stop>
          <div class="modal-header">
            <h3>{{ historyType === 'global' ? '全站历史记录' : `${selectedNode?.name} 的修改记录` }}</h3>
          </div>
          <div class="history-list">
            <div v-if="isHistoryLoading" class="history-loading-container">
              <div class="mini-loader"></div>
              <span>加载中...</span>
            </div>
            <template v-else>
              <div v-if="historyData.length === 0" class="no-history">暂无记录</div>
              <div v-for="(item, idx) in historyData" :key="idx" class="history-item">
                <span class="history-time">[{{ item.time }}]</span>
                <span class="history-user" :class="item.role">[{{ item.nickname }}]</span>
                <span v-if="item.action === 'apply_famous'"> 申请 </span>
                <span v-else-if="item.action === 'approve_famous'"> 同意了 </span>
                <span v-else-if="item.action === 'reject_famous'"> 拒绝了 </span>
                <span v-else> 进行了 </span>
                <span class="history-action" :class="item.action">
                  {{ item.action === 'add' ? '新增' : item.action === 'edit' ? '修改' : item.action === 'delete' ? '删除' : '' }}
                </span>
                <span v-if="historyType === 'global' || item.action.includes('famous')">
                  <span v-if="!item.action.includes('famous')"> 形象 </span>
                  <span class="history-node-link" @click="focusNode(item.node_id); showHistory = false">
                    {{ item.node_name }}
                  </span>
                  <span v-if="item.action === 'apply_famous'"> 为<span style="color: #87CEEB;">知名二创</span> </span>
                  <span v-if="item.action === 'approve_famous' || item.action === 'reject_famous'"> 的<span style="color: #87CEEB;">知名二创</span>申请 </span>
                </span>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Site Info Bottom Panel -->
    <Transition name="slide-up">
      <div v-if="showSiteInfo" class="site-info-panel" @click.stop>
        <div class="site-info-grid">
          <div class="info-section">
            <h4>开发者</h4>
            <a href="https://space.bilibili.com/365169149" target="_blank" class="info-link">空之堇</a>
          </div>
          <div class="info-section">
            <h4>特别鸣谢</h4>
            <a href="https://space.bilibili.com/3493081661836152" target="_blank" class="info-link">璀璨水晶Crystal</a>
          </div>
          <div class="info-section">
            <h4>Github仓库</h4>
            <a href="https://github.com/Node000/AnonUniverse" target="_blank" class="info-link">AnonUniverse</a>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Apply Famous Modal -->
    <div v-if="showApplyFamousModal" class="modal-overlay" @click="showApplyFamousModal = false">
      <div class="apply-famous-modal" @click.stop style="background: #1a1a2e; border: 1px solid #ff69b4; border-radius: 10px; width: 320px; display: flex; flex-direction: column;">
        <div class="modal-header" style="display: flex; justify-content: center; align-items: center; padding: 15px 20px; border-bottom: 1px solid rgba(255, 105, 180, 0.3);">
          <h3 style="margin: 0; color: #ff69b4;">申请知名二创</h3>
        </div>
        <div class="modal-body" style="padding: 20px; text-align: center; line-height: 1.6; color: #fff;">
          <p>作品为剧情类二创</p>
          <p>B站播放量≥20W</p>
        </div>
        <div class="modal-footer" style="display: flex; justify-content: center; gap: 40px; padding: 0 10px 20px 10px;">
          <button class="btn confirm" @click="submitFamousApplication">确认</button>
          <button class="btn cancel" @click="showApplyFamousModal = false">取消</button>
        </div>
      </div>
    </div>

    <!-- Pending Applications Modal -->
    <div v-if="showPendingApplicationsModal" class="modal-overlay" @click="showPendingApplicationsModal = false">
      <div class="pending-applications-modal" @click.stop style="background: #1a1a2e; border: 1px solid #ff69b4; border-radius: 10px; width: 90%; max-width: 500px; max-height: 80vh; display: flex; flex-direction: column;">
        <div class="modal-header" style="position: relative; display: flex; justify-content: center; align-items: center; padding: 15px 20px; border-bottom: 1px solid rgba(255, 105, 180, 0.3);">
          <h3 style="margin: 0; color: #ff69b4;">待认证申请</h3>
          <button class="close-btn" @click="showPendingApplicationsModal = false" style="position: absolute; right: 15px; top: 50%; transform: translateY(-50%); color: #ff69b4; background: none; border: none; font-size: 24px; cursor: pointer;">×</button>
        </div>
        <div class="modal-body" style="padding: 20px; overflow-y: auto; flex: 1;">
          <div v-if="pendingApplications.length === 0" style="text-align: center; color: #888;">暂无申请</div>
          <div v-for="app in pendingApplications" :key="app.id" style="display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); gap: 10px;">
            <div style="flex: 1; word-break: break-all; color: #fff;">
              <span style="color: #50e3c2;">{{ app.nickname }}</span> 申请 
              <span 
                style="color: #ff69b4; cursor: pointer; text-decoration: underline;" 
                @click="focusNode(app.node_id); showPendingApplicationsModal = false"
              >{{ app.node_name }}</span> 
              为<span style="color: #87CEEB;">知名二创</span>
            </div>
            <div style="display: flex; gap: 10px; flex-shrink: 0;">
              <button class="btn confirm" style="padding: 5px 10px; font-size: 12px;" @click="processApplication(app.id, 'approve')">同意</button>
              <button class="btn delete" style="padding: 5px 10px; font-size: 12px;" @click="processApplication(app.id, 'reject')">拒绝</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Crop Modal -->
    <div v-if="showCropModal" class="crop-modal-overlay">
      <div class="crop-modal">
        <h3>裁剪图片</h3>
        <p class="crop-tip">滚轮缩放，左键拖动</p>
        <div 
          class="canvas-container"
          @mousedown="handleCropMouseDown"
          @mousemove="handleCropMouseMove"
          @mouseup="handleCropMouseUp"
          @mouseleave="handleCropMouseUp"
          @wheel="handleCropWheel"
        >
          <canvas ref="cropCanvas"></canvas>
        </div>
        <div class="crop-actions">
          <button class="btn confirm" @click="confirmCrop">确认</button>
          <button class="btn cancel" @click="cancelCrop">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
.app-container {
  width: 100vw;
  height: 100vh;
  position: relative;
  overflow: hidden;
  background: #0a0a0f;
  transition: background 0.5s ease, color 0.5s ease;
}

/* Mouse Effects */
.click-ripple {
  position: fixed;
  border: 1.5px solid #ff69b4;
  background: transparent;
  border-radius: 50%;
  pointer-events: none;
  z-index: 9998;
  transform: translate(-50%, -50%);
}

.click-ripple.small {
  animation: small-ripple-animation 0.6s ease-out forwards;
}

.click-ripple.large {
  border-width: 2px;
  animation: large-ripple-animation 1s ease-out forwards;
}

@keyframes small-ripple-animation {
  0% {
    width: 0;
    height: 0;
    opacity: 0.5;
  }
  100% {
    width: 30px;
    height: 30px;
    opacity: 0;
  }
}

@keyframes large-ripple-animation {
  0% {
    width: 0;
    height: 0;
    opacity: 0.8;
  }
  100% {
    width: 120px;
    height: 120px;
    opacity: 0;
  }
}

.app-container.light-mode {
  background: #f0f0f5;
  color: #1a1a2e;
}

.app-container.light-mode .side-panel {
  background: #ffffff;
  border-left: 1px solid rgba(0, 0, 0, 0.1);
  box-shadow: -10px 0 30px rgba(0, 0, 0, 0.05);
}

.app-container.light-mode .node-name,
.app-container.light-mode .info-item span,
.app-container.light-mode .related-item span,
.app-container.light-mode .input-group label {
  color: #1a1a2e;
}

.app-container.light-mode .input-group input,
.app-container.light-mode .input-group textarea,
.app-container.light-mode .pair-input input {
  background: #fdfdfd;
  color: #1a1a2e;
  border-color: rgba(255, 105, 180, 0.5);
}

.app-container.light-mode .user-dropdown {
  background: #ffffff;
  color: #1a1a2e;
  border: 1px solid #ff69b4;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.app-container.light-mode .user-dropdown button {
  color: #1a1a2e;
}

.app-container.light-mode .user-dropdown button:hover {
  background: rgba(255, 105, 180, 0.1);
}

.app-container.light-mode .login-guest {
  background: #333;
  color: #fff;
  border: 1px solid #1a1a2e;
}

.app-container.light-mode .login-guest:not(.dropdown-active):hover {
  background: #000;
  box-shadow: 0 0 15px rgba(0, 0, 0, 0.2);
}

.app-container.light-mode .login-active {
  background: #2d9a8a;
  color: #fff;
  border: 1px solid #247a6d;
}

.app-container.light-mode .login-active:not(.dropdown-active):hover {
  background: #247a6d;
  box-shadow: 0 0 15px rgba(36, 122, 109, 0.4);
}

.app-container.light-mode .search-results {
  background: #ffffff;
  color: #1a1a2e;
}

.bottom-left, .bottom-right {
  transition: transform 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
}

.bottom-left.panel-up, .bottom-right.panel-up {
  transform: translateY(-200px); /* Move up when panel shows */
}

.app-container.light-mode .search-container input {
  background: rgba(255, 255, 255, 0.8);
  color: #1a1a2e;
  border: 1px solid #ff69b4;
}

.app-container.light-mode .history-modal,
.app-container.light-mode .site-info-panel {
  background: #ffffff;
  color: #1a1a2e;
  box-shadow: 0 0 30px rgba(0,0,0,0.1);
}

.graph-container {
  width: 100%;
  height: 100%;
  transition: transform 0.5s ease;
}

.graph-container.shifted {
  transform: translateX(-15%);
}

.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: #0a0a0f;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.loader {
  border: 5px solid #1a1a2e;
  border-top: 5px solid #ff69b4;
  border-radius: 50%;
  width: 50px;
  height: 50px;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.ui-layer {
  position: absolute;
  z-index: 100;
}

.top-left { top: 20px; left: 20px; }
.top-right { top: 20px; right: 20px; display: flex; align-items: flex-start; gap: 10px; }
.bottom-left { bottom: 20px; left: 20px; }
.bottom-right { bottom: 20px; right: 20px; }

.header-controls {
  display: flex;
  gap: 15px;
  align-items: center;
  position: relative;
}

.theme-toggle {
  width: 40px !important;
  height: 40px !important;
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  border-radius: 50% !important;
  padding: 0 !important; /* Force remove padding from pink-btn */
  border: 1px solid #ff69b4;
  background: rgba(255, 255, 255, 0.1);
  color: #ff69b4;
  cursor: pointer;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.theme-toggle svg {
  width: 20px !important;
  height: 20px !important;
  min-width: 20px !important;
  min-height: 20px !important;
  display: block;
}

.theme-toggle:hover {
  background: rgba(255, 105, 180, 0.3);
}

.user-status {
  padding: 0 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  position: relative;
  height: 40px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: all 0.3s ease;
}

.user-status.dropdown-active {
  cursor: default;
}

.user-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: #1a1a2e;
  border: 1px solid #ff69b4;
  border-radius: 12px;
  width: 220px;
  overflow: hidden;
  z-index: 1000;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  padding: 10px;
  color: #fff;
}

.user-role-badge {
  text-align: center;
  padding: 4px;
  border-radius: 4px;
  margin-bottom: 10px;
  font-weight: bold;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: normal;
}

.user-role-badge.admin {
  background: linear-gradient(45deg, #ff69b4, #ff1493);
  color: white;
}

.user-role-badge.visitor, .user-role-badge.user {
  background: rgba(80, 227, 194, 0.2);
  color: #50e3c2;
}

.quota-info {
  display: flex;
  justify-content: space-between;
  text-align: center;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.quota-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  align-items: center;
}

.quota-item span:first-child {
  font-size: 11px;
  color: #888;
}

.quota-num {
  font-size: 16px;
  font-weight: bold;
  color: #ff69b4;
  line-height: 1;
}

.logout-btn {
  width: 100%;
  padding: 8px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  font-size: 13px;
}

.logout-btn:hover {
  background: rgba(255, 105, 180, 0.2);
  color: #ff69b4;
}

/* Transitions */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.left-controls {
  display: flex;
  gap: 15px; /* Added spacing between buttons */
}

.pink-btn {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  background: rgba(255, 105, 180, 0.2);
  color: #ff69b4;
  border: 1px solid #ff69b4;
  transition: all 0.3s ease;
}

.pink-btn:hover {
  background: rgba(255, 105, 180, 0.3);
  box-shadow: 0 0 10px rgba(255, 105, 180, 0.5);
}

.grey-btn {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  background: rgba(240, 240, 240, 0.8);
  color: #333;
  border: 1px solid #ccc;
  transition: all 0.3s ease;
}

.grey-btn:hover {
  background: #ffffff;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
}

.user-status {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  position: relative;
  transition: all 0.3s ease;
}

.login-guest:not(.dropdown-active):hover {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
  box-shadow: 0 0 15px rgba(255, 255, 255, 0.2);
}

.login-active:not(.dropdown-active):hover {
  background: rgba(80, 227, 194, 0.3);
  box-shadow: 0 0 15px rgba(80, 227, 194, 0.3);
}

.login-guest {
  background: rgba(255, 255, 255, 0.15);
  color: #ccc;
  transition: all 0.3s ease;
}

.login-active {
  background: rgba(80, 227, 194, 0.2);
  color: #50e3c2;
  border: 1px solid #50e3c2;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 120px;
}

.quota-info {
  padding: 10px;
  font-size: 12px;
  color: #888;
  border-bottom: 1px solid rgba(255, 105, 180, 0.1);
}

.user-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  background: #1a1a2e;
  border: 1px solid #ff69b4;
  border-radius: 8px;
  margin-top: 10px;
  width: 200px;
  overflow: hidden;
  z-index: 1000;
}

/* User Status hover removed in favor of click logic */

.login-action-btn {
  background: #ff69b4;
  color: white !important;
  text-align: center !important;
  border-radius: 4px;
  width: 100% !important;
  box-sizing: border-box;
  margin: 0 !important; /* Removed margin top to avoid centering shift */
  font-weight: bold;
  border: none;
  padding: 10px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: normal; /* Better for fonts than 1 in many cases */
  transform: translateY(-1px); /* Subtle upward bias to offset font baseline */
  white-space: normal; /* Allow text wrap if box is too small */
}

.login-action-btn:hover {
  background: #ff1493;
  box-shadow: 0 0 15px rgba(255, 105, 180, 0.4);
}

.app-container.light-mode .login-action-btn {
  background: #db3a8d; /* Deeper pink for light mode */
}

.app-container.light-mode .login-action-btn:hover {
  background: #b82d75;
  box-shadow: 0 0 10px rgba(219, 58, 141, 0.3);
}

.user-dropdown button {
  width: 100%;
  padding: 10px;
  border: none;
  background: none;
  color: #fff;
  text-align: left;
  cursor: pointer;
}

.user-dropdown button:hover {
  background: rgba(255, 105, 180, 0.2);
}

.search-container {
  position: relative;
  width: 300px;
}

.active-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 5px;
}

.filter-tag {
  background: #ff69b4;
  color: #fff;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.filter-tag i {
  cursor: pointer;
  font-style: normal;
}

.search-container input {
  width: 100%;
  background: rgba(26, 26, 46, 0.8);
  border: 1px solid #ff69b4;
  color: #fff;
  padding: 10px 15px;
  border-radius: 25px;
  outline: none;
}

.search-results {
  position: absolute;
  bottom: 100%;
  left: 0;
  width: 100%;
  background: #1a1a2e;
  border: 1px solid #ff69b4;
  border-radius: 12px;
  margin-bottom: 10px;
  max-height: 300px;
  overflow-y: auto;
}

.search-item {
  padding: 10px 15px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-item:hover {
  background: rgba(255, 105, 180, 0.2);
}

.res-type {
  font-size: 10px;
  background: #ff69b4;
  padding: 2px 5px;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 18px;
}

input,
textarea {
  scrollbar-width: none !important;
  -ms-overflow-style: none !important;
}

input::-webkit-scrollbar,
textarea::-webkit-scrollbar {
  display: none !important;
}

.input-group {
  margin-bottom: 15px;
}

.input-group label {
  display: block;
  color: #888;
  font-size: 14px;
  margin-bottom: 5px;
}

.input-group input,
.input-group textarea {
  width: 100%;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 105, 180, 0.3);
  color: #fff;
  padding: 8px 12px;
  border-radius: 4px;
  font-family: inherit;
  resize: vertical;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.input-group input::-webkit-scrollbar,
.input-group textarea::-webkit-scrollbar {
  display: none; /* Chrome, Safari and Opera */
}

/* Pair Input Stylings */
.pair-input {
  display: flex;
  gap: 10px;
}

.pair-input input {
  flex: 1;
}

.pair-input-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.remove-btn {
  background: none;
  border: none;
  color: #ff4757;
  font-size: 20px;
  cursor: pointer;
  padding: 0 5px;
}

.add-btn {
  background: rgba(255, 105, 180, 0.1);
  border: 1px dashed #ff69b4;
  color: #ff69b4;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  width: 100%;
  margin-top: 5px;
  transition: all 0.2s;
}

.add-btn:hover {
  background: rgba(255, 105, 180, 0.2);
}

.info-link {
  color: #ff69b4;
  text-decoration: none;
  transition: all 0.2s;
}

.info-link:hover {
  text-decoration: underline;
  opacity: 0.8;
}

.related-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.related-item {
  display: block;
}

.image-container.editable {
  cursor: pointer;
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.05);
}

.hover-mask {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  opacity: 0;
  transition: opacity 0.3s;
  color: #fff;
  font-weight: bold;
}

.image-container.editable:hover .hover-mask {
  opacity: 1;
}

.image-container.editable:hover img {
  filter: grayscale(0.5);
}

.upload-placeholder {
  width: 100%;
  height: 200px;
  background: rgba(26, 26, 46, 0.5);
  border: 2px dashed #ff69b4;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #ff69b4;
  border-radius: 8px;
}

.upload-placeholder small {
  font-size: 10px;
  opacity: 0.7;
}

/* Crop Modal */
.crop-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.8);
  z-index: 2000;
  display: flex;
  justify-content: center;
  align-items: center;
}

.crop-modal {
  background: #1a1a2e;
  border: 1px solid #ff69b4;
  border-radius: 20px;
  padding: 24px;
  width: 360px;
  text-align: center;
}

.canvas-container {
  width: 300px;
  height: 300px;
  margin: 20px auto;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  cursor: move;
  touch-action: none;
}

.crop-tip {
  font-size: 12px;
  color: #888;
  margin: 5px 0;
}

.crop-actions {
  display: flex;
  justify-content: space-around;
  margin-top: 20px;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.btn.confirm { background: #50e3c2; }
.btn.cancel { background: #888; }

.side-panel {
  position: absolute;
  right: 0;
  top: 0;
  width: 400px;
  height: 100%;
  background: rgba(10, 10, 15, 0.85);
  backdrop-filter: blur(10px);
  border-left: 1px solid rgba(255, 105, 180, 0.3);
  box-shadow: -10px 0 20px rgba(0,0,0,0.5);
  z-index: 200;
  padding: 0; /* Removed fixed padding to let scroll container fill the panel */
  display: flex;
  flex-direction: column;
  overflow: hidden; 
}

.close-btn {
  position: absolute;
  top: 10px;
  right: 15px;
  background: none;
  border: none;
  color: #fff;
  font-size: 24px;
  cursor: pointer;
}

.node-update-history-btn-round {
  position: absolute;
  top: 15px;
  left: 15px;
  width: 35px;
  height: 35px;
  background: rgba(255, 105, 180, 0.2);
  color: #ff69b4;
  border: 1px solid #ff69b4;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  box-shadow: 0 2px 10px rgba(0,0,0,0.3);
  transition: all 0.3s;
  z-index: 201;
}

.node-update-history-btn-round:hover {
  background: rgba(255, 105, 180, 0.3);
  transform: scale(1.1);
}

.node-apply-famous-btn-round {
  position: absolute;
  top: 15px;
  left: 60px;
  width: 35px;
  height: 35px;
  background: rgba(255, 105, 180, 0.2);
  color: #ff69b4;
  border: 1px solid #ff69b4;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  box-shadow: 0 2px 10px rgba(0,0,0,0.3);
  transition: all 0.3s;
  z-index: 201;
}

.node-apply-famous-btn-round:hover:not(.disabled) {
  background: rgba(255, 105, 180, 0.3);
  transform: scale(1.1);
}

.node-apply-famous-btn-round.disabled {
  background: rgba(128, 128, 128, 0.2);
  color: #888;
  border-color: #888;
  cursor: not-allowed;
}

.famous-toggle-btn {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  background: rgba(135, 206, 235, 0.2);
  color: #87CEEB;
  border: 1px solid #87CEEB;
  transition: all 0.3s ease;
}

.famous-toggle-btn:hover {
  background: rgba(135, 206, 235, 0.3);
  box-shadow: 0 0 10px rgba(135, 206, 235, 0.5);
}

.famous-toggle-btn.active {
  background: rgba(135, 206, 235, 0.8);
  color: #fff;
}

.famous-pending-btn {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  background: rgba(135, 206, 235, 0.2);
  color: #87CEEB;
  border: 1px solid #87CEEB;
  transition: all 0.3s ease;
}

.famous-pending-btn:hover {
  background: rgba(135, 206, 235, 0.3);
  box-shadow: 0 0 10px rgba(135, 206, 235, 0.5);
}

.panel-inner-close-btn {
  position: absolute;
  top: 15px;
  right: 15px;
  width: 35px;
  height: 35px;
  background: rgba(255, 105, 180, 0.2);
  color: #ff69b4;
  border: 1px solid #ff69b4;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.3s;
  z-index: 202;
}

.panel-inner-close-btn:hover {
  background: rgba(255, 105, 180, 0.3);
  transform: rotate(90deg);
}

.panel-content {
  position: relative;
  overflow-y: auto;
  flex: 1;
  padding: 60px 20px 40px 20px; 
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
  cursor: grab;
}

.panel-content:active {
  cursor: grabbing;
}

.panel-content::-webkit-scrollbar {
  display: none; /* Chrome, Safari and Opera */
}

/* Modal Overlay */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  z-index: 1500;
  display: flex;
  justify-content: center;
  align-items: center;
}

.image-container {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  margin-top: 15px; /* Added spacing to avoid overlap */
  margin-bottom: 20px;
  border: 2px solid #ff69b4;
}

.image-container img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.node-name {
  font-size: 24px;
  color: #ff69b4;
  margin-bottom: 20px;
  text-align: center;
}

.info-item {
  margin-bottom: 20px;
}

.info-item label {
  display: block;
  color: #888;
  font-size: 14px;
  margin-bottom: 5px;
}

.info-intro {
  display: block;
  line-height: 1.6;
  white-space: pre-wrap;
  background: rgba(255, 255, 255, 0.05);
  padding: 10px;
  border-radius: 8px;
  border-left: 3px solid #ff69b4;
  font-size: 14px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  background: rgba(255, 105, 180, 0.2);
  border: 1px solid #ff69b4;
  color: #ff69b4;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
}

.action-buttons {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  padding-bottom: 20px;
}

.btn {
  flex: 1;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  border: none;
  color: #fff;
  font-size: 14px;
  transition: opacity 0.3s;
}

.btn:hover {
  opacity: 0.8;
}

.btn.edit { background: #4a90e2; }
.btn.add { background: #50e3c2; }
.btn.delete { background: #d0021b; }
.btn.save-pos { background: #f39c12; }

.btn:disabled {
  background: #555 !important;
  cursor: not-allowed;
  opacity: 0.5;
}

.node-info-footer {
  padding-top: 15px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: flex-end;
}

.history-icon-btn {
  background: none;
  border: 1px solid rgba(255, 105, 180, 0.5);
  color: #ff69b4;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.history-icon-btn:hover {
  background: rgba(255, 105, 180, 0.1);
  box-shadow: 0 0 10px rgba(255, 105, 180, 0.3);
}

/* History Modal */
.history-loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 15px;
  color: #ff69b4;
}

.mini-loader {
  border: 3px solid rgba(255, 105, 180, 0.1);
  border-top: 3px solid #ff69b4;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  animation: spin 0.8s linear infinite;
}

.history-modal {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 90%;
  max-width: 650px;
  max-height: 70vh;
  background: #1a1a2e;
  border: 1px solid rgba(255, 105, 180, 0.4);
  border-radius: 16px;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  box-shadow: 0 0 60px rgba(0,0,0,0.6);
  padding: 10px;
  color: #ffffff; /* Ensure text is white in dark mode */
}

.app-container.light-mode .history-modal {
  background: #ffffff;
  color: #1a1a2e; /* Black text for light mode */
}

.modal-header {
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  text-align: center;
}

.modal-header h3 {
  margin: 0;
  color: #ff69b4;
  font-size: 1.3rem;
}

.history-list {
  padding: 10px 20px;
  overflow-y: auto;
  flex: 1;
}

.history-item {
  padding: 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 0.95rem;
  line-height: 1.6;
}

.history-time {
  color: #888;
  margin-right: 12px;
}

.history-user {
  font-weight: bold;
}

.history-user.admin {
  color: #00ffff; /* Cyan for Admin */
}

.history-user.user {
  color: #ff69b4; /* Pink for regular users */
}

.history-action.add { color: #50fa7b; }
.history-action.edit { color: #f1fa8c; }
.history-action.delete { color: #ff5555; }

.history-node-link {
  color: #ff69b4;
  text-decoration: underline;
  cursor: pointer;
}

/* Site Info Panel (Slide up) */
.site-info-panel {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #1a1a2e;
  border-top: 1px solid rgba(255, 105, 180, 0.5);
  z-index: 1000;
  padding: 40px;
  color: #fff;
  box-shadow: 0 -10px 40px rgba(0,0,0,0.6);
  height: 200px; /* Fixed height for consistent sliding */
  box-sizing: border-box;
}

.site-info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr); /* 3 column layout */
  gap: 40px;
  max-width: 1200px;
  margin: 0 auto;
}

.info-section h4 {
  color: #ff69b4;
  margin-bottom: 20px;
  font-size: 1.1rem;
  border-left: 3px solid #ff69b4;
  padding-left: 10px;
}

.info-section p, .info-section a {
  color: #bbb;
  font-size: 0.95rem;
  text-decoration: none;
  display: block;
  margin-bottom: 10px;
}

.info-section a:hover {
  color: #ff1493;
}

.legal-info {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  text-align: center;
  font-size: 0.8rem;
  color: #666;
}

/* Transition */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.5s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}

.slide-up-enter-active, .slide-up-leave-active {
  transition: transform 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
}
.slide-up-enter-from, .slide-up-leave-to {
  transform: translateY(100%);
}

/* Mobile Responsive Adjustments */
@media screen and (max-width: 768px) {
  .top-left {
    top: 10px;
    left: 10px;
  }
  
  .left-controls {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .left-controls-row2 {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .top-right {
    top: 10px;
    right: 10px;
  }
  
  .user-status {
    padding: 6px 12px;
    max-width: 140px;
    font-size: 11px;
    white-space: nowrap;
    overflow: visible; /* Allow dropdown to show */
    text-overflow: ellipsis;
  }

  .bottom-left {
    bottom: 20px;
    left: 10px;
    width: auto;
    right: 120px; /* Side-by-side with site info button */
  }
  
  .search-container {
    width: 100%;
  }

  .bottom-right {
    bottom: 20px;
    right: 10px;
  }

  .side-panel {
    width: 100%; /* Full screen width on mobile */
    max-width: 100%;
  }
  
  .graph-container.shifted {
    transform: none; /* Don't shift graph on mobile to keep space */
    opacity: 0.3; /* Dim it instead */
  }

  .site-info-panel {
    padding: 20px;
    height: auto;
    min-height: 250px;
    max-height: 400px;
    overflow-y: auto;
  }

  .site-info-grid {
    grid-template-columns: 1fr;
    gap: 15px;
  }
  
  .bottom-left.panel-up, .bottom-right.panel-up {
    transform: translateY(-280px);
  }
}
</style>
