<script setup>
const props = defineProps({
  show: Boolean,
  isDarkMode: Boolean,
  modelValue: String
})

const emit = defineEmits(['close', 'submit', 'update:modelValue'])
</script>

<template>
  <div v-if="show" class="modal-overlay" @click="$emit('close')">
    <div class="new-message-modal" @click.stop :class="{ 'light-mode': !isDarkMode }">
      <div class="modal-header" style="position: relative;">
        <h3 style="width: 100%; text-align: center;">投递信件</h3>
        <button class="close-btn" @click="$emit('close')" style="position: absolute; right: 10px; top: 10px; background: none; border: none; color: inherit; font-size: 20px; cursor: pointer;">&times;</button>
      </div>
      <div class="modal-body">
        <textarea
          :value="modelValue"
          @input="$emit('update:modelValue', $event.target.value)"
          placeholder="请输入信件内容（最多200字）"
          maxlength="200"
        ></textarea>
        <div class="char-count">{{ (modelValue || '').length }}/200</div>
      </div>
      <div class="modal-footer" style="display: flex; justify-content: center; gap: 30px; padding: 15px 30px;">
        <button class="btn confirm" @click="$emit('submit')">确认</button>
        <button class="btn cancel" @click="$emit('close')">取消</button>
      </div>
    </div>
  </div>
</template>
