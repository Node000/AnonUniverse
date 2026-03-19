import { ref, computed } from 'vue'
import axios from 'axios'

export function useMailbox(apiBase, currentUser, fetchUserInfo) {
  const mailboxMessages = ref([])
  const showMailboxModal = ref(false)
  const newMessageContent = ref('')
  const showNewMessageModal = ref(false)
  const showFeedbackModal = ref(false)
  const processingMessageId = ref(null)
  const processingAction = ref('')
  const feedbackContent = ref('')

  const canSendMessage = computed(() => {
    if (!currentUser.logged_in) return false
    if (currentUser.role === 'admin') return true
    return currentUser.quota && currentUser.quota.messages < 3
  })

  const unprocessedMailCount = computed(() => {
    return mailboxMessages.value.filter(m => m.status === 'unprocessed').length
  })

  const shouldShowExpand = (msg) => {
    if (!msg.content) return false
    const lines = msg.content.split('\n').length
    if (lines > 2) return true
    if (msg.content.length > 60) return true
    return false
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

  return {
    mailboxMessages,
    showMailboxModal,
    newMessageContent,
    showNewMessageModal,
    showFeedbackModal,
    processingMessageId,
    processingAction,
    feedbackContent,
    canSendMessage,
    unprocessedMailCount,
    shouldShowExpand,
    fetchMailbox,
    openMailbox,
    submitMailboxMessage,
    handleProcessMessage,
    submitFeedback
  }
}
