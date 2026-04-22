import { reactive, ref } from 'vue'
import axios from 'axios'

export function useNodeForm(apiBase, currentUser, deps, notify = () => {}) {
  // deps: { selectedNode, isPanelOpen, fetchGraphData, fetchUserInfo, getNetwork, getNodesData, applyFilters }

  const isEditing = ref(false)
  const isAdding = ref(false)
  const parentIdForNewNode = ref(null)
  const isSubmittingNode = ref(false)
  const isDeletingNode = ref(false)

  const editForm = reactive({
    id: null,
    name: '',
    source: { name: '', link: '', type: '其他' },
    related: [],
    tags: '',
    extension: [],
    introduction: '',
    imageFile: null,
    imagePreview: null
  })

  const startEdit = () => {
    isEditing.value = true

    let rawSource = deps.selectedNode.value.source
    if (typeof rawSource === 'string') {
      try { rawSource = JSON.parse(rawSource) }
      catch (e) { rawSource = { name: rawSource, link: '', type: '其他' } }
    }
    if (!rawSource.type) rawSource.type = '其他'

    let rawRelated = deps.selectedNode.value.related || []
    if (typeof rawRelated === 'string') {
      try { rawRelated = JSON.parse(rawRelated) }
      catch (e) { rawRelated = [] }
    }
    if (!Array.isArray(rawRelated)) rawRelated = []

    rawRelated = rawRelated.map(item => ({
      name: item.name || '',
      link: item.link || '',
      type: item.type || '其他'
    }))

    Object.assign(editForm, {
      id: deps.selectedNode.value.id,
      name: deps.selectedNode.value.name,
      source: JSON.parse(JSON.stringify(rawSource)),
      related: JSON.parse(JSON.stringify(rawRelated)),
      tags: Array.isArray(deps.selectedNode.value.tags) ? deps.selectedNode.value.tags.join(',') : '',
      extension: deps.selectedNode.value.extension || [],
      introduction: deps.selectedNode.value.introduction || '',
      imageFile: null,
      imagePreview: deps.selectedNode.value.image
    })
  }

  const startAdd = () => {
    parentIdForNewNode.value = deps.selectedNode.value ? deps.selectedNode.value.id : null
    isAdding.value = true
    deps.isPanelOpen.value = true
    Object.assign(editForm, {
      id: null,
      name: '',
      source: { name: '', link: '', type: '其他' },
      related: [],
      tags: '',
      introduction: '',
      imageFile: null,
      imagePreview: null
    })
  }

  const cancelEdit = () => {
    if (isSubmittingNode.value) return
    isEditing.value = false
    isAdding.value = false
    parentIdForNewNode.value = null
  }

  const addRelated = () => {
    editForm.related.push({ name: '', link: '', type: '其他' })
  }

  const removeRelated = (index) => {
    editForm.related.splice(index, 1)
  }

  const submitForm = async () => {
    if (isSubmittingNode.value) return

    if (!editForm.name.trim()) {
      notify('请输入形象名字', 'error')
      return
    }
    if (!editForm.source.name.trim()) {
      notify('请输入出处作品名字', 'error')
      return
    }

    const network = deps.getNetwork()
    const nodesData = deps.getNodesData()

    const formData = new FormData()
    formData.append('name', editForm.name)

    const cleanedRelated = editForm.related.filter(item => item.name.trim() !== '')

    formData.append('source', JSON.stringify(editForm.source))
    formData.append('related', JSON.stringify(cleanedRelated))
    formData.append('tags', JSON.stringify(editForm.tags.split(',').map(t => t.trim())))
    formData.append('extension', JSON.stringify(isAdding.value ? [] : editForm.extension))
    formData.append('introduction', editForm.introduction)
    formData.append('user_id', currentUser.user_id)
    formData.append('nickname', currentUser.nickname)
    if (parentIdForNewNode.value) {
      formData.append('parent_id', parentIdForNewNode.value)
      if (isAdding.value && network) {
        const parentPos = network.getPositions([parentIdForNewNode.value])[parentIdForNewNode.value]
        if (parentPos) {
          const angle = Math.random() * 2 * Math.PI
          const distance = 150
          formData.append('x', parentPos.x + Math.cos(angle) * distance)
          formData.append('y', parentPos.y + Math.sin(angle) * distance)
        }
      }
    }
    if (editForm.imageFile) {
      formData.append('image', editForm.imageFile)
    }

    isSubmittingNode.value = true

    try {
      let resultNode
      if (isAdding.value) {
        const resp = await axios.post(`${apiBase}/api/nodes`, formData)
        resultNode = resp.data
        await deps.fetchGraphData()

        if (network) {
          network.setOptions({ physics: { enabled: true } })
          network.startSimulation()
          setTimeout(() => {
            if (network) network.setOptions({ physics: { enabled: false } })
          }, 3000)
        }
      } else {
        const resp = await axios.put(`${apiBase}/api/nodes/${editForm.id}`, formData)
        resultNode = resp.data

        const currentPos = network ? network.getPositions([resultNode.id])[resultNode.id] : null

        const finalImageUrl = resultNode.image
          ? (resultNode.image.startsWith('http') ? resultNode.image : `${apiBase}${resultNode.image}`)
          : `${apiBase}/images/default.webp`

        nodesData.update({
          ...resultNode,
          id: resultNode.id,
          label: resultNode.name,
          image: finalImageUrl,
          x: currentPos ? currentPos.x : resultNode.x,
          y: currentPos ? currentPos.y : resultNode.y
        })

        if (deps.selectedNode.value && deps.selectedNode.value.id === resultNode.id) {
          Object.assign(deps.selectedNode.value, resultNode)
        }

        deps.applyFilters()
      }

      await deps.fetchUserInfo(currentUser.user_id, currentUser.nickname)
      const successMessage = isAdding.value ? '新增形象成功' : '修改形象成功'
      isEditing.value = false
      isAdding.value = false
      deps.isPanelOpen.value = false
      notify(successMessage)
    } catch (error) {
      notify(error.response?.data?.detail || '保存失败', 'error')
    } finally {
      isSubmittingNode.value = false
    }
  }

  const deleteNode = async () => {
    if (isDeletingNode.value) return

    const confirmName = prompt(`你确定要删除 ${deps.selectedNode.value.name} 吗？请输入名字确认删除`)
    if (confirmName === deps.selectedNode.value.name) {
      isDeletingNode.value = true

      try {
        await axios.delete(`${apiBase}/api/nodes/${deps.selectedNode.value.id}?user_id=${currentUser.user_id}&nickname=${currentUser.nickname}`)
        await deps.fetchGraphData()

        const network = deps.getNetwork()
        if (network) {
          network.setOptions({ physics: { enabled: true } })
          network.startSimulation()
          setTimeout(() => {
            if (network) network.setOptions({ physics: { enabled: false } })
          }, 3000)
        }

        await deps.fetchUserInfo(currentUser.user_id, currentUser.nickname)
        deps.isPanelOpen.value = false
        notify('删除成功')
      } catch (error) {
        notify(error.response?.data?.detail || '删除失败', 'error')
      } finally {
        isDeletingNode.value = false
      }
    } else if (confirmName !== null) {
      notify('名字不一致，取消删除', 'error')
    }
  }

  return {
    editForm,
    isEditing,
    isAdding,
    isSubmittingNode,
    isDeletingNode,
    parentIdForNewNode,
    startEdit,
    startAdd,
    cancelEdit,
    addRelated,
    removeRelated,
    submitForm,
    deleteNode
  }
}
