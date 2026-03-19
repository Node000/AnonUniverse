import { ref } from 'vue'

export function useSearchFilter(nodesData, edgesData, focusNode) {
  const searchQuery = ref('')
  const searchResults = ref([])
  const activeFilters = ref([])

  const handleSearch = () => {
    if (!searchQuery.value.trim()) {
      searchResults.value = []
      return
    }
    const q = searchQuery.value.toLowerCase()
    const results = []

    nodesData.get().forEach(node => {
      if (node.name.toLowerCase().includes(q)) {
        results.push({ type: 'node', id: node.id, name: node.name })
      }
      if (node.source && node.source.name && node.source.name.toLowerCase().includes(q)) {
        if (!results.some(r => r.type === 'source' && r.name === node.source.name)) {
          results.push({ type: 'source', name: node.source.name })
        }
      }
      node.tags.forEach(tag => {
        if (tag.toLowerCase().includes(q) && !results.some(r => r.type === 'tag' && r.name === tag)) {
          results.push({ type: 'tag', name: tag })
        }
      })
    })
    searchResults.value = results.slice(0, 10)
  }

  const selectSearchResult = (res) => {
    if (res.type === 'node') {
      focusNode(res.id)
      searchQuery.value = ''
      searchResults.value = []
    } else if (res.type === 'tag' || res.type === 'source') {
      if (!activeFilters.value.includes(res.name)) {
        activeFilters.value.push(res.name)
      }
      searchQuery.value = ''
      searchResults.value = []
      applyFilters()
    }
  }

  const removeFilter = (tag) => {
    activeFilters.value = activeFilters.value.filter(t => t !== tag)
    applyFilters()
  }

  const applyFilters = () => {
    if (activeFilters.value.length === 0) {
      nodesData.update(nodesData.get().map(n => ({ id: n.id, opacity: 1 })))
      edgesData.update(edgesData.get().map(e => ({ id: e.id, opacity: 0.6 })))
      return
    }

    const visibleNodeIds = new Set()
    const nodeUpdates = nodesData.get().map(node => {
      const matchesAll = activeFilters.value.every(f => {
        const matchesSource = node.source && node.source.name === f
        const matchesTag = node.tags.includes(f)
        return matchesSource || matchesTag
      })
      if (matchesAll) visibleNodeIds.add(node.id)
      return { id: node.id, opacity: matchesAll ? 1 : 0.2 }
    })
    nodesData.update(nodeUpdates)

    const edgeUpdates = edgesData.get().map(edge => {
      const isVisible = visibleNodeIds.has(edge.from) && visibleNodeIds.has(edge.to)
      return { id: edge.id, opacity: isVisible ? 0.6 : 0.1 }
    })
    edgesData.update(edgeUpdates)
  }

  return {
    searchQuery,
    searchResults,
    activeFilters,
    handleSearch,
    selectSearchResult,
    removeFilter,
    applyFilters
  }
}
