<script setup>
import { RouterLink } from 'vue-router'
import { House, ChatDotRound, Plus, User } from '@element-plus/icons-vue'
import FloatingDonkey from '@/components/FloatingDonkey.vue'
import { onMounted, onUnmounted, watch } from 'vue'
import { useNotificationStore } from '@/stores/modules/notifications'
import { useUserStore } from '@/stores/modules/user'

const notifications = useNotificationStore()
let poll
const refreshInbox = () => {
  if (!document.hidden) notifications.refresh()
}
onMounted(() => {
  refreshInbox()
  poll = setInterval(refreshInbox, 60000)
  document.addEventListener('visibilitychange', refreshInbox)
})
onUnmounted(() => {
  clearInterval(poll)
  document.removeEventListener('visibilitychange', refreshInbox)
})
watch(
  () => useUserStore().token,
  () => {
    notifications.unread = 0
    notifications.refresh()
  }
)
defineProps({
  activeBtn: {
    type: Number,
    default: 1
  }
})
</script>

<template>
  <nav class="foot" aria-label="底部导航">
    <FloatingDonkey />
    <RouterLink
      to="/index"
      class="foot-box"
      :class="{ active: activeBtn === 1 }"
    >
      <div class="foot-view">
        <el-icon><House /></el-icon>
      </div>
      <div class="foot-text">首页</div>
    </RouterLink>
    <RouterLink class="foot-box" to="/blogEdit" aria-label="发布探店">
      <span class="publish-icon"
        ><el-icon><Plus /></el-icon
      ></span>
    </RouterLink>
    <RouterLink
      to="/messages"
      class="foot-box"
      :class="{ active: activeBtn === 3 }"
    >
      <div class="foot-view">
        <el-icon><ChatDotRound /></el-icon>
        <span v-if="notifications.unread" class="unread-badge">{{
          notifications.unread > 99 ? '99+' : notifications.unread
        }}</span>
      </div>
      <div class="foot-text">消息</div>
    </RouterLink>
    <RouterLink
      to="/InfoHtml"
      class="foot-box"
      :class="{ active: activeBtn === 4 }"
    >
      <div class="foot-view">
        <el-icon><User /></el-icon>
      </div>
      <div class="foot-text">我的</div>
    </RouterLink>
  </nav>
</template>

<style scoped>
.publish-icon {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  color: white;
  background: var(--tp-ink);
  border-radius: 50%;
}
.foot {
  flex-shrink: 0;
  isolation: isolate;
}
.foot-box {
  display: flex;
  height: 100%;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  text-decoration: none;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.foot-box:focus-visible {
  outline: 2px solid var(--tp-ink);
  outline-offset: -4px;
}
.unread-badge {
  position: absolute;
  top: -7px;
  left: 16px;
  min-width: 16px;
  padding: 2px 4px;
  border-radius: 10px;
  background: var(--tp-ink);
  color: white;
  font-size: 9px;
  line-height: 1.2;
  border: 2px solid white;
}
.foot-view :deep(.el-icon) {
  font-size: 22px;
}
</style>
