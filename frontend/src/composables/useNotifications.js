import { ref } from 'vue'
import axios from 'axios'

export function useNotifications(apiBase, currentUser) {
  const notifiedMails = ref([])
  const showNotificationModal = ref(false)

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
          const formData = new FormData()
          formData.append('user_id', currentUser.user_id)
          await axios.post(`${apiBase}/api/user/clear_notifications`, formData)
        }
      } catch (e) {
        console.error('Failed to check notifications', e)
      }
    }
  }

  return {
    notifiedMails,
    showNotificationModal,
    triggerNotificationCheck
  }
}
