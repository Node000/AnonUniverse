<script setup>
import { computed } from 'vue'

const props = defineProps({
  showHistory: Boolean,
  historyData: Array,
  historyType: String,
  isHistoryLoading: Boolean
})

const emit = defineEmits(['close', 'switchType', 'focusNode'])

const historyTitle = computed(() => {
  return props.historyType === 'global' ? '全站历史记录' : '修改记录'
})
</script>

<template>
  <Transition name="fade">
    <div v-if="showHistory" class="modal-overlay" @click="$emit('close')">
      <div class="modal-content history-modal" @click.stop>
        <div class="modal-header">
          <h3>{{ historyTitle }}</h3>
          <button class="close-btn" @click="$emit('close')">×</button>
        </div>
        <div class="history-list">
          <div v-if="isHistoryLoading" class="loading-spinner">
            <div class="mini-loader"></div>
            <span>加载中...</span>
          </div>
          <template v-else>
            <div v-if="historyData.length === 0" class="no-history">暂无记录</div>
            <div v-for="(item, idx) in historyData" :key="idx" class="history-item">
              <span class="history-time">[{{ item.time }}]</span>
              <span class="history-user" :class="item.role">[{{ item.nickname }}]</span>
              
              <span v-if="item.action === 'apply_famous'"> 申请 </span>
              <span v-else-if="item.action === 'approve_famous'"> 同意了 </span>
              <span v-else-if="item.action === 'reject_famous'"> 拒绝了 </span>
              <span v-else> 进行了 </span>
              
              <span class="history-action" :class="item.action">
                {{ item.action === 'add' ? '新增' : item.action === 'edit' ? '修改' : item.action === 'delete' ? '删除' : '' }}
              </span>
              
              <span v-if="historyType === 'global' || item.action.includes('famous')">
                <span v-if="!item.action.includes('famous')"> 形象 </span>
                <span class="history-node-link" @click="$emit('focusNode', item.node_id)">
                  {{ item.node_name }}
                </span>
                <span v-if="item.action === 'apply_famous'"> 为<span style="color: #87CEEB;">知名二创</span> </span>
                <span v-if="item.action === 'approve_famous' || item.action === 'reject_famous'"> 的<span style="color: #87CEEB;">知名二创</span>申请 </span>
              </span>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px;
}
.mini-loader {
  width: 20px;
  height: 20px;
  border: 2px solid #ff69b4;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.no-history {
  text-align: center;
  padding: 20px;
  color: #888;
}
.history-node-link {
  color: #ff69b4;
  cursor: pointer;
  text-decoration: underline;
}
.history-node-link:hover {
  filter: brightness(1.2);
}
/* Ensure roles and actions are colored */
.admin { color: #87CEEB; }
.user { color: #ff69b4; }
.add { color: #22c55e; }
.edit { color: #ffd60a; }
.delete { color: #ff4d4f; }
</style>
