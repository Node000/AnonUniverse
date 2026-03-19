<script setup>
import { ref, reactive } from 'vue'

const props = defineProps({
  isPanelOpen: Boolean,
  isEditing: Boolean,
  isAdding: Boolean,
  selectedNode: Object,
  editForm: Object,
  apiBase: String,
  currentUser: Object,
  canEditSelectedNode: Boolean,
  canAddNode: Boolean,
  canDeleteSelectedNode: Boolean,
  deleteDisabledReason: String,
  isConnectionEditMode: Boolean
})

const emit = defineEmits([
  'close', 'toggleHistory', 'startEdit', 'startAdd', 'cancelEdit',
  'submitForm', 'deleteNode', 'saveNodePosition', 'toggleFamousStatus',
  'toggleConnectionEditMode', 'addRelated', 'removeRelated',
  'imageUpload'
])

const fileInput = ref(null)
const panelContent = ref(null)
const panelState = reactive({ isDragging: false, startY: 0, scrollStart: 0 })

const handlePanelMouseDown = (e) => {
  panelState.isDragging = true
  panelState.startY = e.pageY - panelContent.value.offsetTop
  panelState.scrollStart = panelContent.value.scrollTop
}

const handlePanelMouseMove = (e) => {
  if (!panelState.isDragging) return
  e.preventDefault()
  const y = e.pageY - panelContent.value.offsetTop
  const walk = (y - panelState.startY) * 1.5
  panelContent.value.scrollTop = panelState.scrollStart - walk
}

const handlePanelMouseUp = () => {
  panelState.isDragging = false
}

const triggerFileInput = () => {
  fileInput.value.click()
}

const onFileChange = (e) => {
  emit('imageUpload', e)
}

defineExpose({ fileInput })
</script>

<template>
  <Transition name="slide">
    <div v-if="isPanelOpen" class="side-panel">
      <div
        class="panel-content"
        ref="panelContent"
        @mousedown="handlePanelMouseDown"
        @mousemove="handlePanelMouseMove"
        @mouseup="handlePanelMouseUp"
        @mouseleave="handlePanelMouseUp"
      >
        <!-- Node History Button -->
        <button
          v-if="!isEditing && !isAdding"
          class="node-update-history-btn-round"
          title="更新记录"
          @click.stop="$emit('toggleHistory', selectedNode.id)"
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>

        <!-- View Mode -->
        <template v-if="!isEditing && !isAdding && selectedNode">
          <button class="panel-inner-close-btn" @click="$emit('close')" title="关闭面板">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>

          <div class="image-container">
            <img
              :src="selectedNode.image ? (selectedNode.image.startsWith('http') ? selectedNode.image : `${apiBase}${selectedNode.image}`) : `${apiBase}/images/default.webp`"
              :alt="selectedNode.name"
              :onerror="`this.src='${apiBase}/images/default.webp'`"
            >
          </div>

          <h2 class="node-name">
            <span v-if="selectedNode.is_famous" title="已认证知名二创" style="color: #ff69b4; margin-right: 5px; cursor: help;">★</span>
            {{ selectedNode.name }}
          </h2>

          <div class="info-item">
            <label>出处：</label>
            <div style="display: inline-flex; align-items: center; gap: 8px;">
              <a v-if="selectedNode.source.link" :href="selectedNode.source.link" target="_blank" class="info-link">{{ selectedNode.source.name }}</a>
              <span v-else>{{ selectedNode.source.name }}</span>
              <span v-if="selectedNode.source.type" class="res-type" style="font-size: 10px; padding: 1px 4px; margin: 0;">{{ selectedNode.source.type }}</span>
            </div>
          </div>

          <div class="info-item" v-if="selectedNode.introduction">
            <label>介绍：</label>
            <span class="info-intro">{{ selectedNode.introduction }}</span>
          </div>

          <div class="info-item" v-if="selectedNode.tags && selectedNode.tags.length > 0">
            <label>标签：</label>
            <div class="tag-list">
              <span v-for="tag in selectedNode.tags" :key="tag" class="tag">{{ tag }}</span>
            </div>
          </div>

          <div class="info-item" v-if="selectedNode.related && selectedNode.related.length > 0">
            <label>相关作品：</label>
            <div class="related-list">
              <div v-for="(item, idx) in selectedNode.related" :key="idx" class="related-item" style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <a v-if="item.link" :href="item.link" target="_blank" class="info-link">{{ item.name }}</a>
                <span v-else>{{ item.name }}</span>
                <span v-if="item.type" class="res-type" style="font-size: 10px; padding: 1px 4px; margin: 0;">{{ item.type }}</span>
              </div>
            </div>
          </div>

          <div class="action-buttons-container" style="display: flex; flex-direction: column; gap: 10px; margin-top: 20px;">
            <div class="action-buttons" style="margin-top: 0;">
              <button
                class="btn edit"
                :disabled="!canEditSelectedNode"
                :title="!canEditSelectedNode ? '今日修改配额已用完' : ''"
                @click="$emit('startEdit')"
              >修改</button>
              <button
                class="btn add"
                :disabled="!canAddNode"
                :title="!canAddNode ? '今日新增配额已用完' : ''"
                @click="$emit('startAdd')"
              >新增</button>
              <button
                class="btn delete"
                :class="{ 'disabled-btn': !canDeleteSelectedNode }"
                :disabled="!canDeleteSelectedNode"
                @click="$emit('deleteNode')"
                :title="deleteDisabledReason"
              >删除</button>
            </div>
            <div class="action-buttons" v-if="currentUser.role === 'admin'" style="margin-top: 0;">
              <button
                class="btn save-pos"
                @click="$emit('saveNodePosition')"
                title="保存当前节点位置"
              >保存位置</button>
              <button
                class="btn famous-toggle"
                @click="$emit('toggleFamousStatus')"
                title="切换知名二创状态"
                style="background: #87CEEB;"
              >{{ selectedNode.is_famous ? '取消知名' : '设为知名' }}</button>
              <button
                class="btn connection-toggle"
                @click="$emit('toggleConnectionEditMode')"
                title="点击图中节点以增删连线"
                :style="{ background: isConnectionEditMode ? '#ff6b6b' : '#9c88ff' }"
              >{{ isConnectionEditMode ? '停止连线' : '增删连线' }}</button>
            </div>
          </div>
        </template>

        <!-- Edit/Add Mode -->
        <template v-else>
          <h2 class="node-name">{{ isAdding ? '新增形象' : '修改形象' }}</h2>

          <div class="image-container editable" @click="triggerFileInput">
            <template v-if="editForm.imagePreview">
              <img :src="editForm.imagePreview">
              <div class="hover-mask">
                <span>上传图片</span>
              </div>
            </template>
            <div v-else class="upload-placeholder">
              <span>暂无图片</span>
              <small>点击上传</small>
            </div>
            <input type="file" ref="fileInput" hidden @change="onFileChange" accept="image/*">
          </div>

          <div class="input-group">
            <label>形象名字</label>
            <input v-model="editForm.name" placeholder="名字">
          </div>

          <div class="input-group">
            <label>出处</label>
            <div class="pair-input-row">
              <div class="pair-input">
                <input v-model="editForm.source.name" placeholder="作品名字">
                <input v-model="editForm.source.link" placeholder="链接 (可选)">
                <select v-model="editForm.source.type" class="type-select">
                  <option>小说</option>
                  <option>视频</option>
                  <option>插画</option>
                  <option>漫画</option>
                  <option>游戏</option>
                  <option>其他</option>
                </select>
              </div>
            </div>
          </div>

          <div class="input-group">
            <label>介绍</label>
            <textarea v-model="editForm.introduction" placeholder="简单介绍一下这个版本/形象..." rows="3"></textarea>
          </div>

          <div class="input-group">
            <label>标签 (逗号分隔)</label>
            <input v-model="editForm.tags" placeholder="标签1, 标签2">
          </div>

          <div class="input-group">
            <label>相关作品</label>
            <div v-for="(item, index) in editForm.related" :key="index" class="pair-input-row">
              <div class="pair-input">
                <input v-model="item.name" placeholder="名字" style="flex: 1.5; min-width: 80px;">
                <input v-model="item.link" placeholder="链接 (可选)" style="flex: 2; min-width: 100px;">
                <select v-model="item.type" class="type-select">
                  <option>小说</option>
                  <option>视频</option>
                  <option>插画</option>
                  <option>漫画</option>
                  <option>游戏</option>
                  <option>其他</option>
                </select>
              </div>
              <button class="remove-btn" @click="$emit('removeRelated', index)" title="删除此项">×</button>
            </div>
            <button class="add-btn" @click="$emit('addRelated')">+ 添加作品</button>
          </div>

          <div class="form-actions">
            <button class="btn confirm" @click="$emit('submitForm')">确认</button>
            <button class="btn cancel" @click="$emit('cancelEdit')">取消</button>
          </div>
        </template>
      </div>
    </div>
  </Transition>
</template>
