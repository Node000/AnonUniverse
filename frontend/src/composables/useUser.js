// Logic for user data, auth, and session management
import { reactive, ref } from 'vue'
import axios from 'axios'

export function useUser(apiBase) {
  const currentUser = reactive({
    user_id: 'guest',
    nickname: '游客',
    logged_in: false,
    role: 'visitor',
    quota: null,
    notifications: []
  })

  const isDropdownOpen = ref(false)

  const fetchUserInfo = async (userId = 'guest', nickname = '游客') => {
    try {
      const url = `${apiBase}/api/user/info?user_id=${userId}&nickname=${encodeURIComponent(nickname)}`
      const response = await axios.get(url)
      Object.assign(currentUser, response.data)
      return response.data
    } catch (error) {
      console.error('Failed to fetch user info:', error)
      if (userId !== 'guest') {
         currentUser.user_id = userId
         currentUser.nickname = nickname
         currentUser.logged_in = true
         if (!currentUser.role) currentUser.role = 'visitor'
         if (!currentUser.quota) currentUser.quota = { adds: 0, edits: 0, deletes: 0 }
      }
      return currentUser
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
    if (e) e.stopPropagation()
    isDropdownOpen.value = !isDropdownOpen.value
  }

  const initAuthFromUrl = async () => {
    const params = new URLSearchParams(window.location.search)
    const userIdFromUrl = params.get('user_id')
    const nicknameFromUrl = params.get('nickname')

    if (userIdFromUrl && nicknameFromUrl) {
      console.log("Found auth params in URL, saving to storage:", userIdFromUrl, nicknameFromUrl)
      localStorage.setItem('user_id', userIdFromUrl)
      localStorage.setItem('nickname', nicknameFromUrl)

      currentUser.user_id = userIdFromUrl
      currentUser.nickname = nicknameFromUrl
      currentUser.logged_in = true

      await fetchUserInfo(userIdFromUrl, nicknameFromUrl)

      try {
        const url = new URL(window.location.href)
        url.searchParams.delete('user_id')
        url.searchParams.delete('nickname')
        window.history.replaceState({}, '', url.toString())
      } catch (e) {
        console.error("Failed to clean URL params", e)
      }
    } else {
      const savedUserId = localStorage.getItem('user_id') || 'guest'
      const savedNickname = localStorage.getItem('nickname') || '游客'
      await fetchUserInfo(savedUserId, savedNickname)
    }
  }

  return {
    currentUser,
    isDropdownOpen,
    fetchUserInfo,
    loginWithBangumi,
    logout,
    toggleDropdown,
    initAuthFromUrl
  }
}
