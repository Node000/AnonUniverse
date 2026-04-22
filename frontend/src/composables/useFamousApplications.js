import { ref } from 'vue'
import axios from 'axios'

export function useFamousApplications(apiBase, currentUser, getNodesData, selectedNode, notify = () => {}) {
  const pendingApplications = ref([])
  const showApplyFamousModal = ref(false)
  const showPendingApplicationsModal = ref(false)
  const isTogglingFamous = ref(false)
  const processingApplicationId = ref(null)

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

  const openPendingApplications = async () => {
    await fetchPendingApplications()
    showPendingApplicationsModal.value = true
  }

  const toggleFamousStatus = async () => {
    if (!selectedNode.value || currentUser.role !== 'admin' || isTogglingFamous.value) return

    const newStatus = !selectedNode.value.is_famous
    const formData = new FormData()
    formData.append('is_famous', newStatus)
    formData.append('user_id', currentUser.user_id)
    formData.append('nickname', currentUser.nickname)

    isTogglingFamous.value = true

    try {
      await axios.patch(`${apiBase}/api/nodes/${selectedNode.value.id}/famous`, formData)
      const nodesData = getNodesData()
      nodesData.update({ id: selectedNode.value.id, is_famous: newStatus })
      selectedNode.value.is_famous = newStatus
      notify(newStatus ? '已设为知名二创' : '已取消知名二创')
    } catch (error) {
      notify(error.response?.data?.detail || '修改失败', 'error')
    } finally {
      isTogglingFamous.value = false
    }
  }

  const processApplication = async (appId, action) => {
    if (!appId || currentUser.role !== 'admin' || processingApplicationId.value) return

    const targetApplication = pendingApplications.value.find(app => app.id === appId)
    const formData = new FormData()
    formData.append('action', action)
    formData.append('user_id', currentUser.user_id)
    formData.append('nickname', currentUser.nickname)

    processingApplicationId.value = appId

    try {
      await axios.post(`${apiBase}/api/applications/${appId}/process`, formData)

      if (action === 'approve' && targetApplication) {
        const nodesData = getNodesData()
        nodesData.update({ id: targetApplication.node_id, is_famous: true })
        if (selectedNode.value && selectedNode.value.id === targetApplication.node_id) {
          selectedNode.value.is_famous = true
        }
      }

      pendingApplications.value = pendingApplications.value.filter(app => app.id !== appId)
      notify(action === 'approve' ? '申请已同意' : '申请已拒绝')
    } catch (error) {
      notify(error.response?.data?.detail || '处理申请失败', 'error')
    } finally {
      processingApplicationId.value = null
    }
  }

  return {
    pendingApplications,
    showApplyFamousModal,
    showPendingApplicationsModal,
    isTogglingFamous,
    processingApplicationId,
    fetchPendingApplications,
    openPendingApplications,
    toggleFamousStatus,
    processApplication
  }
}
