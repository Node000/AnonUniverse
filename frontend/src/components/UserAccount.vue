<script setup>
import { ref } from 'vue'

const props = defineProps({
  currentUser: Object,
  isDropdownOpen: Boolean
})

const emit = defineEmits(['toggleDropdown', 'loginWithBangumi', 'logout'])
</script>

<template>
  <div class="ui-layer top-right">
    <div class="header-controls">
      <div 
        class="user-status" 
        :class="[currentUser.logged_in ? 'login-active' : 'login-guest', isDropdownOpen ? 'dropdown-active' : '', currentUser.role]" 
        @click.stop="$emit('toggleDropdown')"
      >
        {{ currentUser.logged_in ? `已登录：${currentUser.nickname}` : '未登录' }}
        <Transition name="fade">
          <div class="user-dropdown" v-if="isDropdownOpen" @click.stop>
            <template v-if="!currentUser.logged_in">
              <button 
                class="login-action-btn" 
                @click="$emit('loginWithBangumi')"
                title="使用 Bangumi 账号授权登录以获得更多权限"
              >使用 Bangumi 账号登录</button>
            </template>
            <template v-else>
              <div class="user-role-badge" :class="currentUser.role">
                {{ currentUser.role === 'admin' ? '管理员' : (currentUser.role === 'banned' ? '已封禁' : '普通用户') }}
              </div>
              <div class="quota-info">
                <div class="quota-item">
                  <span>新增</span>
                  <span class="quota-num">{{ currentUser.role === 'admin' ? '∞' : (currentUser.role === 'banned' ? '✕' : (10 - currentUser.quota.adds)) }}</span>
                </div>
                <div class="quota-item">
                  <span>修改</span>
                  <span class="quota-num">{{ currentUser.role === 'admin' ? '∞' : (currentUser.role === 'banned' ? '✕' : (10 - currentUser.quota.edits)) }}</span>
                </div>
                <div class="quota-item">
                  <span>删除</span>
                  <span class="quota-num">{{ currentUser.role === 'admin' ? '∞' : (currentUser.role === 'banned' ? '✕' : (1 - currentUser.quota.deletes)) }}</span>
                </div>
                <div class="quota-item">
                  <span>信件</span>
                  <span class="quota-num">{{ currentUser.role === 'admin' ? '∞' : (currentUser.role === 'banned' ? '✕' : (3 - (currentUser.quota.messages || 0))) }}</span>
                </div>
              </div>
              <button @click="$emit('logout')" class="logout-btn">退出登录</button>
            </template>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>
