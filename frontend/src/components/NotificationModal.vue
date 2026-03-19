<script setup>
defineProps({
  show: Boolean,
  notifiedMails: Array
})

const emit = defineEmits(['close'])
</script>

<template>
  <Transition name="fade">
    <div v-if="show" class="modal-overlay" @click="$emit('close')">
      <div class="modal-content notification-modal" @click.stop style="background: #1a1a2e; border: 2px solid #ff69b4; border-radius: 15px; width: 450px; max-width: 90vw; padding: 25px; box-shadow: 0 0 30px rgba(255, 105, 180, 0.4);">
        <h2 style="color: #ff69b4; text-align: center; margin-bottom: 20px;">有新的信件反馈！</h2>
        <div class="notification-list" style="max-height: 450px; overflow-y: auto; padding-right: 5px;">
          <div v-for="mail in notifiedMails" :key="mail.id" class="notified-mail-item" style="border-bottom: 1px dashed rgba(255,105,180,0.3); padding: 15px 0;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
              <span style="color: #888; font-size: 0.8rem;">{{ mail.time }}</span>
              <span :style="{ color: mail.status === 'processed' ? '#50e3c2' : '#ff4d4f', fontSize: '0.9rem', fontWeight: 'bold' }">
                {{ mail.status === 'processed' ? '已处理' : '已拒绝' }}
              </span>
            </div>
            <div style="color: #eee; margin-bottom: 10px; font-size: 0.95rem; line-height: 1.4; background: rgba(255,255,255,0.05); padding: 8px; border-radius: 5px; white-space: pre-wrap; word-break: break-all;">
              {{ mail.content }}
            </div>
            <div style="display: flex; flex-direction: column; gap: 4px;">
              <div style="color: #ff69b4; font-size: 0.9rem; white-space: pre-wrap;">反馈：{{ mail.feedback }}</div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
                <span style="color: #666; font-size: 0.75rem;">处理时间：{{ mail.processed_time || mail.time }}</span>
                <span style="color: #00ffff; font-size: 0.8rem;">处理人：{{ mail.processed_by }}</span>
              </div>
            </div>
          </div>
        </div>
        <button @click="$emit('close')" class="pink-btn" style="width: 100%; margin-top: 20px; padding: 10px; border-radius: 20px; font-weight: bold;">我知道了</button>
      </div>
    </div>
  </Transition>
</template>
