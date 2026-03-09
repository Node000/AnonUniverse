<script setup>
import { onMounted, onUnmounted, ref, reactive, nextTick, computed, watch } from 'vue'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import axios from 'axios'

// Components
import Toolbar from './components/Toolbar.vue'
import UserAccount from './components/UserAccount.vue'
import SearchBox from './components/SearchBox.vue'
import HistoryModal from './components/HistoryModal.vue'

// Composables
import { useUser } from './composables/useUser'
import { useMouseEffects } from './composables/useMouseEffects'

const apiBase = import.meta.env.DEV ? 'http://localhost:8000' : ''
const vizContainer = ref(null)
const fileInput = ref(null)

// Use Composables
const { currentUser, fetchUserInfo } = useUser(apiBase)
const { ripples, handleMouseMove, handleClickRipple } = useMouseEffects()

const loading = ref(true)
const selectedNode = ref(null)
const isPanelOpen = ref(false)
const isDropdownOpen = ref(false)
let isDraggingNode = false // Track dragging state for physics optimization

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
const showNewNodes = ref(false)
const pendingApplications = ref([])
const mailboxMessages = ref([])
const showMailboxModal = ref(false)
const newMessageContent = ref('')
const showNewMessageModal = ref(false)
const showFeedbackModal = ref(false)
const processingMessageId = ref(null)
const processingAction = ref('')
const feedbackContent = ref('')
const showApplyFamousModal = ref(false)
const showPendingApplicationsModal = ref(false)
const showGuideModal = ref(false)
const showNotificationModal = ref(false)
const notifiedMails = ref([])

const triggerNotificationCheck = async () => {
  if (currentUser.logged_in && currentUser.notifications && currentUser.notifications.length > 0) {
    try {
      const resp = await axios.get(`${apiBase}/api/mailbox`, {
        params: { user_id: currentUser.user_id }
      })
      const allMails = resp.data
      notifiedMails.value = allMails.filter(m => currentUser.notifications.includes(m.id))
      
      if (notifiedMails.value.length > 0) {
        showNotificationModal.value = true
        // 告知后端清空通知列表
        const formData = new FormData()
        formData.append('user_id', currentUser.user_id)
        await axios.post(`${apiBase}/api/user/clear_notifications`, formData)
      }
    } catch (e) {
      console.error("Failed to check notifications", e)
    }
  }
}

const canSendMessage = computed(() => {
  if (!currentUser.logged_in) return false
  if (currentUser.role === 'admin') return true
  return currentUser.quota && currentUser.quota.messages < 3
})

// Site info state
const showSiteInfo = ref(false)

const isHistoryLoading = ref(false)

// Connection Edit Mode state
const isConnectionEditMode = ref(false)

const editForm = reactive({
  id: null,
  name: '',
  source: { name: '', link: '', type: '其他' },
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
  if (!selectedNode.value || !currentUser.logged_in || currentUser.role === 'banned') return false
  
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
    if (isAdding.value && currentUser.quota.adds >= 10) return '今日新增配额已用完'
    if (!isAdding.value && currentUser.quota.edits >= 10) return '今日修改配额已用完'
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

    const imageUrl = node.image ? (node.image.startsWith('http') ? node.image : `${apiBase}${node.image}`) : `${apiBase}/images/default.webp`;
    
    // Calculate size based on connections
    const nodeSize = 34 + Math.min(36, (connectionCounts[node.id] || 0) * 4);

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
      brokenImage: `${apiBase}/images/default.webp`,
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
    // Search Name
    if (node.name.toLowerCase().includes(q)) {
      results.push({ type: 'node', id: node.id, name: node.name })
    }
    // Search Source Name (Works/作品)
    if (node.source && node.source.name && node.source.name.toLowerCase().includes(q)) {
      if (!results.some(r => r.type === 'source' && r.name === node.source.name)) {
        results.push({ type: 'source', name: node.source.name })
      }
    }
    // Search Tags
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
  } else if (res.type === 'tag' || res.type === 'source') {
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
    const matchesAll = activeFilters.value.every(f => {
      // Return true if node belongs to this Work (source.name) OR has this Tag (tags)
      const matchesSource = node.source && node.source.name === f
      const matchesTag = node.tags.includes(f)
      return matchesSource || matchesTag
    })
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
    
    // 如果之前开启了连线编辑，在切换节点时关闭或切换目标
    isConnectionEditMode.value = false
    
    // Highlight focused node by increasing size and border width
    nodesData.update({ id: nodeId, size: node.originalSize * 1.5, borderWidth: 6 })
    
    selectedNode.value = node
    isPanelOpen.value = true
    if (network) {
      // 优化：侧边栏宽度为 400px，因此中心点应向左偏移 200px 来抵消侧边栏占用的空间。
      // 注意：offset 是视口坐标。将视图中心相对于视口中心向右移动 200px，会让节点看起来位于除去侧边栏后的中心。
      network.focus(nodeId, {
        scale: 1, 
        offset: { x: 0, y: 0 }, 
        animation: { 
          duration: 530, 
          easingFunction: 'easeInOutCubic' 
        }
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
    catch(e) { rawSource = { name: rawSource, link: '', type: '其他' }; }
  }
  
  // Ensure source has type
  if (!rawSource.type) rawSource.type = '其他';
  
  // Clean up related if it's a string or has invalid items
  let rawRelated = selectedNode.value.related || []
  if (typeof rawRelated === 'string') {
    try { rawRelated = JSON.parse(rawRelated); }
    catch(e) { rawRelated = []; }
  }
  if (!Array.isArray(rawRelated)) rawRelated = [];

  // Ensure all related items have type
  rawRelated = rawRelated.map(item => ({
    name: item.name || '',
    link: item.link || '',
    type: item.type || '其他'
  }));

  Object.assign(editForm, {
    id: selectedNode.value.id,
    name: selectedNode.value.name,
    source: JSON.parse(JSON.stringify(rawSource)),
    related: JSON.parse(JSON.stringify(rawRelated)),
    tags: Array.isArray(selectedNode.value.tags) ? selectedNode.value.tags.join(',') : '',
    extension: selectedNode.value.extension || [],
    introduction: selectedNode.value.introduction || '',
    imageFile: null,
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
    source: { name: '', link: '', type: '其他' },
    related: [],
    tags: '',
    introduction: '',
    imageFile: null,
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
    editForm.imageFile = new File([blob], "avatar.webp", { type: "image/webp" })
    editForm.imagePreview = URL.createObjectURL(blob)
    showCropModal.value = false
  }, 'image/webp')
}

const cancelCrop = () => {
  showCropModal.value = false
}

const addRelated = () => {
  editForm.related.push({ name: '', link: '', type: '其他' })
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
      
      // 新增节点后激活物理引擎一段时间以自动布局
      if (network) {
        network.setOptions({ physics: { enabled: true } });
        network.startSimulation();
        setTimeout(() => {
          if (network) network.setOptions({ physics: { enabled: false } });
        }, 3000);
      }
    } else {
      const resp = await axios.put(`${apiBase}/api/nodes/${editForm.id}`, formData)
      resultNode = resp.data;
      
      // Get current position to prevent jumping back to initial coordinates
      const currentPos = network ? network.getPositions([resultNode.id])[resultNode.id] : null;
      
      // Update local data without full refresh
      const finalImageUrl = resultNode.image 
        ? (resultNode.image.startsWith('http') ? resultNode.image : `${apiBase}${resultNode.image}`) 
        : `${apiBase}/images/default.webp`;
        
      nodesData.update({
        ...resultNode,
        id: resultNode.id,
        label: resultNode.name,
        image: finalImageUrl,
        x: currentPos ? currentPos.x : resultNode.x,
        y: currentPos ? currentPos.y : resultNode.y
      })
      
      // Update selectedNode which updates the side panel
      if (selectedNode.value && selectedNode.value.id === resultNode.id) {
         Object.assign(selectedNode.value, resultNode);
      }

      // Re-apply filters to ensure new tags/content are searchable
      applyFilters()
      
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
      
      // 删除节点后激活物理引擎一段时间以重新排列
      if (network) {
        network.setOptions({ physics: { enabled: true } });
        network.startSimulation();
        setTimeout(() => {
          if (network) network.setOptions({ physics: { enabled: false } });
        }, 3000);
      }
      
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
  if (e) e.stopPropagation()
  isDropdownOpen.value = !isDropdownOpen.value
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

const fetchMailbox = async () => {
  if (!currentUser.logged_in) return
  try {
    const response = await axios.get(`${apiBase}/api/mailbox`, {
      params: { user_id: currentUser.user_id }
    })
    mailboxMessages.value = response.data
  } catch (error) {
    console.error('Failed to fetch mailbox:', error)
  }
}

const openMailbox = async () => {
  await fetchMailbox()
  showMailboxModal.value = true
}

const submitMailboxMessage = async () => {
  if (!newMessageContent.value.trim()) {
    alert('请输入信件内容')
    return
  }
  if (newMessageContent.value.length > 200) {
    alert('内容不能超过200字')
    return
  }
  
  const formData = new FormData()
  formData.append('content', newMessageContent.value)
  formData.append('user_id', currentUser.user_id)
  formData.append('nickname', currentUser.nickname)
  
  try {
    await axios.post(`${apiBase}/api/mailbox`, formData)
    newMessageContent.value = ''
    showNewMessageModal.value = false
    await fetchMailbox()
    await fetchUserInfo(currentUser.user_id, currentUser.nickname)
  } catch (error) {
    alert(error.response?.data?.detail || '发送失败')
  }
}

const handleProcessMessage = (msgId, action) => {
  processingMessageId.value = msgId
  processingAction.value = action
  feedbackContent.value = ''
  showFeedbackModal.value = true
}

const submitFeedback = async () => {
  if (feedbackContent.value.length > 30) {
    alert('反馈不能超过30字')
    return
  }
  
  const formData = new FormData()
  formData.append('action', processingAction.value)
  formData.append('feedback', feedbackContent.value)
  formData.append('user_id', currentUser.user_id)
  formData.append('nickname', currentUser.nickname)
  
  try {
    await axios.post(`${apiBase}/api/mailbox/${processingMessageId.value}/process`, formData)
    showFeedbackModal.value = false
    await fetchMailbox()
  } catch (error) {
    console.error('Failed to process message:', error)
    alert('提交失败')
  }
}

const unprocessedMailCount = computed(() => {
  return mailboxMessages.value.filter(m => m.status === 'unprocessed').length
})

const shouldShowExpand = (msg) => {
  // Simple heuristic: if content is long enough or has multiple newlines
  if (!msg.content) return false;
  const lines = msg.content.split('\n').length;
  // If more than 2 lines, show expand
  if (lines > 2) return true;
  // If text is very long (approx more than 2 lines of container width)
  if (msg.content.length > 60) return true;
  return false;
}

const openPendingApplications = () => {
  fetchPendingApplications()
  showPendingApplicationsModal.value = true
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

const toggleConnectionEditMode = () => {
  isConnectionEditMode.value = !isConnectionEditMode.value
}

const handleNodeConnection = async (targetId) => {
  if (!selectedNode.value || currentUser.role !== 'admin') return
  
  // 检查是添加还是删除
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
    
    // 更新本地数据
    nodesData.update({ id: selectedNode.value.id, extension: newExtension })
    selectedNode.value.extension = newExtension
    
    // 更新 Edge
    const edgeId = `${selectedNode.value.id}-${targetId}`
    const reverseEdgeId = `${targetId}-${selectedNode.value.id}`
    const existingEdge = edgesData.get(edgeId) || edgesData.get(reverseEdgeId)
    
    if (isRemoving) {
      if (existingEdge) {
        edgesData.remove(existingEdge.id)
      }
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
    
    // 连线变动后激活物理引擎一段时间以重新排布
    if (network) {
      network.setOptions({ physics: { enabled: true } });
      network.startSimulation();
      setTimeout(() => {
        if (network) network.setOptions({ physics: { enabled: false } });
      }, 3000);
    }
    
  } catch (error) {
    console.error(error)
    alert(error.response?.data?.detail || '修改连线失败')
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

const closeGuide = () => {
  showGuideModal.value = false
  // 仅在本地存储标记已读，不再设置过期时间
  localStorage.setItem('guide_seen', 'true')
}

const openGuide = () => {
  showGuideModal.value = true
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
      
      // 检查是否有新的信件反馈通知 (等加载结束后)
      triggerNotificationCheck()
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
  let newNodesRotationAngle = 0;
  let lastFrameTime = 0;
  const FPS_LIMIT = 30;
  const FRAME_INTERVAL = 1000 / FPS_LIMIT;
  
  let isZoomingOrPanning = false; // Flag to skip redraw during interaction

  const animateFamousNodes = (timestamp) => {
    // Basic throttling
    if (!lastFrameTime) lastFrameTime = timestamp;
    const elapsed = timestamp - lastFrameTime;

    if (elapsed > FRAME_INTERVAL) {
      if ((showFamous.value || showNewNodes.value) && network) {
        const timeScale = elapsed / FRAME_INTERVAL;
        // Increment angle based on time to be smooth regardless of frame rate
        famousRotationAngle += 0.03 * timeScale;
        newNodesRotationAngle += 0.036 * timeScale; // 1.2x speed (0.03 * 1.2 = 0.036)
        
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

  // Watch for toggle to force a redraw when we turn it off
  watch([showFamous, showNewNodes], () => {
    if (network) {
      network.redraw();
    }
  });

  watch(isPanelOpen, (newVal) => {
    if (!newVal) {
      isConnectionEditMode.value = false;
    }
  });

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
    if (!showFamous.value && !showNewNodes.value) return;
    const nodes = nodesData.get();
    nodes.forEach(node => {
      const pos = network.getPositions([node.id])[node.id];
      if (!pos) return;

      // Draw Famous Circle (Skyblue, Original Speed)
      if (showFamous.value && node.is_famous) {
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

      // Draw New Node Circle (Orange, 1.2x Speed)
      if (showNewNodes.value && node.new) {
        ctx.save();
        ctx.translate(pos.x, pos.y);
        ctx.rotate(newNodesRotationAngle);
        ctx.beginPath();
        // Slightly different radius if both circles are on (nested)
        const radius = (node.size || 40) + (node.is_famous && showFamous.value ? 25 : 15);
        const circumference = 2 * Math.PI * radius;
        const dashLen = circumference / 12;
        ctx.arc(0, 0, radius, 0, 2 * Math.PI);
        ctx.strokeStyle = '#FFA500'; // Orange
        ctx.lineWidth = 6;
        ctx.setLineDash([dashLen, dashLen]);
        ctx.stroke();
        ctx.restore();
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
      
      if (isConnectionEditMode.value) {
        if (nodeId !== selectedNode.value.id) {
          handleNodeConnection(nodeId)
        }
        return
      }

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
  await fetchMailbox()

  // 漫游指南：检查是否首次进入
  if (!localStorage.getItem('guide_seen')) {
    setTimeout(() => {
      showGuideModal.value = true
    }, 1500)
  }

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
    <Toolbar 
      v-model:showFamous="showFamous"
      v-model:showNewNodes="showNewNodes"
      :isDarkMode="isDarkMode"
      :currentUser="currentUser"
      :unprocessedMailCount="unprocessedMailCount"
      @resetView="resetView"
      @toggleHistory="toggleHistory()"
      @toggleDarkMode="toggleDarkMode"
      @openGuide="openGuide"
      @openMailbox="openMailbox"
    />

    <UserAccount 
      :currentUser="currentUser"
      :isDropdownOpen="isDropdownOpen"
      @toggleDropdown="toggleDropdown"
      @loginWithBangumi="loginWithBangumi"
      @logout="logout"
    />

    <div class="ui-layer bottom-left" :class="{ 'panel-up': showSiteInfo }">
      <SearchBox 
        v-model:searchQuery="searchQuery"
        :searchResults="searchResults"
        :activeFilters="activeFilters"
        @handleSearch="handleSearch"
        @selectSearchResult="selectSearchResult"
        @removeFilter="removeFilter"
      />
    </div>

    <div class="ui-layer bottom-right" :class="{ 'panel-up': showSiteInfo }">
      <button class="info-btn pink-btn" @click.stop="toggleSiteInfo">网站信息</button>
    </div>

    <!-- Modals -->
    <HistoryModal 
      :showHistory="showHistory"
      :historyData="historyData"
      :historyType="historyType"
      :isHistoryLoading="isHistoryLoading"
      @close="showHistory = false"
    />
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
                :src="selectedNode.image ? (selectedNode.image.startsWith('http') ? selectedNode.image : `${apiBase}${selectedNode.image}`) : `${apiBase}/images/default.webp`" 
                :alt="selectedNode.name"
                :onerror="`this.src='${apiBase}/images/default.webp'`"
              >
            </div>
            
            <h2 class="node-name">
              <span v-if="selectedNode.is_famous" title="已认证知名二创" style="color: #ff69b4; margin-right: 5px; cursor: help;">★</span>
              {{ selectedNode.name }}
            </h2>
            
            <div class="info-item">
              <label>出处：</label>
              <div style="display: inline-flex; align-items: center; gap: 8px;">
                <a v-if="selectedNode.source.link" :href="selectedNode.source.link" target="_blank" class="info-link">{{ selectedNode.source.name }}</a>
                <span v-else>{{ selectedNode.source.name }}</span>
                <span v-if="selectedNode.source.type" class="res-type" style="font-size: 10px; padding: 1px 4px; margin: 0;">{{ selectedNode.source.type }}</span>
              </div>
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
                <div v-for="(item, idx) in selectedNode.related" :key="idx" class="related-item" style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                  <a v-if="item.link" :href="item.link" target="_blank" class="info-link">{{ item.name }}</a>
                  <span v-else>{{ item.name }}</span>
                  <span v-if="item.type" class="res-type" style="font-size: 10px; padding: 1px 4px; margin: 0;">{{ item.type }}</span>
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
                >{{ selectedNode.is_famous ? '取消知名' : '设为知名' }}</button>
                <button 
                  class="btn connection-toggle" 
                  @click="toggleConnectionEditMode"
                  title="点击图中节点以增删连线"
                  :style="{ background: isConnectionEditMode ? '#ff6b6b' : '#9c88ff' }"
                >{{ isConnectionEditMode ? '停止连线' : '增删连线' }}</button>
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
              <div class="pair-input-row">
                <div class="pair-input">
                  <input v-model="editForm.source.name" placeholder="作品名字">
                  <input v-model="editForm.source.link" placeholder="链接 (可选)">
                  <select v-model="editForm.source.type" class="type-select">
                    <option>小说</option>
                    <option>视频</option>
                    <option>插画</option>
                    <option>漫画</option>
                    <option>游戏</option>
                    <option>其他</option>
                  </select>
                </div>
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
                  <input v-model="item.name" placeholder="名字" style="flex: 1.5; min-width: 80px;">
                  <input v-model="item.link" placeholder="链接 (可选)" style="flex: 2; min-width: 100px;">
                  <select v-model="item.type" class="type-select">
                    <option>小说</option>
                    <option>视频</option>
                    <option>插画</option>
                    <option>漫画</option>
                    <option>游戏</option>
                    <option>其他</option>
                  </select>
                </div>
                <button class="remove-btn" @click="removeRelated(index)" title="删除此项">×</button>
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

    <!-- Modals -->
    <HistoryModal 
      v-if="showHistory"
      :showHistory="showHistory"
      :historyData="historyData"
      :historyType="historyType"
      :isHistoryLoading="isHistoryLoading"
      @close="showHistory = false"
      @focusNode="(id) => { focusNode(id); showHistory = false }"
    />

    <!-- Guide Modal -->
    <Transition name="fade">
      <div v-if="showGuideModal" class="modal-overlay" @click="closeGuide">
        <div class="guide-modal" @click.stop style="background: #1a1a2e; border: 2px solid #ff69b4; border-radius: 15px; width: 450px; max-width: 90vw; padding: 30px; box-shadow: 0 0 30px rgba(255, 105, 180, 0.4);">
          <h2 style="color: #ff69b4; text-align: center; margin-bottom: 25px; font-size: 1.5rem;">千早爱音宇宙漫游指南</h2>
          <div style="color: #eee; line-height: 1.8; font-size: 0.95rem;">
            <p>1. 本站用于记录千早爱音在中文互联网的各种形象，侵权即删。</p>
            <p>2. 点击节点可以查看该形象的详细信息。</p>
            <p>3. 用户在登录后，每日可以进行10次新增、10次修改、1次删除与3次信件投递</p>
            <p>4. “知名二创”的标准是：该形象作品为剧情性二创，且B站播放量 ≥ 20w。</p>
            <p>5. 如有大范围节点调整、连线增删、知名二创申请等需求，请通过信箱联系管理员。</p>
            <p>6. 若想担任本站管理员，请联系本站站长。点击右下角“网站信息”可以显示站长的B站空间链接，私信即可。</p>
            <p>7. 欢迎各位观众与作者对本网站的内容进行更新！</p>
          </div>
          <div style="display: flex; justify-content: center; margin-top: 30px;">
            <button class="btn confirm" style="padding: 10px 40px; font-size: 1rem;" @click="closeGuide">出发！</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Site Info Bottom Panel -->
    <Transition name="slide-up">
      <div v-if="showSiteInfo" class="site-info-panel" @click.stop>
        <div class="site-info-grid">
          <div class="info-section">
            <h4>开发者&站长</h4>
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

    <!-- Mailbox Feedback Notification Modal -->
    <Transition name="fade">
      <div v-if="showNotificationModal" class="modal-overlay" @click="showNotificationModal = false">
        <div class="modal-content notification-modal" @click.stop style="background: #1a1a2e; border: 2px solid #ff69b4; border-radius: 15px; width: 450px; max-width: 90vw; padding: 25px; box-shadow: 0 0 30px rgba(255, 105, 180, 0.4);">
          <h2 style="color: #ff69b4; text-align: center; margin-bottom: 20px;">有新的信件反馈！</h2>
          <div class="notification-list" style="max-height: 450px; overflow-y: auto; padding-right: 5px; scrollbar-width: none; -ms-overflow-style: none;">
            <style>
              .notification-list::-webkit-scrollbar { display: none; }
            </style>
            <div v-for="mail in notifiedMails" :key="mail.id" class="notified-mail-item" style="border-bottom: 1px dashed rgba(255,105,180,0.3); padding: 15px 0;">
              <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span style="color: #888; font-size: 0.8rem;">{{ mail.time }}</span>
                <span :style="{ color: mail.status === 'processed' ? '#50e3c2' : '#ff4d4f', fontSize: '0.9rem', fontWeight: 'bold' }">
                  {{ mail.status === 'processed' ? '已处理' : '已拒绝' }}
                </span>
              </div>
              <div style="color: #eee; margin-bottom: 10px; font-size: 0.95rem; line-height: 1.4; background: rgba(255,255,255,0.05); padding: 8px; border-radius: 5px; white-space: pre-wrap; word-break: break-all;">
                {{ mail.content }}
              </div>
              <div style="display: flex; flex-direction: column; gap: 4px;">
                <div style="color: #ff69b4; font-size: 0.9rem; white-space: pre-wrap;">反馈：{{ mail.feedback }}</div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
                  <span style="color: #666; font-size: 0.75rem;">处理时间：{{ mail.processed_time || mail.time }}</span>
                  <span style="color: #00ffff; font-size: 0.8rem;">处理人：{{ mail.processed_by }}</span>
                </div>
              </div>
            </div>
          </div>
          <button @click="showNotificationModal = false" class="pink-btn" style="width: 100%; margin-top: 20px; padding: 10px; border-radius: 20px; font-weight: bold;">我知道了</button>
        </div>
      </div>
    </Transition>

    <!-- Mailbox Modal -->
    <div v-if="showMailboxModal" class="modal-overlay" @click="showMailboxModal = false">
      <div class="mailbox-modal" @click.stop :class="{ 'light-mode': !isDarkMode }">
        <div class="modal-header" style="position: relative;">
          <h3 style="width: 100%; text-align: center;">信箱</h3>
          <button class="close-btn" @click="showMailboxModal = false" style="position: absolute; right: 15px; top: 15px; color: #ff69b4; background: none; border: none; font-size: 24px; cursor: pointer; line-height: 1;">&times;</button>
        </div>
        <div class="mailbox-content">
          <div class="mailbox-add-btn-wrapper">
             <button 
               class="mailbox-add-btn-large" 
               @click="showNewMessageModal = true"
               :disabled="!canSendMessage"
               :title="!canSendMessage ? '今日信件配额已用完' : ''"
               :style="{ opacity: canSendMessage ? 1 : 0.5, cursor: canSendMessage ? 'pointer' : 'not-allowed' }"
             >
                <span>{{ canSendMessage ? '+ 投递新信件' : '今日投递配额已用完' }}</span>
             </button>
          </div>
          <div v-if="mailboxMessages.length === 0" class="no-messages">暂无信件</div>
          <div v-for="msg in mailboxMessages" :key="msg.id" class="mailbox-item" :class="msg.status">
            <div class="msg-main">
              <div class="msg-header">
                <span class="msg-user">{{ msg.nickname }}</span>
                <span class="msg-time">{{ msg.time }}</span>
              </div>
              <div class="msg-body">
                <div 
                  class="msg-body-inner" 
                  :class="{ 'expanded': msg.isExpanded }"
                  :id="'msg-content-' + msg.id"
                >
                  {{ msg.content }}
                </div>
                <div 
                  v-if="shouldShowExpand(msg)" 
                  class="expand-toggle" 
                  @click.stop="msg.isExpanded = !msg.isExpanded"
                >
                  {{ msg.isExpanded ? '收起' : '展开全文' }}
                </div>
              </div>
            </div>
            <div class="msg-status">
              <template v-if="msg.status === 'unprocessed'">
                <div v-if="currentUser.role === 'admin'" style="display: flex; gap: 5px;">
                  <button class="process-btn" @click="handleProcessMessage(msg.id, 'process')">处理</button>
                  <button class="reject-btn" @click="handleProcessMessage(msg.id, 'reject')" style="background: #ff4d4f; border: none; color: white; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px;">拒绝</button>
                </div>
                <span v-else class="status-text unprocessed">未处理</span>
              </template>
              <template v-else>
                <div class="status-info">
                  <span>{{ msg.status === 'processed' ? '已处理' : '拒绝' }}</span>
                  <span class="feedback-info" style="color: #ff69b4;">
                    反馈：{{ msg.feedback || '无' }}
                  </span>
                  <span>处理人：{{ msg.processed_by }}</span>
                  <span>时间：{{ msg.processed_time }}</span>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- New Message Modal -->
    <div v-if="showNewMessageModal" class="modal-overlay" @click="showNewMessageModal = false">
      <div class="new-message-modal" @click.stop :class="{ 'light-mode': !isDarkMode }">
        <div class="modal-header" style="position: relative;">
          <h3 style="width: 100%; text-align: center;">投递信件</h3>
          <button class="close-btn" @click="showNewMessageModal = false" style="position: absolute; right: 10px; top: 10px; background: none; border: none; color: inherit; font-size: 20px; cursor: pointer;">&times;</button>
        </div>
        <div class="modal-body">
          <textarea 
            v-model="newMessageContent" 
            placeholder="请输入信件内容（最多200字）" 
            maxlength="200"
          ></textarea>
          <div class="char-count">{{ newMessageContent.length }}/200</div>
        </div>
        <div class="modal-footer" style="display: flex; justify-content: center; gap: 30px; padding: 15px 30px;">
          <button class="btn confirm" @click="submitMailboxMessage">确认</button>
          <button class="btn cancel" @click="showNewMessageModal = false">取消</button>
        </div>
      </div>
    </div>

    <!-- Feedback Modal -->
    <div v-if="showFeedbackModal" class="modal-overlay" @click="showFeedbackModal = false">
      <div class="new-message-modal" @click.stop :class="{ 'light-mode': !isDarkMode }">
        <div class="modal-header" style="position: relative;">
          <h3 style="width: 100%; text-align: center;">信件反馈 ({{ processingAction === 'process' ? '处理' : '拒绝' }})</h3>
          <button class="close-btn" @click="showFeedbackModal = false" style="position: absolute; right: 10px; top: 10px; background: none; border: none; color: inherit; font-size: 20px; cursor: pointer;">&times;</button>
        </div>
        <div class="modal-body">
          <textarea 
            v-model="feedbackContent" 
            placeholder="请输入反馈内容（最多30字，可选）" 
            maxlength="30"
          ></textarea>
          <div class="char-count">{{ feedbackContent.length }}/30</div>
        </div>
        <div class="modal-footer" style="display: flex; justify-content: center; gap: 30px; padding: 15px 30px;">
          <button class="btn confirm" @click="submitFeedback">确认</button>
          <button class="btn cancel" @click="showFeedbackModal = false">取消</button>
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

.guide-toggle {
  width: 40px !important;
  height: 40px !important;
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  border-radius: 50% !important;
  padding: 0 !important;
  border: 1px solid #ff69b4;
  background: rgba(255, 255, 255, 0.1);
  color: #ff69b4;
  cursor: pointer;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.guide-toggle:hover {
  background: rgba(255, 105, 180, 0.3);
}

.guide-toggle svg {
  width: 20px !important;
  height: 20px !important;
  min-width: 20px !important;
  min-height: 20px !important;
  display: block;
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

.login-active.admin:not(.dropdown-active):hover {
  background: rgba(0, 191, 255, 0.3);
  box-shadow: 0 0 15px rgba(0, 191, 255, 0.3);
}

.login-active.banned:not(.dropdown-active):hover {
  background: rgba(255, 69, 0, 0.3);
  box-shadow: 0 0 15px rgba(255, 69, 0, 0.3);
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

.login-active.admin {
  background: rgba(0, 191, 255, 0.2);
  color: #00bfff;
  border: 1px solid #00bfff;
}

.login-active.banned {
  background: rgba(255, 69, 0, 0.2);
  color: #ff4500;
  border: 1px solid #ff4500;
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
.type-select {
  background: rgba(255, 105, 180, 0.1);
  border: 1px solid rgba(255, 105, 180, 0.3);
  color: #fff;
  border-radius: 4px;
  padding: 0 5px;
  font-size: 12px;
  outline: none;
  cursor: pointer;
  transition: all 0.2s;
  height: 35px;
  width: 65px;
  flex-shrink: 0;
}

.type-select:hover {
  background: rgba(255, 105, 180, 0.2);
}

.app-container.light-mode .type-select {
  background: rgba(255, 105, 180, 0.05);
  border: 1px solid rgba(255, 105, 180, 0.2);
  color: #333;
}

.type-select option {
  background: #1a1a2e;
  color: #fff;
}

.app-container.light-mode .type-select option {
  background: #fff;
  color: #333;
}

.pair-input {
  display: flex;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.pair-input input {
  flex: 1;
  min-width: 0;
}

.pair-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  width: 100%;
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

.newnode-toggle-btn {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  background: rgba(255, 165, 0, 0.1);
  color: #FFA500;
  border: 1px solid #FFA500;
  transition: all 0.3s ease;
}

.newnode-toggle-btn:hover {
  background: rgba(255, 165, 0, 0.2);
  box-shadow: 0 0 10px rgba(255, 165, 0, 0.5);
}

.newnode-toggle-btn.active {
  background: rgba(255, 165, 0, 0.8);
  color: #fff;
}

.mailbox-btn {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  background: rgba(80, 227, 194, 0.2);
  color: #50e3c2;
  border: 1px solid #50e3c2;
  transition: all 0.3s ease;
}

.mailbox-btn:hover {
  background: rgba(80, 227, 194, 0.3);
  box-shadow: 0 0 10px rgba(80, 227, 194, 0.5);
}

.mailbox-btn.has-unread {
  background: rgba(243, 156, 18, 0.2);
  color: #f39c12;
  border: 1px solid #f39c12;
}

.mailbox-btn.has-unread:hover {
  background: rgba(243, 156, 18, 0.3);
  box-shadow: 0 0 10px rgba(243, 156, 18, 0.5);
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
.btn.famous-toggle { 
  background: #87CEEB !important; 
  white-space: nowrap;
}
.btn.connection-toggle {
  white-space: nowrap;
}

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
  scrollbar-width: none; /* Firefox */
}

.history-list::-webkit-scrollbar {
  display: none; /* Chrome, Safari, Edge */
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

.mailbox-modal, .new-message-modal {
  background: #1a1a2e;
  border: 1px solid #ff69b4;
  border-radius: 10px;
  width: 90%;
  max-width: 600px;
  height: 65vh; /* Reduced fixed height for mailbox */
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: #fff;
}

.new-message-modal {
  max-width: 400px;
  height: auto; /* New message modal adapts to content */
  max-height: 80vh;
}

.mailbox-modal.light-mode, .new-message-modal.light-mode {
  background: #fff;
  color: #333;
}

.mailbox-content {
  flex: 1;
  overflow-y: auto;
  padding: 15px;
  /* Hide scrollbar for Chrome, Safari and Opera */
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.mailbox-content::-webkit-scrollbar {
  display: none;
}

.mailbox-item {
  border-bottom: 1px solid rgba(255, 105, 180, 0.2);
  padding: 4px 0; /* Further reduced vertical padding */
  display: flex;
  flex-direction: column;
  gap: 4px; /* Reduced gap inside items */
}

.mailbox-item:last-child {
  border-bottom: none;
}

.msg-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 2px; /* Reduced margin */
}

.msg-user {
  font-weight: bold;
  color: #ff69b4;
  font-size: 14px;
}

.msg-time {
  font-size: 11px;
  color: #888;
}

.msg-body {
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-width: 100%;
}

.msg-body-inner {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.msg-body-inner.expanded {
  display: block;
  overflow: visible;
  -webkit-line-clamp: initial;
}

.expand-toggle {
  color: #ff69b4;
  font-size: 12px;
  cursor: pointer;
  margin-top: 4px;
  display: inline-block;
}

.expand-toggle:hover {
  text-decoration: underline;
}

.msg-status {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.status-text.unprocessed {
  color: #f39c12;
  font-size: 12px;
}

.status-info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-size: 11px;
  color: #888;
  gap: 2px;
}

.status-info span:first-child {
  color: #50e3c2;
  font-weight: bold;
  font-size: 11px;
}

.status-info .feedback-info {
   font-size: 11px;
   font-weight: bold;
}

.status-info span:nth-child(3) {
  color: #87CEEB;
}

.process-btn {
  background: #50e3c2;
  color: #fff;
  border: none;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.mailbox-add-btn-wrapper {
  padding: 10px 0 20px 0;
  border-bottom: 1px dashed rgba(255, 105, 180, 0.5);
  margin-bottom: 10px;
}

.mailbox-add-btn-large {
  width: 100%;
  padding: 12px;
  background: rgba(255, 105, 180, 0.1);
  border: 2px dashed #ff69b4;
  border-radius: 8px;
  color: #ff69b4;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  transition: all 0.3s ease;
}

.mailbox-add-btn-large:hover {
  background: rgba(255, 105, 180, 0.2);
  box-shadow: 0 0 15px rgba(255, 105, 180, 0.3);
}

.new-message-modal .modal-body {
  padding: 20px;
}

.new-message-modal textarea {
  width: 100%;
  height: 120px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid #ff69b4;
  border-radius: 5px;
  color: inherit;
  padding: 10px;
  resize: none;
  font-family: inherit;
}

.char-count {
  text-align: right;
  font-size: 12px;
  color: #888;
  margin-top: 5px;
}

.no-messages {
  text-align: center;
  padding: 40px;
  color: #888;
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
