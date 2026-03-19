import { ref } from 'vue'

export function useTheme(getNetwork, getNodesData) {
  const isDarkMode = ref(localStorage.getItem('theme') !== 'light')

  const toggleDarkMode = () => {
    isDarkMode.value = !isDarkMode.value
    localStorage.setItem('theme', isDarkMode.value ? 'dark' : 'light')

    const network = getNetwork()
    const nodesData = getNodesData()
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

  return {
    isDarkMode,
    toggleDarkMode
  }
}
