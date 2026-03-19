<script setup>
defineProps({
  show: Boolean,
  isDarkMode: Boolean,
  mailboxMessages: Array,
  canSendMessage: Boolean,
  currentUser: Object
})

const emit = defineEmits(['close', 'openNewMessage', 'processMessage', 'rejectMessage', 'shouldShowExpand'])

const shouldShowExpand = (msg) => {
  if (!msg.content) return false
  const lines = msg.content.split('\n').length
  if (lines > 2) return true
  if (msg.content.length > 60) return true
  return false
}
</script>

<template>
  <div v-if="show" class="modal-overlay" @click="$emit('close')">
    <div class="mailbox-modal" @click.stop :class="{ 'light-mode': !isDarkMode }">
      <div class="modal-header" style="position: relative;">
        <h3 style="width: 100%; text-align: center;">信箱</h3>
        <button class="close-btn" @click="$emit('close')" style="position: absolute; right: 15px; top: 15px; color: #ff69b4; background: none; border: none; font-size: 24px; cursor: pointer; line-height: 1;">&times;</button>
      </div>
      <div class="mailbox-content">
        <div class="mailbox-add-btn-wrapper">
          <button
            class="mailbox-add-btn-large"
            @click="$emit('openNewMessage')"
            :disabled="!canSendMessage"
            :title="!canSendMessage ? '今日信件配额已用完' : ''"
            :style="{ opacity: canSendMessage ? 1 : 0.5, cursor: canSendMessage ? 'pointer' : 'not-allowed' }"
          >
            <span>{{ canSendMessage ? '+ 投递新信件' : '今日投递配额已用完' }}</span>
          </button>
        </div>
        <div v-if="mailboxMessages.length === 0" class="no-messages">暂无信件</div>
        <div v-for="msg in mailboxMessages" :key="msg.id" class="mailbox-item" :class="msg.status">
          <div class="msg-main">
            <div class="msg-header">
              <span class="msg-user">{{ msg.nickname }}</span>
              <span class="msg-time">{{ msg.time }}</span>
            </div>
            <div class="msg-body">
              <div
                class="msg-body-inner"
                :class="{ 'expanded': msg.isExpanded }"
                :id="'msg-content-' + msg.id"
              >
                {{ msg.content }}
              </div>
              <div
                v-if="shouldShowExpand(msg)"
                class="expand-toggle"
                @click.stop="msg.isExpanded = !msg.isExpanded"
              >
                {{ msg.isExpanded ? '收起' : '展开全文' }}
              </div>
            </div>
          </div>
          <div class="msg-status">
            <template v-if="msg.status === 'unprocessed'">
              <div v-if="currentUser.role === 'admin'" style="display: flex; gap: 5px;">
                <button class="process-btn" @click="$emit('processMessage', msg.id, 'process')">处理</button>
                <button class="reject-btn" @click="$emit('processMessage', msg.id, 'reject')" style="background: #ff4d4f; border: none; color: white; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px;">拒绝</button>
              </div>
              <span v-else class="status-text unprocessed">未处理</span>
            </template>
            <template v-else>
              <div class="status-info">
                <span>{{ msg.status === 'processed' ? '已处理' : '拒绝' }}</span>
                <span class="feedback-info" style="color: #ff69b4;">
                  反馈：{{ msg.feedback || '无' }}
                </span>
                <span>处理人：{{ msg.processed_by }}</span>
                <span>时间：{{ msg.processed_time }}</span>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
