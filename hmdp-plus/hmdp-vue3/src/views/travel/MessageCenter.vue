<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, ArrowRight, Check, Compass } from '@element-plus/icons-vue'
import FootBar from '@/components/FootBar.vue'
import {
  listNotifications,
  readNotification,
  readAllNotifications
} from '@/api/travel'
import { useNotificationStore } from '@/stores/modules/notifications'
import { useUserStore } from '@/stores/modules/user'

const router = useRouter()
const notifications = useNotificationStore()
const items = ref([])
const unreadOnly = ref(false)
const busy = ref(false)
const error = ref('')
const page = ref(1)
const hasMore = ref(false)
const actionBusy = ref(false)
const emptyText = computed(() =>
  unreadOnly.value ? '未读消息都看完啦' : '下一次出发，从这里收到消息'
)
let generation = 0
async function load(append = false) {
  const current = ++generation
  busy.value = true
  error.value = ''
  const nextPage = append ? page.value + 1 : 1
  try {
    const result = await listNotifications({
      unread_only: unreadOnly.value,
      page: nextPage
    })
    if (current !== generation) return
    items.value = append ? [...items.value, ...result.items] : result.items
    page.value = nextPage
    hasMore.value = result.items.length === 20
    notifications.unread = result.unread_count
  } catch (e) {
    if (current === generation) error.value = e.message
  } finally {
    if (current === generation) busy.value = false
  }
}
async function open(item) {
  if (actionBusy.value) return
  actionBusy.value = true
  const account = useUserStore().token
  try {
    await readNotification(item.id)
    if (account !== useUserStore().token) return
    if (!item.is_read)
      notifications.unread = Math.max(0, notifications.unread - 1)
    item.is_read = true
    if (item.itinerary_id)
      router.push({
        path: '/travel/itineraries',
        query: { id: item.itinerary_id }
      })
    else if (unreadOnly.value) load()
  } catch (e) {
    error.value = e.message
  } finally {
    actionBusy.value = false
  }
}
async function markAll() {
  actionBusy.value = true
  const account = useUserStore().token
  try {
    await readAllNotifications()
    if (account === useUserStore().token) await load()
  } catch (e) {
    error.value = e.message
  } finally {
    actionBusy.value = false
  }
}
function date(value) {
  return new Date(value * 1000).toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}
watch(unreadOnly, () => load())
watch(
  () => useUserStore().token,
  () => {
    items.value = []
    notifications.unread = 0
    load()
  }
)
onMounted(() => load())
</script>

<template>
  <div class="inbox-page">
    <main class="inbox">
      <header>
        <span class="overline">TRIPPAL · INBOX</span>
        <h1>
          消息，慢慢看。<el-icon><Bell /></el-icon>
        </h1>
        <p>每一次小小的更新，都为下一次出发。</p>
      </header>
      <section class="inbox-summary">
        <span
          ><strong>{{ notifications.unread }}</strong> 条未读消息</span
        ><button
          :disabled="!notifications.unread || actionBusy || busy"
          @click="markAll"
        >
          <el-icon><Check /></el-icon>全部已读
        </button>
      </section>
      <nav aria-label="消息筛选">
        <button :class="{ selected: !unreadOnly }" @click="unreadOnly = false">
          全部消息</button
        ><button :class="{ selected: unreadOnly }" @click="unreadOnly = true">
          只看未读</button
        ><button class="refresh" :disabled="busy" @click="load()">刷新</button>
      </nav>
      <p v-if="error" class="error" role="alert">
        {{ error }} <button :disabled="busy" @click="load()">重试</button>
      </p>
      <p v-if="busy && !items.length" class="empty" role="status">
        正在打开信箱…
      </p>
      <section v-else-if="!items.length && !error" class="empty">
        <span class="empty-icon"
          ><el-icon><Compass /></el-icon
        ></span>
        <h2>{{ emptyText }}</h2>
        <p>保存或调整行程后，旅伴会把更新放进信箱。</p>
        <router-link to="/travel">和旅伴计划一次出游 →</router-link>
      </section>
      <div class="message-list" :aria-busy="busy">
        <button
          v-for="item in items"
          :key="item.id"
          class="notification"
          :class="{ unread: !item.is_read }"
          :disabled="actionBusy"
          @click="open(item)"
        >
          <span class="event-icon"
            ><el-icon><Compass /></el-icon></span
          ><span class="event-copy"
            ><span class="event-title"
              >{{ item.title
              }}<i v-if="!item.is_read" aria-label="未读"></i></span
            ><span class="body">{{ item.body }}</span
            ><time>{{ date(item.created) }}</time
            ><small v-if="!item.itinerary_id">关联行程已删除</small></span
          ><el-icon><ArrowRight /></el-icon>
        </button>
      </div>
      <button
        v-if="hasMore"
        class="load-more"
        :disabled="busy"
        @click="load(true)"
      >
        {{ busy ? '加载中…' : '再看看更早的消息' }}
      </button>
      <p class="scope-note">当前接收行程更新通知</p>
    </main>
    <FootBar :active-btn="3" />
  </div>
</template>

<style scoped>
.inbox-page {
  min-height: 100dvh;
  background: var(--tp-surface-soft);
  color: var(--tp-ink);
  padding: 36px 20px calc(max(8vh, 54px) + 24px);
  box-sizing: border-box;
}
.inbox {
  max-width: 780px;
  margin: auto;
}
header {
  padding: 12px 0 24px;
}
.overline {
  font-size: 10px;
  letter-spacing: 3px;
  color: var(--tp-muted);
}
h1 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 30px;
  letter-spacing: 1px;
  margin: 14px 0;
}
h1 .el-icon {
  color: var(--tp-muted);
  font-size: 28px;
}
header p {
  font-size: 13px;
  color: var(--tp-muted);
}
.inbox-summary {
  background: var(--tp-surface-soft);
  border: 1px solid var(--tp-line);
  border-radius: 18px;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}
.inbox-summary strong {
  font-size: 28px;
  margin-right: 8px;
}
button {
  font: inherit;
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
.inbox-summary button {
  display: flex;
  gap: 5px;
  align-items: center;
  border: 0;
  background: transparent;
  color: var(--tp-ink);
}
nav {
  display: flex;
  gap: 18px;
  border-bottom: 1px solid var(--tp-line);
  margin: 24px 0 16px;
}
nav button {
  background: transparent;
  color: var(--tp-muted);
  border: 0;
  padding: 10px 2px;
  font-size: 13px;
}
.selected {
  border-bottom: 2px solid var(--tp-line) !important;
  color: var(--tp-ink) !important;
  font-weight: 600;
}
.refresh {
  margin-left: auto;
}
.notification {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
  text-align: left;
  border: 1px solid var(--tp-line);
  background: #ffffffc9;
  border-radius: 18px;
  padding: 19px;
  margin: 10px 0;
  color: var(--tp-ink);
}
.notification.unread {
  border-color: var(--tp-line);
  background: #fff;
}
.notification:hover {
  border-color: var(--tp-line);
}
.event-icon,
.empty-icon {
  display: inline-flex;
  background: var(--tp-surface-soft);
  color: var(--tp-ink);
  padding: 12px;
  border-radius: 14px;
  font-size: 22px;
}
.event-copy {
  flex: 1;
  min-width: 0;
}
.event-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}
.event-title i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--tp-ink);
}
.body {
  display: block;
  font-size: 12px;
  color: var(--tp-ink);
  line-height: 1.8;
  margin: 7px 0;
  overflow-wrap: anywhere;
}
time,
.event-copy small {
  font-size: 10px;
  color: var(--tp-muted);
  display: block;
  margin-top: 3px;
}
.empty {
  text-align: center;
  padding: 58px 12px;
  color: var(--tp-muted);
}
.empty h2 {
  font-size: 17px;
  color: var(--tp-ink);
  margin-top: 22px;
}
.empty p {
  font-size: 12px;
  line-height: 1.8;
}
.empty a {
  display: inline-block;
  color: var(--tp-ink);
  text-decoration: none;
  margin-top: 14px;
  font-size: 13px;
}
.empty-icon {
  font-size: 38px;
  padding: 22px;
  border-radius: 24px;
  transform: rotate(-7deg);
}
.scope-note {
  font-size: 10px;
  text-align: center;
  color: var(--tp-muted);
  margin-top: 28px;
}
.load-more {
  display: block;
  margin: 20px auto;
  border: 1px solid var(--tp-line);
  background: white;
  border-radius: 20px;
  padding: 10px 20px;
  color: var(--tp-ink);
}
.error {
  background: #fff0e8;
  color: #a05834;
  border-radius: 10px;
  padding: 14px;
}
.inbox-page :deep(.foot .active) {
  color: var(--tp-ink);
}
button:focus-visible,
a:focus-visible {
  outline: 2px solid var(--tp-ink);
  outline-offset: 3px;
}
@media (max-width: 450px) {
  .inbox-page {
    padding-top: 20px;
  }
  h1 {
    font-size: 26px;
  }
  .notification {
    padding: 15px 12px;
    gap: 10px;
  }
}
</style>
