import { ref } from 'vue'
import axios from 'axios'

export function useFamousApplications(apiBase, currentUser, getNodesData, selectedNode) {
  const pendingApplications = ref([])
  const showApplyFamousModal = ref(false)
  const showPendingApplicationsModal = ref(false)

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
      const nodesData = getNodesData()
      nodesData.update({ id: selectedNode.value.id, is_famous: newStatus })
      selectedNode.value.is_famous = newStatus
    } catch (error) {
      alert(error.response?.data?.detail || '修改失败')
    }
  }

  return {
    pendingApplications,
    showApplyFamousModal,
    showPendingApplicationsModal,
    fetchPendingApplications,
    openPendingApplications,
    toggleFamousStatus
  }
}
