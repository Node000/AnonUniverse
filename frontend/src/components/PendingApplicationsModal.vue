<script setup>
defineProps({
  show: Boolean,
  pendingApplications: Array
})

const emit = defineEmits(['close', 'approve', 'reject', 'focusNode'])
</script>

<template>
  <div v-if="show" class="modal-overlay" @click="$emit('close')">
    <div class="pending-applications-modal" @click.stop style="background: #1a1a2e; border: 1px solid #ff69b4; border-radius: 10px; width: 90%; max-width: 500px; max-height: 80vh; display: flex; flex-direction: column;">
      <div class="modal-header" style="position: relative; display: flex; justify-content: center; align-items: center; padding: 15px 20px; border-bottom: 1px solid rgba(255, 105, 180, 0.3);">
        <h3 style="margin: 0; color: #ff69b4;">待认证申请</h3>
        <button class="close-btn" @click="$emit('close')" style="position: absolute; right: 15px; top: 50%; transform: translateY(-50%); color: #ff69b4; background: none; border: none; font-size: 24px; cursor: pointer;">×</button>
      </div>
      <div class="modal-body" style="padding: 20px; overflow-y: auto; flex: 1;">
        <div v-if="pendingApplications.length === 0" style="text-align: center; color: #888;">暂无申请</div>
        <div v-for="app in pendingApplications" :key="app.id" style="display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); gap: 10px;">
          <div style="flex: 1; word-break: break-all; color: #fff;">
            <span style="color: #50e3c2;">{{ app.nickname }}</span> 申请
            <span
              style="color: #ff69b4; cursor: pointer; text-decoration: underline;"
              @click="$emit('focusNode', app.node_id); $emit('close')"
            >{{ app.node_name }}</span>
            为<span style="color: #87CEEB;">知名二创</span>
          </div>
          <div style="display: flex; gap: 10px; flex-shrink: 0;">
            <button class="btn confirm" style="padding: 5px 10px; font-size: 12px;" @click="$emit('approve', app.id)">同意</button>
            <button class="btn delete" style="padding: 5px 10px; font-size: 12px;" @click="$emit('reject', app.id)">拒绝</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
