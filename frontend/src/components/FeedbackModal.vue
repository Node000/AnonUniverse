<script setup>
const props = defineProps({
  show: Boolean,
  isDarkMode: Boolean,
  modelValue: String,
  actionLabel: String,
  isSubmitting: Boolean
})

const emit = defineEmits(['close', 'submit', 'update:modelValue'])

const handleOverlayClick = () => {
  if (props.isSubmitting) return
  emit('close')
}

const handleClose = () => {
  if (props.isSubmitting) return
  emit('close')
}
</script>

<template>
  <div v-if="show" class="modal-overlay" @click="handleOverlayClick">
    <div class="new-message-modal" @click.stop :class="{ 'light-mode': !isDarkMode }">
      <div class="modal-header" style="position: relative;">
        <h3 style="width: 100%; text-align: center;">信件反馈 ({{ actionLabel }})</h3>
        <button class="close-btn" @click="handleClose" :disabled="isSubmitting" style="position: absolute; right: 10px; top: 10px; background: none; border: none; color: inherit; font-size: 20px; cursor: pointer;">&times;</button>
      </div>
      <div class="modal-body">
        <textarea
          :value="modelValue"
          @input="$emit('update:modelValue', $event.target.value)"
          placeholder="请输入反馈内容（最多30字，可选）"
          maxlength="30"
          :disabled="isSubmitting"
        ></textarea>
        <div class="char-count">{{ (modelValue || '').length }}/30</div>
      </div>
      <div class="modal-footer" style="display: flex; justify-content: center; gap: 30px; padding: 15px 30px;">
        <button class="btn confirm" @click="$emit('submit')" :disabled="isSubmitting">{{ isSubmitting ? '提交中...' : '确认' }}</button>
        <button class="btn cancel" @click="handleClose" :disabled="isSubmitting">取消</button>
      </div>
    </div>
  </div>
</template>
