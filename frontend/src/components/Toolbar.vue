<script setup>
import { ref } from 'vue'

const props = defineProps({
  showFamous: Boolean,
  showNewNodes: Boolean,
  isDarkMode: Boolean,
  currentUser: Object,
  unprocessedMailCount: Number,
  apiBase: String
})

const emit = defineEmits([
  'resetView', 'toggleHistory', 'toggleDarkMode', 'openGuide', 
  'update:showFamous', 'update:showNewNodes', 'openMailbox',
  'login', 'logout', 'toggleDropdown', 'isDropdownOpen'
])
// Internal dropdown state or emit toggle
</script>

<template>
  <div>
    <!-- Logic from App.vue for the Buttons -->
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
        <div class="left-controls-row2" style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button 
            class="famous-toggle-btn" 
            :class="{ active: showFamous }" 
            @click="$emit('update:showFamous', !showFamous)"
          >
            知名二创显示
          </button>
          <button 
            class="newnode-toggle-btn" 
            :class="{ active: showNewNodes }" 
            @click="$emit('update:showNewNodes', !showNewNodes)"
          >
            最近新增显示
          </button>
          <button 
            v-if="currentUser.logged_in"
            class="mailbox-btn" 
            :class="{ 'has-unread': currentUser.role === 'admin' && unprocessedMailCount > 0 }"
            @click="$emit('openMailbox')"
          >
            {{ currentUser.role === 'admin' ? `信箱：${unprocessedMailCount}` : '信箱' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
