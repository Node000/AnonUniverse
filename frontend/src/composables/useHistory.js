import { ref } from 'vue'
import axios from 'axios'

export function useHistory(apiBase) {
  const showHistory = ref(false)
  const historyData = ref([])
  const historyType = ref('global')
  const isHistoryLoading = ref(false)

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

  const toggleHistory = async (nodeId = null) => {
    if (showHistory.value) {
      showHistory.value = false
      return
    }
    showHistory.value = true
    await fetchHistory(nodeId)
  }

  return {
    showHistory,
    historyData,
    historyType,
    isHistoryLoading,
    fetchHistory,
    toggleHistory
  }
}
