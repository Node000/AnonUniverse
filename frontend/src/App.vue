<script setup>
import { onMounted, ref, reactive, nextTick } from 'vue'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import axios from 'axios'

const apiBase = 'http://localhost:8000'
const container = ref(null)
const loading = ref(true)
const selectedNode = ref(null)
const isPanelOpen = ref(false)
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
  source: '',
  related: '',
  tags: '',
  imageFile: null,
  imagePreview: null
})

let network = null
let nodesData = new DataSet([])
let edgesData = new DataSet([])

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

const renderNodes = (data) => {
  const nodes = data.map(node => ({
    id: node.id,
    label: node.name,
    shape: 'circularImage',
    image: node.image.startsWith('http') ? node.image : `${apiBase}${node.image}`,
    brokenImage: `https://via.placeholder.com/80/ff69b4/ffffff?text=${encodeURIComponent(node.name[0])}`,
    ...node
  }))

  const edges = []
  data.forEach(node => {
    if (node.connections) {
      node.connections.forEach(targetId => {
        edges.push({ from: node.id, to: targetId })
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
    return
  }
  
  const updates = nodesData.get().map(node => {
    const matchesAll = activeFilters.value.every(f => node.tags.includes(f))
    return { id: node.id, opacity: matchesAll ? 1 : 0.2 }
  })
  nodesData.update(updates)
}

const focusNode = (nodeId) => {
  const node = nodesData.get(nodeId)
  if (node) {
    selectedNode.value = node
    isPanelOpen.value = true
    network.focus(nodeId, {
      scale: 1,
      animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
    })
  }
}

const resetView = () => {
  if (network) {
    network.fit({ animation: true })
    isPanelOpen.value = false
    activeFilters.value = []
    applyFilters()
  }
}

// Edit / Add Actions
const startEdit = () => {
  isEditing.value = true
  Object.assign(editForm, {
    id: selectedNode.value.id,
    name: selectedNode.value.name,
    source: selectedNode.value.source,
    related: selectedNode.value.related,
    tags: selectedNode.value.tags.join(','),
    imagePreview: selectedNode.value.image
  })
}

const startAdd = () => {
  isAdding.value = true
  isPanelOpen.value = true
  Object.assign(editForm, {
    id: null,
    name: '',
    source: '',
    related: '',
    tags: '',
    imagePreview: null
  })
}

const cancelEdit = () => {
  isEditing.value = false
  isAdding.value = false
}

const handleImageUpload = (e) => {
  const file = e.target.files[0]
  if (file) {
    if (file.size > 1024 * 1024) {
      alert('图片大小不能超过 1MB')
      return
    }
    editForm.imageFile = file
    editForm.imagePreview = URL.createObjectURL(file)
  }
}

const submitForm = async () => {
  const formData = new FormData()
  formData.append('name', editForm.name)
  formData.append('source', editForm.source)
  formData.append('related', editForm.related)
  formData.append('tags', JSON.stringify(editForm.tags.split(',').map(t => t.trim())))
  formData.append('connections', JSON.stringify([]))
  formData.append('user_id', currentUser.user_id)
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
}

const initNetwork = () => {
  const data = { nodes: nodesData, edges: edgesData }
  const options = {
    nodes: {
      borderWidth: 3,
      size: 40,
      color: {
        border: '#ff69b4',
        background: '#1a1a2e',
        highlight: { border: '#ff1493', background: '#1a1a2e' }
      },
      font: { color: '#ffffff', size: 14, strokeWidth: 2, strokeColor: '#000000' }
    },
    edges: {
      color: { color: '#ff69b4', highlight: '#ff1493', opacity: 0.6 },
      width: 2
    },
    physics: {
      enabled: true,
      barnesHut: {
        gravitationalConstant: -2000,
        centralGravity: 0.1,
        springLength: 150,
        springConstant: 0.04,
        damping: 0.09,
        avoidOverlap: 0.1
      },
      stabilization: { iterations: 150 }
    },
    layout: {
      improvedLayout: true,
      randomSeed: 42 // Keep it stable
    },
    interaction: {
      hover: true,
      tooltipDelay: 200
    }
  }

  network = new Network(container.value, data, options)

  network.on('click', (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      selectedNode.value = nodesData.get(nodeId)
      isPanelOpen.value = true
    } else {
      isPanelOpen.value = false
    }
  })

  network.on('dragEnd', (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      const pos = network.getPositions([nodeId])[nodeId]
      savePosition(nodeId, pos)
    }
  })
}

const savePosition = async (nodeId, pos) => {
  try {
    await axios.put(`${apiBase}/api/nodes/${nodeId}/position`, pos)
  } catch (error) {
    console.error('Failed to save position:', error)
  }
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
})
</script>

<template>
  <div class="app-container">
    <!-- Loading Animation -->
    <div v-if="loading" class="loading-overlay">
      <div class="loader"></div>
      <p>正在加载千早爱音的世界...</p>
    </div>

    <!-- UI Buttons -->
    <div class="ui-layer top-left">
      <button class="home-btn" @click="resetView">回到中心</button>
    </div>

    <div class="ui-layer top-right">
      <div class="user-status" :class="currentUser.logged_in ? 'login-active' : 'login-guest'">
        {{ currentUser.logged_in ? `已登录：${currentUser.nickname}` : '未登录' }}
        <div class="user-dropdown">
          <button v-if="!currentUser.logged_in" @click="loginWithBangumi">使用 Bangumi 账号登录</button>
          <template v-else>
            <div class="quota-info" v-if="currentUser.role !== 'admin'">
              今日剩余：新{{ 1 - currentUser.quota.adds }} 改{{ 1 - currentUser.quota.edits }} 删{{ 1 - currentUser.quota.deletes }}
            </div>
            <button @click="logout">退出登录</button>
          </template>
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
              <span>{{ selectedNode.source }}</span>
            </div>
            
            <div class="info-item">
              <label>标签：</label>
              <div class="tag-list">
                <span v-for="tag in selectedNode.tags" :key="tag" class="tag">{{ tag }}</span>
              </div>
            </div>
            
            <div class="info-item">
              <label>相关作品：</label>
              <span>{{ selectedNode.related }}</span>
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
              <img v-if="editForm.imagePreview" :src="editForm.imagePreview">
              <div v-else class="upload-placeholder">点击上传图片</div>
              <input type="file" ref="fileInput" hidden @change="handleImageUpload" accept="image/*">
            </div>

            <div class="input-group">
              <label>形象名字</label>
              <input v-model="editForm.name" placeholder="名字">
            </div>

            <div class="input-group">
              <label>出处</label>
              <input v-model="editForm.source" placeholder="出处">
            </div>

            <div class="input-group">
              <label>标签 (逗号分隔)</label>
              <input v-model="editForm.tags" placeholder="标签1, 标签2">
            </div>

            <div class="input-group">
              <label>相关作品</label>
              <input v-model="editForm.related" placeholder="相关作品">
            </div>

            <div class="form-actions">
              <button class="btn confirm" @click="submitForm">确认</button>
              <button class="btn cancel" @click="cancelEdit">取消</button>
            </div>
          </template>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style>
.app-container {
  width: 100vw;
  height: 100vh;
  position: relative;
  overflow: hidden;
  background: #0a0a0f;
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
.top-right { top: 20px; right: 20px; }
.bottom-left { bottom: 20px; left: 20px; }

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
}

.quota-info {
  padding: 10px;
  font-size: 12px;
  color: #888;
  border-bottom: 1px solid rgba(255, 105, 180, 0.1);
}

.user-dropdown {
  display: none;
  position: absolute;
  top: 100%;
  right: 0;
  background: #1a1a2e;
  border: 1px solid #ff69b4;
  border-radius: 8px;
  margin-top: 10px;
  width: 200px;
  overflow: hidden;
}

.user-status:hover .user-dropdown {
  display: block;
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

.image-container.editable {
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.05);
}

.upload-placeholder {
  color: #ff69b4;
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
