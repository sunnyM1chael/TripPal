<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Close,
  MagicStick,
  Sunny,
  Umbrella,
  Wallet,
  Guide,
  Plus,
  Promotion,
  RefreshRight,
  Shop,
  Tickets
} from '@element-plus/icons-vue'
import FootBar from '@/components/FootBar.vue'
import DonkeyMascot from '@/components/DonkeyMascot.vue'
import AgentRichText from '@/components/AgentRichText.vue'
import TravelResultCards from '@/components/TravelResultCards.vue'
import MapResultCards from '@/components/MapResultCards.vue'
import ItineraryResultCards from '@/components/ItineraryResultCards.vue'
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
    icon: Guide,
    title: '多日行程规划',
    subtitle: '按天安排，用高德核算路线',
    prompt:
      '帮我生成并保存一份按天安排的城市行程。先确认城市、天数、同行人数、全程总预算、出行方式和兴趣偏好，再查询真实地点与高德路线。',
    skill: 'plan-city-trip'
  },
  {
    icon: Guide,
    title: '到站第一程',
    subtitle: '放下行李，轻松开启探索',
    prompt:
      '刚到一座城市，帮我安排从车站或酒店出发的第一程，先确认具体起点和可用时间。',
    skill: 'arrival-first-stop'
  },
  {
    icon: RefreshRight,
    title: '随心改行程',
    subtitle: '走累了，就换一种安排',
    prompt:
      '想调整剩余行程，请先读取当前行程，确认我的当前位置和剩余时间，再给出少走路的方案。',
    skill: 'replan-remaining'
  },
  {
    icon: Wallet,
    title: '预算一日游',
    subtitle: '把钱花在喜欢的地方',
    prompt:
      '想安排一次预算友好的一日游，请先确认城市、人数、预算口径和出发点。',
    skill: 'budget-city-day'
  },
  {
    icon: Sunny,
    title: '亲子慢游',
    subtitle: '带上家人，放慢一点',
    prompt: '想带家人轻松逛逛，请先确认同行需求、步行接受度和休息安排。',
    skill: 'family-slow-trip'
  },
  {
    icon: Umbrella,
    title: '雨天备选',
    subtitle: '天气变了，好心情继续',
    prompt:
      '如果下雨，帮我准备室内备选方案，先确认城市和剩余时间，不需要猜天气。',
    skill: 'rainy-day-plan'
  },
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
    title: '优惠券核查',
    subtitle: '看清规则，再决定划不划算',
    prompt:
      '帮我核查一家平台商户的优惠券，比较购买价、面值和使用限制，先问我是哪家店。',
    skill: 'voucher-check'
  }
]
const toolNames = {
  get_visit_feedback: '回顾我的出行体验',
  search_trip_places: '批量查询行程地点',
  prepare_voucher_subscription: '准备候补操作',
  get_voucher_subscription: '回查候补状态',
  compare_shops: '商户对比',
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
  load_travel_skill: '加载旅行技能',
  create_itinerary: '保存行程',
  get_current_itinerary: '读取当前行程',
  edit_current_itinerary: '调整行程与路线'
}
const skillNames = {
  'visit-review': '去过之后',
  'plan-city-trip': '多日行程规划',
  'arrival-first-stop': '到站第一程',
  'replan-remaining': '随心改行程',
  'budget-city-day': '预算一日游',
  'family-slow-trip': '亲子慢游',
  'rainy-day-plan': '雨天备选',
  'voucher-check': '优惠券核查',
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
  if (/^[a-f0-9-]{36}$/i.test(String(route.query.itinerary || ''))) {
    chat.activeItineraryId = route.query.itinerary
    if (!chat.draft) chat.draft = '请先查看当前行程，帮我调整后续安排。'
  }
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
        <span class="brand-mark donkey-brand"><DonkeyMascot decorative /></span>
        <div>
          <h1>驴友 <small class="brand-english">TripPal</small></h1>
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
      ><router-link to="/travel/itineraries">我的行程</router-link
      ><button type="button" @click="openMemory('history')">历史对话</button
      ><button type="button" @click="openMemory('preferences')">
        我的记忆
      </button>
    </nav>
    <p v-if="chat.activeItineraryId" class="memory-warning">
      当前对话关联了一份已保存行程，可直接说“换一家”或“少走点”。
      <router-link
        :to="{
          path: '/travel/itineraries',
          query: { id: chat.activeItineraryId }
        }"
        >查看行程</router-link
      >
      <button
        type="button"
        :disabled="chat.pending || chat.busy"
        @click="chat.activeItineraryId = null"
      >
        取消关联
      </button>
    </p>
    <p v-if="chat.memoryError" class="memory-warning" role="alert">
      {{ chat.memoryError }}
      <button type="button" @click="chat.initialize">重新连接记忆</button>
    </p>
    <p v-if="chat.busy" class="memory-warning" role="status">
      这段对话仍在生成，正在自动等待最新结果。也可以新建对话。
    </p>

    <main ref="timeline" class="travel-timeline" aria-label="驴友对话">
      <div v-if="!hasMessages" class="welcome">
        <div class="welcome-symbol donkey-welcome"><DonkeyMascot /></div>
        <svg
          class="landscape"
          viewBox="0 0 360 240"
          fill="none"
          aria-hidden="true"
        >
          <circle cx="278" cy="55" r="28" fill="#e9cf80" />
          <path
            d="M0 160 Q75 38 165 130 Q250 22 360 120 V240 H0Z"
            fill="#c6dfb3"
          />
          <path
            d="M0 195 Q100 85 210 163 Q300 85 360 155 V240 H0Z"
            fill="#8fbea0"
          />
          <path
            d="M0 225 Q110 135 220 207 Q300 155 360 190 V240 H0Z"
            fill="#4e9274"
          />
          <path
            d="M210 240 Q138 207 217 177 Q245 162 216 151"
            stroke="#f4efcf"
            stroke-width="13"
          />
          <path
            d="M70 125 V179 M48 154 L70 113 L93 154Z"
            stroke="#39755d"
            stroke-width="5"
            stroke-linejoin="round"
            fill="#39755d"
          />
          <path
            d="M300 125 V165 M284 145 L300 115 L316 145Z"
            stroke="#39755d"
            stroke-width="4"
            stroke-linejoin="round"
            fill="#39755d"
          />
        </svg>
        <div class="eyebrow">A LITTLE ESCAPE · 一起去走走</div>
        <div class="welcome-tag">
          <el-icon><Guide /></el-icon>
          {{ chat.selectedCity || '从你喜欢的城市开始' }} · 慢慢探索
        </div>
        <h2>把日子过成，<br /><span>喜欢的风景。</span></h2>
        <p class="welcome-copy">
          想吃的小店、想走的街道，<br
            class="mobile-break"
          />和驴友一起，安排下一段小小的出发。
        </p>
        <div class="section-caption">
          <strong>今天，想怎样出发？</strong
          ><span>选一个灵感，驴友陪你细化</span>
        </div>
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
              <span class="mini-brand donkey-avatar"
                ><DonkeyMascot decorative /></span
              >驴友<span class="ai-badge">AI</span>
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
              <ItineraryResultCards :tools="message.tools" />
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
        <label class="sr-only" for="travel-prompt">向驴友发送消息</label>
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
  border-bottom: 1px solid var(--tp-line);
  flex-wrap: wrap;
}
.travel-toolbar button,
.travel-toolbar a {
  background: #f6fbf7;
  color: var(--tp-ink);
  border: 1px solid var(--tp-line);
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
  --ink: var(--tp-ink);
  --muted: var(--tp-muted);
  --accent: var(--tp-ink);
  box-sizing: border-box;
  height: 100vh;
  height: 100dvh;
  padding-bottom: max(8vh, 54px);
  display: flex;
  flex-direction: column;
  background: #f2f8f3;
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
  outline: 2px solid var(--tp-ink);
  outline-offset: 4px;
}
.travel-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px max(20px, calc((100% - 880px) / 2));
  border-bottom: 1px solid var(--tp-line);
  background: rgba(255, 255, 255, 0.92);
}
.icon-button {
  border: 0;
  background: transparent;
  padding: 7px;
  color: var(--tp-ink);
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
  background: var(--tp-ink);
}
.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 13px;
  font-size: 23px;
  box-shadow: 0 4px 12px #292c2820;
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
  border: 1px solid var(--tp-line);
  border-radius: 18px;
  background: #fff;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--tp-ink);
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
  background: var(--tp-surface-soft);
  border: 1px solid #ffffff;
  border-radius: 25px;
  color: var(--tp-ink);
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 37px;
  position: relative;
  box-shadow:
    0 8px 28px #292c2825,
    inset 0 0 0 5px #ffffff55;
  transform: rotate(-7deg);
}
.spark {
  position: absolute;
  font-size: 19px;
  color: var(--tp-muted);
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
  color: var(--tp-muted);
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
  color: var(--tp-ink);
}
.welcome-copy {
  font-size: 13px;
  line-height: 1.9;
  color: var(--tp-muted);
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
  border: 1px solid var(--tp-line);
  border-radius: 15px;
  padding: 15px 17px;
  background: #ffffff;
  color: var(--ink);
  transition:
    transform 0.15s,
    border-color 0.15s;
}
.suggestion:hover {
  transform: translateY(-2px);
  border-color: var(--tp-line);
}
.suggestion-icon {
  color: var(--tp-ink);
  background: var(--tp-surface-soft);
  padding: 10px;
  display: inline-flex;
  font-size: 20px;
  border-radius: 12px;
}
.suggestion:nth-child(2) .suggestion-icon {
  color: var(--tp-ink);
  background: var(--tp-surface-soft);
}
.suggestion:nth-child(3) .suggestion-icon {
  color: var(--tp-ink);
  background: var(--tp-surface-soft);
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
  color: var(--tp-muted);
}
.suggestion-arrow {
  color: var(--tp-muted);
}
.welcome-note {
  display: flex;
  gap: 5px;
  align-items: center;
  font-size: 10px;
  color: var(--tp-muted);
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
  color: var(--tp-muted);
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
  border: 1px solid var(--tp-line);
  border-radius: 17px 17px 4px 17px;
  background: var(--tp-surface-soft);
  color: var(--tp-ink);
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
  color: var(--tp-ink);
  margin-bottom: 10px;
}
.mini-brand {
  width: 26px;
  height: 26px;
  border-radius: 9px;
  font-size: 17px;
}
.ai-badge {
  border: 1px solid var(--tp-line);
  color: var(--tp-muted);
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
  color: var(--tp-muted);
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
  background: var(--tp-ink);
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
  color: var(--tp-muted);
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
  border-bottom: 1px solid var(--tp-line);
}
.query-failed {
  color: var(--tp-muted);
}
.retry-button {
  margin-top: 8px;
  border: 1px solid var(--tp-line);
  color: var(--tp-muted);
  background: var(--tp-surface-soft);
  border-radius: 8px;
  display: inline-flex;
  gap: 5px;
  align-items: center;
  padding: 7px 10px;
  font-size: 12px;
}
.status-note {
  font-size: 11px;
  color: #567a62;
}
.followup-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 34px;
}
.followup-chips button {
  border: 1px solid var(--tp-line);
  background: #f8fcf8;
  color: var(--tp-ink);
  border-radius: 20px;
  padding: 8px 12px;
  font-size: 11px;
}
.composer-area {
  flex-shrink: 0;
  padding: 10px max(20px, calc((100% - 692px) / 2)) 8px;
  background: var(--tp-surface-soft);
}
.composer {
  background: #fff;
  border: 1px solid var(--tp-line);
  border-radius: 18px;
  padding: 13px 14px 9px;
  box-shadow: 0 5px 25px #292c2812;
}
.composer:focus-within {
  border-color: var(--tp-line);
}
textarea {
  display: block;
  width: 100%;
  resize: none;
  border: 0;
  background: transparent;
  color: var(--tp-ink);
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
  color: var(--tp-muted);
}
.composer-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-top: 3px;
}
.composer-bottom > span {
  color: var(--tp-muted);
  font-size: 10px;
}
.composer-bottom small {
  color: var(--tp-ink);
}
.send-button {
  border: 0;
  background: var(--tp-ink);
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
  background: var(--tp-line);
  opacity: 1;
}
.stop-button {
  border: 1px solid var(--tp-line);
  border-radius: 10px;
  background: var(--tp-surface-soft);
  color: var(--tp-ink);
  padding: 7px 9px;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.composer-note {
  text-align: center;
  font-size: 9px;
  color: var(--tp-muted);
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

/* A travel journal layout, with landscape shapes drawn in CSS. */
.travel-page {
  background: var(--tp-surface-soft);
}
.travel-header {
  background: #ffffffdb;
}
.brand-english {
  font-size: 11px;
  color: var(--tp-ink);
  font-weight: 500;
  margin-left: 4px;
}
.travel-toolbar {
  background: #ffffff80;
  padding: 12px;
}
.travel-toolbar a,
.travel-toolbar button {
  font-size: 12px;
  color: var(--tp-ink);
  background: white;
}
.travel-toolbar a:hover,
.travel-toolbar button:hover {
  border-color: var(--tp-line);
  background: var(--tp-surface-soft);
}
.welcome {
  max-width: 860px;
  width: 100%;
  position: relative;
  padding-top: 28px;
}
.welcome::before {
  content: '';
  position: absolute;
  width: 160px;
  height: 120px;
  border-radius: 75% 40% 60% 35%;
  right: 32px;
  top: 40px;
  background: var(--tp-surface-soft);
  transform: rotate(-12deg);
  opacity: 0.6;
  pointer-events: none;
}
.welcome::after {
  content: '';
  position: absolute;
  width: 95px;
  height: 95px;
  border: 1px solid #292c2870;
  border-radius: 50%;
  right: 55px;
  top: 52px;
  pointer-events: none;
}
.welcome-symbol {
  width: 52px;
  height: 52px;
  font-size: 28px;
  border-radius: 18px;
  margin-bottom: 18px;
}
.welcome-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--tp-ink);
  margin-bottom: 10px;
}
h2 {
  font-size: clamp(30px, 4vw, 43px);
  letter-spacing: 2px;
  line-height: 1.4;
}
.welcome-copy {
  margin: 14px 0 22px;
  color: var(--tp-ink);
}
.eyebrow {
  color: var(--tp-ink);
  font-size: 9px;
  letter-spacing: 2.5px;
}
.suggestion-list {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.suggestion {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  min-height: 126px;
  padding: 16px;
  border-radius: 19px;
  box-shadow: 0 4px 20px #292c2804;
}
.suggestion-copy strong {
  font-weight: 650;
}
.suggestion-copy small {
  line-height: 1.6;
}
.suggestion-arrow {
  position: absolute;
  right: 15px;
  top: 22px;
}
.suggestion-icon {
  padding: 9px;
  font-size: 21px;
}
.suggestion:nth-child(3n + 2) {
  background: var(--tp-surface-soft);
}
.suggestion:nth-child(3n) {
  background: var(--tp-surface-soft);
}
.assistant-body {
  background: #ffffffd9;
  border: 1px solid var(--tp-line);
  border-radius: 4px 20px 20px;
  padding: 16px 19px;
  margin-left: 34px;
}
.assistant-label {
  color: var(--tp-ink);
}
.composer {
  border-radius: 22px;
  box-shadow: 0 8px 28px #292c2810;
}
.composer-area {
  background: var(--tp-surface-soft);
}
.travel-page :deep(.foot .active) {
  color: var(--tp-ink);
}
@media (max-width: 600px) {
  .welcome {
    padding: 24px 20px 18px;
  }
  .suggestion-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 9px;
  }
  .suggestion {
    min-height: 120px;
    padding: 13px;
    gap: 9px;
  }
  .welcome::before {
    right: 15px;
    width: 100px;
    height: 90px;
    top: 35px;
    opacity: 0.45;
  }
  .welcome::after {
    right: 30px;
    width: 65px;
    height: 65px;
    top: 47px;
  }
  .assistant-body {
    margin-left: 0;
    padding: 14px;
  }
}

.landscape {
  position: absolute;
  right: 20px;
  top: 24px;
  width: 300px;
  height: 210px;
  opacity: 0.9;
  pointer-events: none;
  border-radius: 35% 35% 24% 24%;
}
.welcome::before,
.welcome::after {
  display: none;
}
.welcome > :not(.landscape) {
  position: relative;
}
.welcome h2 {
  max-width: 420px;
  font-weight: 750;
  letter-spacing: 1px;
}
.section-caption {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin: 28px 0 14px;
}
.section-caption strong {
  font-size: 15px;
}
.section-caption span {
  font-size: 11px;
  color: var(--tp-muted);
}
.suggestion-list {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.suggestion {
  transition:
    transform 0.18s,
    box-shadow 0.18s;
  border-color: var(--tp-line);
}
.suggestion:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px #292c2812;
}
@media (max-width: 700px) {
  .landscape {
    width: 155px;
    height: 125px;
    right: 8px;
    top: 65px;
    opacity: 0.6;
  }
  .suggestion-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .section-caption {
    align-items: flex-start;
    flex-direction: column;
    gap: 5px;
  }
  .welcome h2 {
    font-size: 30px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .suggestion:hover {
    transform: none;
  }
}
.brand-mark.donkey-brand {
  width: 44px;
  height: 52px;
  background: transparent;
  box-shadow: none;
}
.welcome-symbol.donkey-welcome {
  width: 80px;
  height: 96px;
  background: transparent;
  box-shadow: none;
  transform: none;
}
.mini-brand.donkey-avatar {
  width: 28px;
  height: 34px;
  background: transparent;
  border-radius: 0;
}
</style>
