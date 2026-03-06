<script setup>
import { reactive, onMounted } from 'vue'
import axios from 'axios'

const props = defineProps({
  apiBase: String
})

const currentUser = reactive({
  user_id: 'guest',
  nickname: '游客',
  logged_in: false,
  role: 'visitor',
  quota: null
})

const fetchUserInfo = async (userId = 'guest', nickname = '游客') => {
  try {
    const url = `${props.apiBase}/api/user/info?user_id=${userId}&nickname=${encodeURIComponent(nickname)}`
    const response = await axios.get(url)
    Object.assign(currentUser, response.data)
  } catch (error) {
    console.error('Failed to fetch user info:', error)
    if (userId !== 'guest') {
       currentUser.user_id = userId
       currentUser.nickname = nickname
       currentUser.logged_in = true
       if (!currentUser.role) currentUser.role = 'visitor'
       if (!currentUser.quota) currentUser.quota = { adds: 0, edits: 0, deletes: 0 }
    }
  }
}

defineExpose({
  currentUser,
  fetchUserInfo
})
</script>

<template>
  <slot :currentUser="currentUser" :fetchUserInfo="fetchUserInfo"></slot>
</template>
