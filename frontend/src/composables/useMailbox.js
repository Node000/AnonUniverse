<script setup>
import { ref, reactive } from 'vue'

export function useMailbox(apiBase, currentUser) {
  const mailboxMessages = ref([])
  const showMailboxModal = ref(false)
  const newMessageContent = ref('')
  const showNewMessageModal = ref(false)
  const showFeedbackModal = ref(false)
  const processingMessageId = ref(null)
  const processingAction = ref('')
  const feedbackContent = ref('')

  const fetchMailbox = async () => {
    try {
      const resp = await axios.get(`${apiBase}/api/mail/list?user_id=${currentUser.user_id}`)
      mailboxMessages.value = resp.data
    } catch (e) { console.error(e) }
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
    fetchMailbox
  }
}
