<script setup>
defineProps({
  show: Boolean,
  cropCanvas: Object
})

const emit = defineEmits([
  'confirm', 'cancel',
  'mousedown', 'mousemove', 'mouseup', 'wheel'
])
</script>

<template>
  <div v-if="show" class="crop-modal-overlay">
    <div class="crop-modal">
      <h3>裁剪图片</h3>
      <p class="crop-tip">滚轮缩放，左键拖动</p>
      <div
        class="canvas-container"
        @mousedown="$emit('mousedown', $event)"
        @mousemove="$emit('mousemove', $event)"
        @mouseup="$emit('mouseup')"
        @mouseleave="$emit('mouseup')"
        @wheel="$emit('wheel', $event)"
      >
        <canvas ref="canvasEl"></canvas>
      </div>
      <div class="crop-actions">
        <button class="btn confirm" @click="$emit('confirm')">确认</button>
        <button class="btn cancel" @click="$emit('cancel')">取消</button>
      </div>
    </div>
  </div>
</template>
