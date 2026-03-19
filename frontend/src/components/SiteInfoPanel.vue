<script setup>
defineProps({
  show: Boolean
})
</script>

<template>
  <Transition name="slide-up">
    <div v-if="show" class="site-info-panel" @click.stop>
      <div class="site-info-grid">
        <div class="info-section">
          <h4>开发者&站长</h4>
          <a href="https://space.bilibili.com/365169149" target="_blank" class="info-link">空之堇</a>
        </div>
        <div class="info-section">
          <h4>特别鸣谢</h4>
          <a href="https://space.bilibili.com/3493081661836152" target="_blank" class="info-link">璀璨水晶Crystal</a>
        </div>
        <div class="info-section">
          <h4>Github仓库</h4>
          <a href="https://github.com/Node000/AnonUniverse" target="_blank" class="info-link">AnonUniverse</a>
        </div>
      </div>
    </div>
  </Transition>
</template>
