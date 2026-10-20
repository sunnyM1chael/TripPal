<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Close,
  MagicStick,
  Plus,
  Promotion,
  RefreshRight,
  Shop,
  Tickets
} from '@element-plus/icons-vue'
import FootBar from '@/components/FootBar.vue'
import AgentRichText from '@/components/AgentRichText.vue'
import TravelResultCards from '@/components/TravelResultCards.vue'
import MapResultCards from '@/components/MapResultCards.vue'
import CityPicker from '@/components/CityPicker.vue'
import TravelMemoryPanel from '@/components/TravelMemoryPanel.vue'
import { useTravelStore } from '@/stores/modules/travel'
import { useUserStore } from '@/stores/modules/user'

const chat = useTravelStore()
const route = useRoute()
const router = useRouter()
const timeline = ref(null)
const input = ref(null)
const cityOpen = ref(false)
const memoryOpen = ref(false)
const memoryTab = ref('preferences')
const hasMessages = computed(() => chat.messages.length > 0)
const canSend = computed(
  () =>
    chat.draft.trim().length > 0 &&
    chat.draft.length <= 4000 &&
    !chat.pending &&
    !chat.busy
)
const suggestions = [
  {
    icon: Shop,
    title: '美食探索',
    subtitle: '按口味、人均预算找店',
    prompt:
      '想探索本地美食，人均100元以内，请结合我的口味比较两三家餐馆，缺少信息时先问我。',
    skill: 'explore-food'
  },
  {
    icon: MagicStick,
    title: '轻松半日游',
    subtitle: '少赶路，留点时间休息',
    prompt:
      '想安排一个轻松的半日游，别太累，请先确认出发点和时间，再查询地点和路线。',
    skill: 'plan-relaxed-half-day'
  },
  {
    icon: Tickets,
    title: '先看看有什么',
    subtitle: '从商户分类开始挑选',
    prompt: '看看有哪些商户分类，帮我挑一个适合周末探店的方向。'
  }
]
const toolNames = {
  list_categories: '商户分类',
  search_shops: '店名搜索',
  shops_by_category: '分类商户',
  shop_detail: '商户详情',
  shop_vouchers: '商户优惠券',
  plan_day: '探店预算',
  search_cities: '城市查询',
  search_city_places: '城市地点搜索',
  plan_route: '地图路线',
  remember_preferences: '保存出行偏好',
  load_travel_skill: '加载旅行技能'
}
const skillNames = {
  'explore-food': '美食探索',
  'plan-relaxed-half-day': '轻松半日游'
}

async function scrollToEnd() {
  await nextTick()
  timeline.value?.scrollTo({
    top: timeline.value.scrollHeight,
    behavior: 'smooth'
  })
}

function sendSuggestion(prompt, skill = null) {
  if (chat.pending || chat.busy) return
  chat.send(prompt, skill)
}

function sendDraft() {
  if (!canSend.value) return
  chat.send(chat.draft)
}

function fillBudget() {
  chat.draft = '我的人均预算是'
  input.value?.focus()
}

function handleKeydown(event) {
  // Mobile IME confirmation and Shift+Enter must not accidentally send a message.
  if (
    event.key === 'Enter' &&
    !event.shiftKey &&
    !event.isComposing &&
    event.keyCode !== 229
  ) {
    event.preventDefault()
    sendDraft()
  }
}

function goBack() {
  if (window.history.state?.back) router.back()
  else router.push('/index')
}

watch(() => [chat.messages.length, chat.pending], scrollToEnd)
watch(
  () => route.query.shopId,
  (id) => {
    if (/^[1-9]\d{0,19}$/.test(String(id || ''))) {
      chat.draft = `请查询商户ID为${id}的店铺详情和优惠券，帮我看看人均消费、营业时间和使用规则。`
      nextTick(() => input.value?.focus())
    }
  },
  { immediate: true }
)
function openMemory(tab) {
  memoryTab.value = tab
  memoryOpen.value = true
}
onMounted(async () => {
  const prepared = chat.draft
  const account = useUserStore().token
  await chat.initialize()
  if (prepared && account === useUserStore().token) chat.draft = prepared
  scrollToEnd()
})
</script>

<template>
  <div class="travel-page">
    <header class="travel-header">
      <button
        type="button"
        class="icon-button back-button"
        aria-label="返回上一页"
        @click="goBack"
      >
        <el-icon><ArrowLeft /></el-icon>
      </button>
      <div class="header-brand">
        <span class="brand-mark"
          ><el-icon><MagicStick /></el-icon
        ></span>
        <div>
          <h1>AI 旅伴</h1>
          <span>把出行想法，慢慢变成计划</span>
        </div>
      </div>
      <button
        type="button"
        class="new-chat"
        :disabled="!hasMessages && !chat.draft"
        @click="chat.reset"
      >
        <el-icon><Plus /></el-icon><span>新对话</span>
      </button>
    </header>

    <nav class="travel-toolbar" aria-label="出行与记忆工具">
      <button type="button" @click="cityOpen = true">
        {{ chat.selectedCity || '选择城市' }} ▾</button
      ><router-link to="/travel/map">地图出行</router-link
      ><button type="button" @click="openMemory('history')">历史对话</button
      ><button type="button" @click="openMemory('preferences')">
        我的记忆
      </button>
    </nav>
    <p v-if="chat.memoryError" class="memory-warning" role="alert">
      {{ chat.memoryError }}
      <button type="button" @click="chat.initialize">重新连接记忆</button>
    </p>
    <p v-if="chat.busy" class="memory-warning" role="status">
      这段对话仍在生成，正在自动等待最新结果。也可以新建对话。
    </p>

    <main ref="timeline" class="travel-timeline" aria-label="旅伴对话">
      <div v-if="!hasMessages" class="welcome">
        <div class="welcome-symbol">
          <el-icon><MagicStick /></el-icon><span class="spark spark-one">✦</span
          ><span class="spark spark-two">✧</span>
        </div>
        <div class="eyebrow">YOUR LITTLE TRAVEL COMPANION</div>
        <h2>下一顿美食，<br />下一次出发。<span>一起想想？</span></h2>
        <p class="welcome-copy">
          告诉我你的口味和预算，<br
            class="mobile-break"
          />我来帮你找店、看优惠、安排探店。
        </p>
        <div class="suggestion-list">
          <button
            v-for="suggestion in suggestions"
            :key="suggestion.title"
            type="button"
            class="suggestion"
            @click="sendSuggestion(suggestion.prompt, suggestion.skill)"
          >
            <span class="suggestion-icon"
              ><el-icon><component :is="suggestion.icon" /></el-icon
            ></span>
            <span class="suggestion-copy"
              ><strong>{{ suggestion.title }}</strong
              ><small>{{ suggestion.subtitle }}</small></span
            >
            <el-icon class="suggestion-arrow"><ArrowRight /></el-icon>
          </button>
        </div>
        <p class="welcome-note">
          <el-icon><Check /></el-icon>先查询商户信息，再给你建议
        </p>
      </div>

      <div
        v-else
        class="messages"
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
      >
        <div class="conversation-note">这次想怎么逛，我们一起商量。</div>
        <article
          v-for="message in chat.messages"
          :key="message.id"
          class="message"
          :class="message.role"
        >
          <template v-if="message.role === 'user'"
            ><div class="user-bubble">{{ message.content }}</div></template
          >
          <template v-else>
            <div class="assistant-label">
              <span class="mini-brand"
                ><el-icon><MagicStick /></el-icon></span
              >旅伴<span class="ai-badge">AI</span>
            </div>
            <div
              v-if="message.state === 'pending'"
              class="thinking"
              role="status"
            >
              <span class="thinking-dots"><i></i><i></i><i></i></span
              ><span>正在查询和整理建议…</span>
            </div>
            <div
              v-else
              class="assistant-body"
              :class="{ 'error-body': message.state === 'error' }"
            >
              <AgentRichText :text="message.content" />
              <p v-if="message.skills?.length" class="status-note">
                本次玩法：{{
                  message.skills
                    .map((name) => skillNames[name] || name)
                    .join('、')
                }}
              </p>
              <TravelResultCards
                v-if="message.state === 'complete'"
                :tools="message.tools"
                :pending="chat.pending"
                @ask="sendSuggestion"
              />
              <MapResultCards
                v-if="message.state === 'complete'"
                :tools="message.tools"
              />
              <p v-if="message.stopped" class="status-note">
                本次查询已达到上限，可以缩小范围后继续。
              </p>
              <details v-if="message.tools?.length" class="query-sources">
                <summary>
                  查看本次查询与处理过程（{{ message.tools.length }}）
                </summary>
                <div v-for="(result, index) in message.tools" :key="index">
                  <span>{{ toolNames[result.tool] || '商户信息' }}</span
                  ><span :class="{ 'query-failed': result.data?.error }">{{
                    result.data?.error ? '查询未成功' : '已返回结果'
                  }}</span>
                </div>
              </details>
              <button
                v-if="
                  message.state === 'error' &&
                  message.id === chat.messages.at(-1)?.id
                "
                class="retry-button"
                type="button"
                :disabled="chat.pending"
                @click="chat.retry"
              >
                <el-icon><RefreshRight /></el-icon>重新发送
              </button>
            </div>
          </template>
        </article>
        <div v-if="!chat.pending" class="followup-chips">
          <button
            type="button"
            @click="
              sendSuggestion(
                '请根据刚才查到的商户，帮我比较人均价格和评分；信息不足时请重新查询。'
              )
            "
          >
            比较一下这些店</button
          ><button type="button" @click="fillBudget">补充我的预算</button>
        </div>
      </div>
    </main>

    <footer class="composer-area">
      <div class="composer" :class="{ 'is-busy': chat.pending }">
        <label class="sr-only" for="travel-prompt">向旅伴发送消息</label>
        <textarea
          id="travel-prompt"
          ref="input"
          v-model="chat.draft"
          rows="2"
          maxlength="4000"
          :placeholder="
            hasMessages
              ? '继续补充口味、预算，或问问优惠券…'
              : '想吃什么，或者想怎么逛？'
          "
          @keydown="handleKeydown"
        ></textarea>
        <div class="composer-bottom">
          <span
            >{{ chat.pending ? '查询需要一点时间' : '找美食 · 查优惠 · 做计划'
            }}<small v-if="chat.draft.length > 3500">
              {{ chat.draft.length }}/4000</small
            ></span
          ><button
            v-if="chat.pending"
            type="button"
            class="stop-button"
            @click="chat.cancel"
          >
            <el-icon><Close /></el-icon>停止等待</button
          ><button
            v-else
            type="button"
            class="send-button"
            :disabled="!canSend"
            aria-label="发送消息"
            @click="sendDraft"
          >
            <el-icon><Promotion /></el-icon>
          </button>
        </div>
      </div>
      <p class="composer-note">
        AI 建议仅供参考，价格与营业信息请以商户实际为准
      </p>
    </footer>
    <FootBar :active-btn="2" />
    <CityPicker v-model="cityOpen" />
    <TravelMemoryPanel v-model="memoryOpen" :initial-tab="memoryTab" />
  </div>
</template>

<style scoped>
.travel-toolbar {
  display: flex;
  gap: 7px;
  flex-shrink: 0;
  justify-content: center;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #f0e8e9;
  flex-wrap: wrap;
}
.travel-toolbar button,
.travel-toolbar a {
  background: #fffaf6;
  color: #a3848c;
  border: 1px solid #ecdee5;
  border-radius: 16px;
  padding: 7px 12px;
  font-size: 11px;
  text-decoration: none;
}
.memory-warning {
  margin: 0;
  padding: 9px 18px;
  background: #fff3e3;
  color: #b08154;
  font-size: 11px;
  text-align: center;
  flex-shrink: 0;
  line-height: 1.8;
}
.memory-warning button {
  border: 0;
  background: none;
  text-decoration: underline;
  color: inherit;
}
.travel-page {
  --ink: #302a35;
  --muted: #958994;
  --accent: #ec754e;
  box-sizing: border-box;
  height: 100vh;
  height: 100dvh;
  padding-bottom: max(8vh, 54px);
  display: flex;
  flex-direction: column;
  background: #fcfaf8;
  color: var(--ink);
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
}
.travel-page *,
.travel-page *::before,
.travel-page *::after {
  box-sizing: border-box;
}
button {
  font: inherit;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
button:disabled {
  cursor: default;
  opacity: 0.45;
}
button:focus-visible,
textarea:focus-visible,
:deep(a:focus-visible) {
  outline: 2px solid #b685bd;
  outline-offset: 4px;
}
.travel-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px max(20px, calc((100% - 880px) / 2));
  border-bottom: 1px solid #f1eae4;
  background: rgba(255, 255, 255, 0.92);
}
.icon-button {
  border: 0;
  background: transparent;
  padding: 7px;
  color: #655c69;
  font-size: 19px;
  display: inline-flex;
}
.header-brand {
  display: flex;
  align-items: center;
  gap: 11px;
  flex: 1;
}
.brand-mark,
.mini-brand {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  color: #fff;
  background: linear-gradient(135deg, #f4a266, #e57774 60%, #a688bb);
}
.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 13px;
  font-size: 23px;
  box-shadow: 0 4px 12px #e9926b20;
}
h1 {
  margin: 0;
  font-size: 18px;
  letter-spacing: 0.5px;
  font-weight: 650;
}
.header-brand div > span {
  display: block;
  font-size: 10px;
  color: var(--muted);
  margin-top: 3px;
}
.new-chat {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  border: 1px solid #eae3e5;
  border-radius: 18px;
  background: #fff;
  padding: 8px 12px;
  font-size: 12px;
  color: #77687d;
  white-space: nowrap;
}
.travel-timeline {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
}
.welcome {
  max-width: 580px;
  padding: 35px 24px 20px;
  margin: auto;
}
.welcome-symbol {
  width: 70px;
  height: 70px;
  margin: 0 0 24px;
  background: linear-gradient(140deg, #fff0dc, #f8dce0 65%, #e8e1f3);
  border: 1px solid #ffffff;
  border-radius: 25px;
  color: #c67773;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 37px;
  position: relative;
  box-shadow:
    0 8px 28px #e1c1aa35,
    inset 0 0 0 5px #ffffff55;
  transform: rotate(-7deg);
}
.spark {
  position: absolute;
  font-size: 19px;
  color: #bd96b6;
}
.spark-one {
  top: 0;
  right: -19px;
}
.spark-two {
  bottom: -8px;
  right: -9px;
  font-size: 14px;
}
.eyebrow {
  font-size: 9px;
  letter-spacing: 2px;
  color: #b09aa4;
  margin-bottom: 14px;
}
h2 {
  margin: 0;
  font-size: clamp(27px, 4vw, 35px);
  font-weight: 600;
  line-height: 1.55;
  letter-spacing: 1px;
}
h2 span {
  color: #bd7f86;
}
.welcome-copy {
  font-size: 13px;
  line-height: 1.9;
  color: #948592;
  margin: 17px 0 24px;
}
.suggestion-list {
  display: grid;
  gap: 10px;
}
.suggestion {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  text-align: left;
  border: 1px solid #ece5df;
  border-radius: 15px;
  padding: 15px 17px;
  background: #fffdfb;
  color: var(--ink);
  transition:
    transform 0.15s,
    border-color 0.15s;
}
.suggestion:hover {
  transform: translateY(-2px);
  border-color: #e7baa2;
}
.suggestion-icon {
  color: #d48c61;
  background: #fff1e5;
  padding: 10px;
  display: inline-flex;
  font-size: 20px;
  border-radius: 12px;
}
.suggestion:nth-child(2) .suggestion-icon {
  color: #9c80b4;
  background: #f2ebf7;
}
.suggestion:nth-child(3) .suggestion-icon {
  color: #7e9b81;
  background: #edf4eb;
}
.suggestion-copy {
  flex: 1;
}
.suggestion-copy strong {
  display: block;
  font-size: 14px;
  font-weight: 550;
}
.suggestion-copy small {
  display: block;
  margin-top: 5px;
  font-size: 11px;
  color: #a0929a;
}
.suggestion-arrow {
  color: #b6a6ac;
}
.welcome-note {
  display: flex;
  gap: 5px;
  align-items: center;
  font-size: 10px;
  color: #aa9a9d;
  margin-top: 20px;
}
.messages {
  max-width: 740px;
  padding: 20px 24px 30px;
  margin: auto;
}
.conversation-note {
  text-align: center;
  font-size: 11px;
  color: #b2a2aa;
  padding: 5px 0 22px;
}
.message {
  margin-bottom: 26px;
  font-size: 14px;
}
.message.user {
  display: flex;
  justify-content: flex-end;
}
.user-bubble {
  max-width: 87%;
  border: 1px solid #f0d6c5;
  border-radius: 17px 17px 4px 17px;
  background: #ffeadb;
  color: #654733;
  padding: 13px 17px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.assistant-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #786571;
  margin-bottom: 10px;
}
.mini-brand {
  width: 26px;
  height: 26px;
  border-radius: 9px;
  font-size: 17px;
}
.ai-badge {
  border: 1px solid #e4d8e7;
  color: #b098b2;
  font-size: 9px;
  border-radius: 4px;
  padding: 1px 4px;
}
.assistant-body {
  padding-left: 34px;
  min-width: 0;
}
.error-body {
  color: #ac5b52;
}
.thinking {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 0 10px 34px;
  color: #ac939e;
  font-size: 12px;
}
.thinking-dots {
  display: inline-flex;
  gap: 4px;
}
.thinking-dots i {
  display: block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #c795a4;
  animation: breathe 1.2s infinite;
}
.thinking-dots i:nth-child(2) {
  animation-delay: 0.2s;
}
.thinking-dots i:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes breathe {
  50% {
    opacity: 0.3;
    transform: translateY(-3px);
  }
}
.query-sources {
  color: #a398a0;
  margin-top: 13px;
  font-size: 10px;
}
.query-sources summary {
  cursor: pointer;
}
.query-sources > div {
  display: flex;
  justify-content: space-between;
  gap: 15px;
  padding: 7px 4px;
  border-bottom: 1px solid #f0eaea;
}
.query-failed {
  color: #bc7b69;
}
.retry-button {
  margin-top: 8px;
  border: 1px solid #ead3cc;
  color: #b16d5a;
  background: #fff8f4;
  border-radius: 8px;
  display: inline-flex;
  gap: 5px;
  align-items: center;
  padding: 7px 10px;
  font-size: 12px;
}
.status-note {
  font-size: 11px;
  color: #ad8560;
}
.followup-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 34px;
}
.followup-chips button {
  border: 1px solid #e8dee6;
  background: #fffcff;
  color: #937c99;
  border-radius: 20px;
  padding: 8px 12px;
  font-size: 11px;
}
.composer-area {
  flex-shrink: 0;
  padding: 10px max(20px, calc((100% - 692px) / 2)) 8px;
  background: linear-gradient(#fcfaf8eb, #fcfaf8);
}
.composer {
  background: #fff;
  border: 1px solid #e3d7df;
  border-radius: 18px;
  padding: 13px 14px 9px;
  box-shadow: 0 5px 25px #9a6d8710;
}
.composer:focus-within {
  border-color: #cda2b9;
}
textarea {
  display: block;
  width: 100%;
  resize: none;
  border: 0;
  background: transparent;
  color: #493c4c;
  font: inherit;
  font-size: 14px;
  line-height: 1.7;
  min-height: 48px;
  max-height: 120px;
  outline: none;
  padding: 0 2px;
}
.composer textarea:focus-visible {
  outline: none;
}
textarea::placeholder {
  color: #bcadb6;
}
.composer-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-top: 3px;
}
.composer-bottom > span {
  color: #b9a6b2;
  font-size: 10px;
}
.composer-bottom small {
  color: #aa7587;
}
.send-button {
  border: 0;
  background: linear-gradient(130deg, #ec9265, #df7b84);
  color: white;
  border-radius: 11px;
  width: 36px;
  height: 33px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}
.send-button:disabled {
  background: #e6dee2;
  opacity: 1;
}
.stop-button {
  border: 1px solid #dfd2de;
  border-radius: 10px;
  background: #faf6fb;
  color: #937c99;
  padding: 7px 9px;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.composer-note {
  text-align: center;
  font-size: 9px;
  color: #b9adb4;
  margin: 8px 0 0;
  line-height: 1.5;
}
.sr-only {
  position: absolute;
  height: 1px;
  width: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
@media (min-width: 700px) {
  .mobile-break {
    display: none;
  }
  .welcome {
    padding-top: 42px;
  }
  .welcome-symbol {
    margin-bottom: 26px;
  }
  .travel-header {
    min-height: 83px;
  }
}
@media (max-width: 400px) {
  .travel-header {
    gap: 9px;
    padding: 13px 12px;
  }
  .header-brand {
    gap: 8px;
  }
  .header-brand div > span {
    font-size: 9px;
  }
  .new-chat {
    padding: 7px 9px;
  }
  .welcome {
    padding: 24px 21px 16px;
  }
  .welcome-symbol {
    width: 56px;
    height: 56px;
    font-size: 30px;
    margin-bottom: 20px;
  }
  h2 {
    font-size: 27px;
  }
  .suggestion {
    padding: 12px;
  }
  .messages {
    padding-left: 17px;
    padding-right: 17px;
  }
  .assistant-body {
    padding-left: 0;
  }
  .composer-area {
    padding-left: 13px;
    padding-right: 13px;
  }
}
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
  }
}
</style>
