<script setup>
import { onMounted, onUnmounted, ref, reactive, nextTick } from 'vue'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import axios from 'axios'

const apiBase = 'http://localhost:8000'
const container = ref(null)
const loading = ref(true)
const selectedNode = ref(null)
const isPanelOpen = ref(false)
const isDropdownOpen = ref(false)
const currentUser = reactive({
  user_id: 'guest',
  nickname: '游客',
  logged_in: false,
  role: 'visitor',
  quota: null
})

const fetchUserInfo = async (userId = 'guest', nickname = '游客') => {
  try {
    const response = await axios.get(`${apiBase}/api/user/info?user_id=${userId}&nickname=${nickname}`)
    Object.assign(currentUser, response.data)
  } catch (error) {
    console.error('Failed to fetch user info:', error)
  }
}

const isEditing = ref(false)
const isAdding = ref(false)
const searchQuery = ref('')
const searchResults = ref([])
const activeFilters = ref([])

const editForm = reactive({
  id: null,
  name: '',
  source: { name: '', link: '' },
  related: [],
  tags: '',
  extension: [],
  imageFile: null,
  imagePreview: null
})

let network = null
let nodesData = new DataSet([])
let edgesData = new DataSet([])

// Track focused node to handle enlargement state
const focusedNodeId = ref(null)

const fetchGraphData = async () => {
  try {
    const response = await axios.get(`${apiBase}/api/nodes`)
    const data = response.data.nodes

    renderNodes(data)
    loading.value = false
  } catch (error) {
    console.error('Failed to fetch data:', error)
  }
}

const isDarkMode = ref(true)

const toggleDarkMode = () => {
  isDarkMode.value = !isDarkMode.value
  
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
    return {
      ...node,
      source,
      related,
      id: node.id,
      label: node.name,
      shape: 'circularImage',
      image: imageUrl,
      brokenImage: `${apiBase}/images/default.png`,
      color: {
        border: '#ff69b4',
        background: isDarkMode.value ? '#1a1a2e' : '#ffffff'
      },
      shapeProperties: {
         useBorderWithImage: true
      }
    };
  })

  const edges = []
  data.forEach(node => {
    if (node.extension) {
      node.extension.forEach(targetId => {
        edges.push({ 
          id: `${node.id}-${targetId}`, 
          from: node.id, 
          to: targetId 
        })
      })
    }
  })

  nodesData.clear()
  nodesData.add(nodes)
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
       nodesData.update({ id: focusedNodeId.value, size: 40 })
    }
    focusedNodeId.value = nodeId
    nodesData.update({ id: nodeId, size: 55 })
    
    selectedNode.value = node
    isPanelOpen.value = true
    network.focus(nodeId, {
      scale: 1,
      animation: { duration: 600, easingFunction: 'easeInOutQuad' }
    })
  }
}

const resetView = () => {
  if (network) {
    if (focusedNodeId.value) {
      nodesData.update({ id: focusedNodeId.value, size: 40 })
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

const submitForm = async () => {
  const formData = new FormData()
  formData.append('name', editForm.name)
  
  // Clean empty links or names from related
  const cleanedRelated = editForm.related.filter(item => item.name.trim() !== '')
  
  formData.append('source', JSON.stringify(editForm.source))
  formData.append('related', JSON.stringify(cleanedRelated))
  formData.append('tags', JSON.stringify(editForm.tags.split(',').map(t => t.trim())))
  formData.append('extension', JSON.stringify(isAdding.value ? [] : editForm.extension))
  formData.append('user_id', currentUser.user_id)
  if (parentIdForNewNode.value) {
    formData.append('parent_id', parentIdForNewNode.value)
  }
  if (editForm.imageFile) {
    formData.append('image', editForm.imageFile)
  }

  try {
    if (isAdding.value) {
      await axios.post(`${apiBase}/api/nodes`, formData)
    } else {
      await axios.put(`${apiBase}/api/nodes/${editForm.id}`, formData)
    }
    await fetchGraphData()
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
      await axios.delete(`${apiBase}/api/nodes/${selectedNode.value.id}?user_id=${currentUser.user_id}`)
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
    // Delay slightly to allow animation out if needed, but not necessary with v-if/transition
  } else {
    isDropdownOpen.value = true
  }
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
      arrowStrikethrough: false
    },
    physics: {
      enabled: true,
      stabilization: false,
      barnesHut: {
        gravitationalConstant: -1000,
        centralGravity: 0.02,
        springLength: 200,
        springConstant: 0.01,
        damping: 0.4,
        avoidOverlap: 1
      },
      minVelocity: 0.01
    },
    layout: {
      randomSeed: 42
    },
    interaction: {
      hover: true,
      tooltipDelay: 200
    }
  }

  network = new Network(container.value, data, options)

  network.on('click', (params) => {
    if (params.nodes.length > 0) {
      if (isEditing.value || isAdding.value) {
        cancelEdit()
      }
      
      const nodeId = params.nodes[0]
      if (focusedNodeId.value === nodeId) {
        // Deselect if clicking the same node
        nodesData.update({ id: nodeId, size: 40 })
        focusedNodeId.value = null
        isPanelOpen.value = false
      } else {
        focusNode(nodeId)
      }
    } else {
      if (focusedNodeId.value) {
        nodesData.update({ id: focusedNodeId.value, size: 40 })
        focusedNodeId.value = null
      }
      isPanelOpen.value = false
      cancelEdit()
    }
  })
  
  network.on('hoverNode', (params) => {
     const nodeId = params.node
     nodesData.update({id: nodeId, size: 55})
     document.body.style.cursor = 'pointer'
  })
  
  network.on('blurNode', (params) => {
      const nodeId = params.node
      nodesData.update({id: nodeId, size: 40})
      document.body.style.cursor = 'default'
  })
}

onMounted(async () => {
  // Check URL for callback params
  const params = new URLSearchParams(window.location.search)
  const userIdFromUrl = params.get('user_id')
  const nicknameFromUrl = params.get('nickname')

  if (userIdFromUrl && nicknameFromUrl) {
    localStorage.setItem('user_id', userIdFromUrl)
    localStorage.setItem('nickname', nicknameFromUrl)
    // Clean up URL
    window.history.replaceState({}, document.title, "/")
  }

  const savedUserId = localStorage.getItem('user_id') || 'guest'
  const savedNickname = localStorage.getItem('nickname') || '游客'
  
  await fetchUserInfo(savedUserId, savedNickname)
  await fetchGraphData()
  initNetwork()

  window.addEventListener('click', () => {
    isDropdownOpen.value = false
  })
})
</script>

<template>
  <div class="app-container" :class="{ 'light-mode': !isDarkMode }">
    <!-- Loading Animation -->
    <div v-if="loading" class="loading-overlay">
      <div class="loader"></div>
      <p>正在加载千早爱音的世界...</p>
    </div>

    <!-- UI Buttons -->
    <div class="ui-layer top-left">
      <button class="home-btn pink-btn" @click="resetView">回到中心</button>
    </div>

    <div class="ui-layer top-right">
      <div class="header-controls">
        <button class="theme-toggle pink-btn" @click="toggleDarkMode" :class="{ 'dark-mode-btn': isDarkMode }">
          {{ isDarkMode ? '☀' : '🌙' }}
        </button>
        <div class="user-status" :class="currentUser.logged_in ? 'login-active' : 'login-guest'" @click="toggleDropdown">
          {{ currentUser.logged_in ? `已登录：${currentUser.nickname}` : '未登录' }}
          <Transition name="fade">
            <div class="user-dropdown" v-if="isDropdownOpen" @click.stop>
              <template v-if="!currentUser.logged_in">
                <button @click="loginWithBangumi">使用 Bangumi 账号登录</button>
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
                </div>
                <button @click="logout" class="logout-btn">退出登录</button>
              </template>
            </div>
          </Transition>
        </div>
      </div>
    </div>

    <div class="ui-layer bottom-left">
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

    <!-- Graph Container -->
    <div 
      ref="container" 
      class="graph-container" 
      :class="{ 'shifted': isPanelOpen }"
    ></div>

    <!-- Right Panel -->
    <Transition name="slide">
      <div v-if="isPanelOpen" class="side-panel">
        <button class="close-btn" @click="isPanelOpen = false">×</button>
        
        <div class="panel-content">
          <!-- View Mode -->
          <template v-if="!isEditing && !isAdding && selectedNode">
            <div class="image-container">
              <img 
                :src="selectedNode.image.startsWith('http') ? selectedNode.image : `${apiBase}${selectedNode.image}`" 
                :alt="selectedNode.name"
                onerror="this.src='https://via.placeholder.com/200/ff69b4/ffffff?text=?'"
              >
            </div>
            
            <h2 class="node-name">{{ selectedNode.name }}</h2>
            
            <div class="info-item">
              <label>出处：</label>
              <a v-if="selectedNode.source.link" :href="selectedNode.source.link" target="_blank" class="info-link">{{ selectedNode.source.name }}</a>
              <span v-else>{{ selectedNode.source.name }}</span>
            </div>
            
            <div class="info-item">
              <label>标签：</label>
              <div class="tag-list">
                <span v-for="tag in selectedNode.tags" :key="tag" class="tag">{{ tag }}</span>
              </div>
            </div>
            
            <div class="info-item">
              <label>相关作品：</label>
              <div class="related-list">
                <div v-for="(item, idx) in selectedNode.related" :key="idx" class="related-item">
                  <a v-if="item.link" :href="item.link" target="_blank" class="info-link">{{ item.name }}</a>
                  <span v-else>{{ item.name }}</span>
                </div>
              </div>
            </div>

            <div class="action-buttons">
              <button class="btn edit" @click="startEdit">修改</button>
              <button class="btn add" @click="startAdd">新增</button>
              <button class="btn delete" @click="deleteNode">删除</button>
            </div>
          </template>

          <!-- Edit/Add Mode -->
          <template v-else>
            <h2 class="node-name">{{ isAdding ? '新增形象' : '修改形象' }}</h2>
            
            <div class="image-container editable" @click="$refs.fileInput.click()">
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

.app-container.light-mode .pair-input input {
  background: #fdfdfd;
  color: #1a1a2e;
}

.app-container.light-mode .user-dropdown {
  background: #ffffff;
  color: #1a1a2e;
  border: 1px solid #ff69b4;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.app-container.light-mode .search-results {
  background: #ffffff;
  color: #1a1a2e;
}

.app-container.light-mode .search-container input {
  background: rgba(255, 255, 255, 0.8);
  color: #1a1a2e;
  border: 1px solid #ff69b4;
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

.header-controls {
  display: flex;
  gap: 15px;
  align-items: center;
  position: relative;
}

.theme-toggle {
  width: 40px;
  height: 40px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 20px;
  border-radius: 50%;
  padding: 0;
  border: 1px solid #ff69b4;
  background: rgba(255, 255, 255, 0.1);
  color: #ff69b4;
  cursor: pointer;
  transition: all 0.3s ease;
}

.theme-toggle:hover {
  background: rgba(255, 105, 180, 0.3);
}

.user-status {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  position: relative;
  height: 40px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
}

.user-dropdown {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  background: #1a1a2e;
  border: 1px solid #ff69b4;
  border-radius: 12px;
  width: 240px;
  overflow: hidden;
  z-index: 1000;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  padding: 15px;
  color: #fff;
}

.user-role-badge {
  text-align: center;
  padding: 5px;
  border-radius: 4px;
  margin-bottom: 15px;
  font-weight: bold;
  font-size: 12px;
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
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.quota-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.quota-item span:first-child {
  font-size: 12px;
  color: #888;
}

.quota-num {
  font-size: 18px;
  font-weight: bold;
  color: #ff69b4;
}

.logout-btn {
  width: 100%;
  padding: 10px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  background: rgba(255, 105, 180, 0.2);
  color: #ff69b4;
}

/* Animations */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
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

.user-status {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  position: relative;
}

.login-guest {
  background: rgba(128, 128, 128, 0.2);
  color: #888;
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

.input-group input {
  width: 100%;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 105, 180, 0.3);
  color: #fff;
  padding: 8px 12px;
  border-radius: 4px;
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
  padding: 40px 20px;
  display: flex;
  flex-direction: column;
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

.panel-content {
  overflow-y: auto;
  flex: 1;
}

.image-container {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
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

/* Transition */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.5s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
