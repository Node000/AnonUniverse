<script setup>
defineProps({
  show: Boolean
})

const emit = defineEmits(['close'])
</script>

<template>
  <Transition name="fade">
    <div v-if="show" class="modal-overlay" @click="$emit('close')">
      <div class="guide-modal" @click.stop style="background: #1a1a2e; border: 2px solid #ff69b4; border-radius: 15px; width: 450px; max-width: 90vw; padding: 30px; box-shadow: 0 0 30px rgba(255, 105, 180, 0.4);">
        <h2 style="color: #ff69b4; text-align: center; margin-bottom: 25px; font-size: 1.5rem;">千早爱音宇宙漫游指南</h2>
        <div style="color: #eee; line-height: 1.8; font-size: 0.95rem;">
          <p>1. 本站用于记录千早爱音在中文互联网的各种形象，侵权即删。</p>
          <p>2. 点击节点可以查看该形象的详细信息。</p>
          <p>3. 用户在登录后，每日可以进行10次新增、10次修改、1次删除与3次信件投递</p>
          <p>4. "知名二创"需满足以下标准：</p>
          <p>①该形象作品为剧情性二创</p>
          <p>②B站单作品播放量20w+或系列播放量50w+/NGA楼层2k+/LOFTER单作品热度2k+</p>
          <p>5. 普通用户也可直接增删连线，每次会消耗1次修改次数；如有知名二创申请或大范围节点调整需求，请通过信箱联系管理员。</p>
          <p>6. 若想担任本站管理员，请通过B站私信联系本站站长。</p>
          <p>7. 欢迎各位观众与作者对本网站的内容进行更新！</p>
        </div>
        <div style="display: flex; justify-content: center; margin-top: 30px;">
          <button class="btn confirm" style="padding: 10px 40px; font-size: 1rem;" @click="$emit('close')">出发！</button>
        </div>
      </div>
    </div>
  </Transition>
</template>
