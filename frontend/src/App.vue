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
import GuideModal from './components/GuideModal.vue'
import NotificationModal from './components/NotificationModal.vue'
import SiteInfoPanel from './components/SiteInfoPanel.vue'
import MailboxModal from './components/MailboxModal.vue'
import NewMessageModal from './components/NewMessageModal.vue'
import FeedbackModal from './components/FeedbackModal.vue'
import PendingApplicationsModal from './components/PendingApplicationsModal.vue'
import ImageCropModal from './components/ImageCropModal.vue'
import NodeSidePanel from './components/NodeSidePanel.vue'

// Composables
import { useUser } from './composables/useUser'
import { useMouseEffects } from './composables/useMouseEffects'
import { useHistory } from './composables/useHistory'
import { useMailbox } from './composables/useMailbox'
import { useImageCropper } from './composables/useImageCropper'
import { useSearchFilter } from './composables/useSearchFilter'

const apiBase = import.meta.env.DEV ? 'http://localhost:8000' : ''
const vizContainer = ref(null)

// Use Composables
const {
  currentUser, isDropdownOpen, fetchUserInfo,
  loginWithBangumi, logout, toggleDropdown, initAuthFromUrl
} = useUser(apiBase)
const { ripples, handleMouseMove, handleClickRipple } = useMouseEffects()
const { showHistory, historyData, historyType, isHistoryLoading, toggleHistory } = useHistory(apiBase)
const {
  mailboxMessages, showMailboxModal, newMessageContent, showNewMessageModal,
  showFeedbackModal, processingAction, feedbackContent,
  canSendMessage, unprocessedMailCount, shouldShowExpand,
  fetchMailbox, openMailbox, submitMailboxMessage, handleProcessMessage, submitFeedback
} = useMailbox(apiBase, currentUser, fetchUserInfo)

const loading = ref(true)
const selectedNode = ref(null)
const isPanelOpen = ref(false)
let isDraggingNode = false // Track dragging state for physics optimization

const isEditing = ref(false)
const isAdding = ref(false)

// Famous Fanwork state
const showFamous = ref(false)
const showNewNodes = ref(false)
const pendingApplications = ref([])
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

// Site info state
const showSiteInfo = ref(false)

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

// Search & Filter composable (initialized early since nodesData/edgesData are ready)
// focusNode is passed lazily via wrapper since it's defined later
const {
  searchQuery, searchResults, activeFilters,
  handleSearch, selectSearchResult, removeFilter, applyFilters
} = useSearchFilter(nodesData, edgesData, (nodeId) => focusNode(nodeId))

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

// Image Cropping logic (composable)
const {
  showCropModal, cropCanvas,
  handleImageUpload, handleCropMouseDown, handleCropMouseMove,
  handleCropMouseUp, handleCropWheel, confirmCrop, cancelCrop
} = useImageCropper(editForm)

const addRelated = () => {
  editForm.related.push({ name: '', link: '', type: '其他' })
}

const removeRelated = (index) => {
  editForm.related.splice(index, 1)
}

// Side Panel drag logic now handled by NodeSidePanel component

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

const globalClickHandler = (e) => {
  isDropdownOpen.value = false
  closePopups()
  handleClickRipple(e)
}

onMounted(async () => {
  await initAuthFromUrl()
  await fetchGraphData()
  initNetwork()
  await fetchMailbox()

  // 漫游指南：检查是否首次进入
  if (!localStorage.getItem('guide_seen')) {
    setTimeout(() => {
      showGuideModal.value = true
    }, 1500)
  }

  window.addEventListener('click', globalClickHandler)
  window.addEventListener('mousemove', handleMouseMove)
})

onUnmounted(() => {
  window.removeEventListener('click', globalClickHandler)
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

    <div 
      ref="vizContainer" 
      class="graph-container" 
      :class="{ 'shifted': isPanelOpen }"
    ></div>

    <!-- Right Panel -->
    <NodeSidePanel
      :isPanelOpen="isPanelOpen"
      :isEditing="isEditing"
      :isAdding="isAdding"
      :selectedNode="selectedNode"
      :editForm="editForm"
      :apiBase="apiBase"
      :currentUser="currentUser"
      :canEditSelectedNode="canEditSelectedNode"
      :canAddNode="canAddNode"
      :canDeleteSelectedNode="canDeleteSelectedNode"
      :deleteDisabledReason="deleteDisabledReason"
      :isConnectionEditMode="isConnectionEditMode"
      @close="isPanelOpen = false"
      @toggleHistory="toggleHistory"
      @startEdit="startEdit"
      @startAdd="startAdd"
      @cancelEdit="cancelEdit"
      @submitForm="submitForm"
      @deleteNode="deleteNode"
      @saveNodePosition="saveNodePosition"
      @toggleFamousStatus="toggleFamousStatus"
      @toggleConnectionEditMode="toggleConnectionEditMode"
      @addRelated="addRelated"
      @removeRelated="removeRelated"
      @imageUpload="handleImageUpload"
    />

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
    <GuideModal :show="showGuideModal" @close="closeGuide" />

    <!-- Site Info Bottom Panel -->
    <SiteInfoPanel :show="showSiteInfo" />

    <!-- Mailbox Feedback Notification Modal -->
    <NotificationModal
      :show="showNotificationModal"
      :notifiedMails="notifiedMails"
      @close="showNotificationModal = false"
    />

    <!-- Mailbox Modal -->
    <MailboxModal
      :show="showMailboxModal"
      :isDarkMode="isDarkMode"
      :mailboxMessages="mailboxMessages"
      :canSendMessage="canSendMessage"
      :currentUser="currentUser"
      @close="showMailboxModal = false"
      @openNewMessage="showNewMessageModal = true"
      @processMessage="handleProcessMessage"
    />

    <!-- New Message Modal -->
    <NewMessageModal
      :show="showNewMessageModal"
      :isDarkMode="isDarkMode"
      v-model="newMessageContent"
      @close="showNewMessageModal = false"
      @submit="submitMailboxMessage"
    />

    <!-- Feedback Modal -->
    <FeedbackModal
      :show="showFeedbackModal"
      :isDarkMode="isDarkMode"
      v-model="feedbackContent"
      :actionLabel="processingAction === 'process' ? '处理' : '拒绝'"
      @close="showFeedbackModal = false"
      @submit="submitFeedback"
    />

    <!-- Pending Applications Modal -->
    <PendingApplicationsModal
      :show="showPendingApplicationsModal"
      :pendingApplications="pendingApplications"
      @close="showPendingApplicationsModal = false"
      @approve="(id) => processApplication(id, 'approve')"
      @reject="(id) => processApplication(id, 'reject')"
      @focusNode="focusNode"
    />

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

/* 全局滚动条样式：粉色滑块，无轨道 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background-color: #ff69b4;
  border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
  background-color: #ff1493;
}

/* 兼容 Firefox */
* {
  scrollbar-width: thin;
  scrollbar-color: #ff69b4 transparent;
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
  cursor: grab;
}

.panel-content:active {
  cursor: grabbing;
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
