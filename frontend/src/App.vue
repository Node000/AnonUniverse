<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import './styles/app-main.css'

// Components
import Toolbar from './components/Toolbar.vue'
import UserAccount from './components/UserAccount.vue'
import SearchBox from './components/SearchBox.vue'
import HistoryModal from './components/HistoryModal.vue'
import GuideModal from './components/GuideModal.vue'
import NotificationModal from './components/NotificationModal.vue'
import SiteInfoPanel from './components/SiteInfoPanel.vue'
import MailboxModal from './components/MailboxModal.vue'
import NewMessageModal from './components/NewMessageModal.vue'
import FeedbackModal from './components/FeedbackModal.vue'
import PendingApplicationsModal from './components/PendingApplicationsModal.vue'
import NodeSidePanel from './components/NodeSidePanel.vue'

// Composables
import { useUser } from './composables/useUser'
import { useMouseEffects } from './composables/useMouseEffects'
import { useHistory } from './composables/useHistory'
import { useMailbox } from './composables/useMailbox'
import { useImageCropper } from './composables/useImageCropper'
import { useSearchFilter } from './composables/useSearchFilter'
import { useTheme } from './composables/useTheme'
import { useNotifications } from './composables/useNotifications'
import { useFamousApplications } from './composables/useFamousApplications'
import { useGraph } from './composables/useGraph'
import { useNodeForm } from './composables/useNodeForm'

const apiBase = import.meta.env.DEV ? 'http://localhost:8000' : ''

const toastState = reactive({
  visible: false,
  message: '',
  type: 'success'
})
let toastTimer = null

const showToast = (message, type = 'success') => {
  if (!message) return

  toastState.message = message
  toastState.type = type
  toastState.visible = true

  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastState.visible = false
  }, 2600)
}

// --- Initialize composables ---

const {
  currentUser, isDropdownOpen, fetchUserInfo,
  loginWithBangumi, logout, toggleDropdown, initAuthFromUrl
} = useUser(apiBase)

const { ripples, handleMouseMove, handleClickRipple } = useMouseEffects()
const { showHistory, historyData, historyType, isHistoryLoading, toggleHistory } = useHistory(apiBase)
const {
  mailboxMessages, showMailboxModal, newMessageContent, showNewMessageModal,
  showFeedbackModal, processingAction, feedbackContent,
  isSendingMessage, isSubmittingFeedback,
  canSendMessage, unprocessedMailCount, shouldShowExpand,
  fetchMailbox, openMailbox, submitMailboxMessage, handleProcessMessage, submitFeedback
} = useMailbox(apiBase, currentUser, fetchUserInfo, showToast)

const { isDarkMode, toggleDarkMode } = useTheme(
  () => graph.getNetwork(),
  () => graph.getNodesData()
)

const { notifiedMails, showNotificationModal, triggerNotificationCheck } = useNotifications(apiBase, currentUser)

// Shared mutable callbacks object — populated incrementally as composables init
const graphCallbacks = {
  cancelEdit: () => {},
  triggerNotificationCheck,
  applyFilters: () => {},
  activeFilters: ref([]),
  isEditing: ref(false),
  isAdding: ref(false)
}

const graph = useGraph(apiBase, currentUser, isDarkMode, graphCallbacks, showToast)

const {
  vizContainer, loading, selectedNode, isPanelOpen, focusedNodeId,
  showFamous, showNewNodes, isConnectionEditMode,
  isUpdatingConnection, isSavingPosition,
  canDeleteSelectedNode, deleteDisabledReason, canEditSelectedNode, canAddNode, canEditConnections, connectionEditDisabledReason, editButtonsDisabledReason,
  getNetwork, getNodesData, getEdgesData,
  fetchGraphData, focusNode, resetView, toggleConnectionEditMode,
  saveNodePosition, initNetwork
} = graph

// Search & Filter (needs nodesData/edgesData/focusNode)
const {
  searchQuery, searchResults, activeFilters,
  handleSearch, selectSearchResult, removeFilter, applyFilters
} = useSearchFilter(getNodesData(), getEdgesData(), (nodeId) => focusNode(nodeId))

// Node Form
const {
  editForm, isEditing, isAdding, isSubmittingNode, isDeletingNode,
  startEdit, startAdd, cancelEdit, addRelated, removeRelated, submitForm, deleteNode
} = useNodeForm(apiBase, currentUser, {
  selectedNode,
  isPanelOpen,
  fetchGraphData,
  fetchUserInfo,
  getNetwork,
  getNodesData,
  applyFilters
}, showToast)

// Patch lazy references now that all composables are initialized
graphCallbacks.cancelEdit = cancelEdit
graphCallbacks.applyFilters = applyFilters
graphCallbacks.activeFilters = activeFilters
graphCallbacks.isEditing = isEditing
graphCallbacks.isAdding = isAdding

// Image Cropping
const {
  showCropModal, cropCanvas,
  handleImageUpload, handleCropMouseDown, handleCropMouseMove,
  handleCropMouseUp, handleCropWheel, confirmCrop, cancelCrop
} = useImageCropper(editForm)

// Famous Applications
const {
  pendingApplications, showPendingApplicationsModal,
  isTogglingFamous, processingApplicationId,
  toggleFamousStatus, processApplication
} = useFamousApplications(apiBase, currentUser, getNodesData, selectedNode, showToast)

// --- UI state ---
const showSiteInfo = ref(false)
const showGuideModal = ref(false)

const toggleSiteInfo = (e) => {
  if (e) e.stopPropagation()
  showSiteInfo.value = !showSiteInfo.value
}

const closePopups = () => {
  showHistory.value = false
  showSiteInfo.value = false
}

const closeGuide = () => {
  showGuideModal.value = false
  localStorage.setItem('guide_seen', 'true')
}

const openGuide = () => {
  showGuideModal.value = true
}

const globalClickHandler = (e) => {
  isDropdownOpen.value = false
  closePopups()
  handleClickRipple(e)
}

// --- Lifecycle ---
onMounted(async () => {
  await initAuthFromUrl()
  await fetchGraphData()
  initNetwork()
  await fetchMailbox()

  if (!localStorage.getItem('guide_seen')) {
    setTimeout(() => {
      showGuideModal.value = true
    }, 1500)
  }

  window.addEventListener('click', globalClickHandler)
  window.addEventListener('mousemove', handleMouseMove)
})

onUnmounted(() => {
  if (toastTimer) clearTimeout(toastTimer)
  window.removeEventListener('click', globalClickHandler)
  window.removeEventListener('mousemove', handleMouseMove)
})
</script>

<template>
  <div class="app-container" :class="{ 'light-mode': !isDarkMode }">
    <!-- Mouse Effects -->
    <div v-for="ripple in ripples" :key="ripple.id" 
         class="click-ripple" 
         :class="ripple.type"
         :style="{ left: ripple.x + 'px', top: ripple.y + 'px' }">
    </div>

    <!-- Loading Animation -->
    <div v-if="loading" class="loading-overlay">
      <div class="loader"></div>
      <p>正在加载千早爱音宇宙...</p>
    </div>

    <!-- UI Buttons -->
    <Toolbar 
      v-model:showFamous="showFamous"
      v-model:showNewNodes="showNewNodes"
      :isDarkMode="isDarkMode"
      :currentUser="currentUser"
      :unprocessedMailCount="unprocessedMailCount"
      @resetView="resetView"
      @toggleHistory="toggleHistory()"
      @toggleDarkMode="toggleDarkMode"
      @openGuide="openGuide"
      @openMailbox="openMailbox"
    />

    <UserAccount 
      :currentUser="currentUser"
      :isDropdownOpen="isDropdownOpen"
      @toggleDropdown="toggleDropdown"
      @loginWithBangumi="loginWithBangumi"
      @logout="logout"
    />

    <div class="ui-layer bottom-left" :class="{ 'panel-up': showSiteInfo }">
      <SearchBox 
        v-model:searchQuery="searchQuery"
        :searchResults="searchResults"
        :activeFilters="activeFilters"
        @handleSearch="handleSearch"
        @selectSearchResult="selectSearchResult"
        @removeFilter="removeFilter"
      />
    </div>

    <div class="ui-layer bottom-right" :class="{ 'panel-up': showSiteInfo }">
      <button class="info-btn pink-btn" @click.stop="toggleSiteInfo">网站信息</button>
    </div>

    <div 
      ref="vizContainer" 
      class="graph-container" 
      :class="{ 'shifted': isPanelOpen }"
    ></div>

    <!-- Right Panel -->
    <NodeSidePanel
      :isPanelOpen="isPanelOpen"
      :isEditing="isEditing"
      :isAdding="isAdding"
      :isSubmittingNode="isSubmittingNode"
      :isDeletingNode="isDeletingNode"
      :isSavingPosition="isSavingPosition"
      :isTogglingFamous="isTogglingFamous"
      :isUpdatingConnection="isUpdatingConnection"
      :selectedNode="selectedNode"
      :editForm="editForm"
      :apiBase="apiBase"
      :currentUser="currentUser"
      :canEditSelectedNode="canEditSelectedNode"
      :canAddNode="canAddNode"
      :canEditConnections="canEditConnections"
      :canDeleteSelectedNode="canDeleteSelectedNode"
      :deleteDisabledReason="deleteDisabledReason"
      :connectionEditDisabledReason="connectionEditDisabledReason"
      :isConnectionEditMode="isConnectionEditMode"
      @close="isPanelOpen = false"
      @toggleHistory="toggleHistory"
      @startEdit="startEdit"
      @startAdd="startAdd"
      @cancelEdit="cancelEdit"
      @submitForm="submitForm"
      @deleteNode="deleteNode"
      @saveNodePosition="saveNodePosition"
      @toggleFamousStatus="toggleFamousStatus"
      @toggleConnectionEditMode="toggleConnectionEditMode"
      @addRelated="addRelated"
      @removeRelated="removeRelated"
      @imageUpload="handleImageUpload"
    />

    <!-- Modals -->
    <HistoryModal 
      v-if="showHistory"
      :showHistory="showHistory"
      :historyData="historyData"
      :historyType="historyType"
      :isHistoryLoading="isHistoryLoading"
      @close="showHistory = false"
      @focusNode="(id) => { focusNode(id); showHistory = false }"
    />

    <GuideModal :show="showGuideModal" @close="closeGuide" />
    <SiteInfoPanel :show="showSiteInfo" />

    <NotificationModal
      :show="showNotificationModal"
      :notifiedMails="notifiedMails"
      @close="showNotificationModal = false"
    />

    <MailboxModal
      :show="showMailboxModal"
      :isDarkMode="isDarkMode"
      :mailboxMessages="mailboxMessages"
      :canSendMessage="canSendMessage"
      :currentUser="currentUser"
      @close="showMailboxModal = false"
      @openNewMessage="showNewMessageModal = true"
      @processMessage="handleProcessMessage"
    />

    <NewMessageModal
      :show="showNewMessageModal"
      :isDarkMode="isDarkMode"
      :isSubmitting="isSendingMessage"
      v-model="newMessageContent"
      @close="showNewMessageModal = false"
      @submit="submitMailboxMessage"
    />

    <FeedbackModal
      :show="showFeedbackModal"
      :isDarkMode="isDarkMode"
      v-model="feedbackContent"
      :isSubmitting="isSubmittingFeedback"
      :actionLabel="processingAction === 'process' ? '处理' : '拒绝'"
      @close="showFeedbackModal = false"
      @submit="submitFeedback"
    />

    <PendingApplicationsModal
      :show="showPendingApplicationsModal"
      :pendingApplications="pendingApplications"
      :processingApplicationId="processingApplicationId"
      @close="showPendingApplicationsModal = false"
      @approve="(id) => processApplication(id, 'approve')"
      @reject="(id) => processApplication(id, 'reject')"
      @focusNode="focusNode"
    />

    <!-- Crop Modal -->
    <div v-if="showCropModal" class="crop-modal-overlay">
      <div class="crop-modal">
        <h3>裁剪图片</h3>
        <p class="crop-tip">滚轮缩放，左键拖动</p>
        <div
          class="canvas-container"
          @mousedown="handleCropMouseDown"
          @mousemove="handleCropMouseMove"
          @mouseup="handleCropMouseUp"
          @mouseleave="handleCropMouseUp"
          @wheel="handleCropWheel"
        >
          <canvas ref="cropCanvas"></canvas>
        </div>
        <div class="crop-actions">
          <button class="btn confirm" @click="confirmCrop">确认</button>
          <button class="btn cancel" @click="cancelCrop">取消</button>
        </div>
      </div>
    </div>

    <Transition name="toast-fade">
      <div v-if="toastState.visible" class="app-toast" :class="toastState.type">
        {{ toastState.message }}
      </div>
    </Transition>
  </div>
</template>
