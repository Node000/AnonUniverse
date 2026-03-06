<script setup>
import { computed } from 'vue'

const props = defineProps({
  currentUser: Object,
  isDarkMode: Boolean
})

const emit = defineEmits(['toggleDarkMode', 'resetView', 'toggleHistory', 'openGuide', 'showFamous', 'showNewNodes', 'openMailbox', 'login', 'logout', 'toggleDropdown'])

const unprocessedMailCount = 0 // This logic needs to be passed in or handled

const userRoleLabel = computed(() => {
  if (!props.currentUser) return '未登录'
  return props.currentUser.role === 'admin' ? '管理员' : '普通用户'
})
</script>

<template>
  <!-- UI Buttons -->
  <div class="ui-layer top-left">
      <div class="left-controls-container" style="display: flex; flex-direction: column; gap: 10px;">
        <div class="left-controls">
          <button class="home-btn pink-btn" @click="$emit('resetView')">回到中心</button>
          <button class="history-btn pink-btn" @click.stop="$emit('toggleHistory')">全站历史</button>
          <button class="theme-toggle" @click="$emit('toggleDarkMode')" :class="{ 'dark-mode-btn': isDarkMode }">
            <svg v-if="!isDarkMode" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="5" />
              <path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M17.66 6.34l1.42-1.42" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
            </svg>
          </button>
          <button class="guide-toggle" @click.stop="$emit('openGuide')" title="查看漫游指南">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
          </button>
        </div>
        <!-- ... other rows ... -->
      </div>
    </div>
</template>
