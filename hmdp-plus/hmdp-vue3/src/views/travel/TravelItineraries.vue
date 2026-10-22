<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/modules/user'
import { useTravelStore } from '@/stores/modules/travel'
import {
  createItinerary,
  deleteItinerary,
  editItinerary,
  getItinerary,
  listItineraries,
  searchPlaces
} from '@/api/travel'
import { formatDistance, formatDuration, navigationFor } from '@/utils/maps'
import FootBar from '@/components/FootBar.vue'
import ItineraryDayOverview from '@/components/ItineraryDayOverview.vue'
import VisitFeedbackForm from '@/components/VisitFeedbackForm.vue'

const route = useRoute(),
  router = useRouter(),
  chat = useTravelStore(),
  user = useUserStore()
const plans = ref([]),
  current = ref(null),
  busy = ref(false),
  error = ref(''),
  notice = ref('')
const search = ref(''),
  results = ref([]),
  selected = ref([]),
  replacing = ref(null)
const creating = ref(false),
  searching = ref(false)
const form = reactive({
  title: '轻松逛一逛',
  city: '',
  people: 1,
  budget_yuan: '',
  mode: 'walking',
  start_time: '14:00',
  end_time: '18:00',
  rest_minutes: 20
})
const settings = reactive({})
const activeCity = computed(() => current.value?.city || form.city)
const legFrom = (stop) =>
  current.value?.legs.find((leg) => leg.origin_stop_id === stop.id)
const dayStopCount = (stop) =>
  current.value?.stops.filter((item) => (item.day || 1) === (stop.day || 1))
    .length
let generation = 0

function setCurrent(plan) {
  current.value = plan
  replacing.value = null
  results.value = []
  if (plan)
    Object.assign(settings, {
      title: plan.title,
      budget_yuan: plan.budget_yuan ?? '',
      mode: plan.mode,
      start_time: plan.start_time || '',
      end_time: plan.end_time || '',
      rest_minutes: plan.rest_minutes
    })
}

function feedbackSaved(plan) {
  if (plan.id !== current.value?.id || plan.revision <= current.value.revision)
    return
  setCurrent(plan)
  plans.value = plans.value.map((row) => (row.id === plan.id ? plan : row))
  notice.value = '体验和私有草稿已保存。'
}

function feedbackRefreshed(plan) {
  feedbackSaved(plan)
  notice.value = '已加载最新行程，请核对已保存体验后决定是否重新保存。'
}

async function load(id) {
  const turn = ++generation,
    account = user.token
  if (!id) {
    setCurrent(null)
    return
  }
  error.value = ''
  setCurrent(null)
  creating.value = false
  try {
    const plan = await getItinerary(id)
    if (account === user.token && turn === generation) {
      setCurrent(plan)
      creating.value = false
    }
  } catch (e) {
    if (turn === generation) {
      setCurrent(null)
      error.value = e.message
    }
  }
}

async function refresh() {
  const account = user.token
  try {
    const data = await listItineraries()
    if (account !== user.token) return
    plans.value = data
    await load(route.query.id || current.value?.id || data[0]?.id)
  } catch (e) {
    if (account === user.token) error.value = e.message
  }
}

function newPlan() {
  generation++
  setCurrent(null)
  selected.value = []
  search.value = ''
  form.city = chat.selectedCity || chat.preferences.default_city || ''
  error.value = ''
  creating.value = true
  router.replace({ path: '/travel/itineraries' })
}

async function find() {
  if (searching.value || busy.value) return
  if (!activeCity.value.trim() || !search.value.trim()) {
    error.value = '先填写城市和要找的地点。'
    return
  }
  const turn = generation,
    account = user.token
  const city = activeCity.value,
    keyword = search.value
  searching.value = true
  error.value = ''
  try {
    const data = await searchPlaces(city, keyword)
    if (turn === generation && account === user.token)
      results.value = data.places
  } catch (e) {
    if (turn === generation && account === user.token) error.value = e.message
  } finally {
    searching.value = false
  }
}

function add(place) {
  if (selected.value.length >= 6) {
    error.value = '最多安排六个地点，轻松游建议两至三个。'
    return
  }
  if (!selected.value.some((row) => row.place.poi_id === place.poi_id))
    selected.value.push({ place, stay_minutes: 60, kind: 'visit' })
}

async function save() {
  if (busy.value) return
  const account = user.token,
    turn = ++generation
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const plan = await createItinerary({
      ...form,
      people: Number(form.people),
      budget_yuan: form.budget_yuan === '' ? null : Number(form.budget_yuan),
      start_time: form.start_time || null,
      end_time: form.end_time || null,
      stops: selected.value.map((row) => ({
        poi_id: row.place.poi_id,
        stay_minutes: Number(row.stay_minutes),
        kind: row.kind
      }))
    })
    if (account !== user.token || turn !== generation) return
    setCurrent(plan)
    creating.value = false
    plans.value = [plan, ...plans.value.filter((row) => row.id !== plan.id)]
    router.replace({ path: '/travel/itineraries', query: { id: plan.id } })
    notice.value = '行程已保存，刷新后可以继续。'
  } catch (e) {
    if (account === user.token && turn === generation) error.value = e.message
  } finally {
    busy.value = false
  }
}

async function change(action, fields = {}) {
  if (busy.value || !current.value) return
  const account = user.token,
    id = current.value.id,
    turn = ++generation
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const plan = await editItinerary(id, {
      action,
      expected_revision: current.value.revision,
      ...fields
    })
    if (account !== user.token || turn !== generation) return
    setCurrent(plan)
    plans.value = plans.value.map((row) => (row.id === id ? plan : row))
    notice.value = '安排已更新。'
  } catch (e) {
    if (account !== user.token || turn !== generation) return
    if (e.response?.status === 409) {
      await load(id)
      error.value = '其他页面已经更新了行程，已加载最新版本，请重新调整。'
    } else error.value = e.message
  } finally {
    busy.value = false
  }
}

function saveSettings() {
  change('update_plan', {
    ...settings,
    budget_yuan:
      settings.budget_yuan === '' ? null : Number(settings.budget_yuan),
    start_time: settings.start_time || null,
    end_time: settings.end_time || null
  })
}

async function removePlan() {
  if (
    busy.value ||
    !current.value ||
    !window.confirm('删除这份行程？此操作无法撤销。')
  )
    return
  const id = current.value.id,
    account = user.token,
    turn = ++generation
  busy.value = true
  try {
    await deleteItinerary(id, current.value.revision)
    if (account !== user.token || turn !== generation) return
    plans.value = plans.value.filter((p) => p.id !== id)
    setCurrent(null)
    router.replace({ path: '/travel/itineraries' })
  } catch (e) {
    if (account === user.token && turn === generation) error.value = e.message
  } finally {
    busy.value = false
  }
}

function openReplacement(stop) {
  generation++
  replacing.value = stop
  results.value = []
  search.value = ''
  error.value = ''
}
const kindNames = { visit: '游览', meal: '用餐', rest: '休息' }

watch(
  () => route.query.id,
  (id) => load(id)
)
watch(
  () => user.token,
  () => {
    generation++
    plans.value = []
    setCurrent(null)
    selected.value = []
    results.value = []
    creating.value = false
    error.value = ''
    notice.value = ''
    router.replace({ path: '/travel/itineraries' })
    refresh()
  }
)
onMounted(async () => {
  form.city = chat.selectedCity || ''
  await refresh()
})
</script>

<template>
  <div class="itinerary-page">
    <header>
      <router-link to="/travel">← 驴友</router-link
      ><span>TRIPPAL · YOUR DAY</span>
    </header>
    <section class="intro">
      <small>把想去的地方，变成真正的安排</small>
      <h1>我的行程</h1>
      <p>慢一点走，留一点时间给喜欢的地方。</p>
    </section>
    <div class="top-actions">
      <button :disabled="busy" @click="newPlan">＋ 新建行程</button
      ><button :disabled="busy" @click="refresh">刷新列表</button>
    </div>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="notice" role="status" class="notice">{{ notice }}</p>
    <p v-if="busy" role="status" class="notice">
      正在核对地点、刷新路线并保存，请稍候…
    </p>
    <div class="layout">
      <aside aria-label="已保存行程">
        <p class="label">已保存 {{ plans.length }} 份</p>
        <router-link
          v-for="plan in plans"
          :key="plan.id"
          :class="{ active: current?.id === plan.id }"
          :to="{ path: '/travel/itineraries', query: { id: plan.id } }"
        >
          <strong>{{ plan.title }}</strong
          ><span
            >{{ plan.city }} · {{ plan.stops.length }} 站 ·
            {{ plan.summary.completed_stops }} 站完成</span
          >
        </router-link>
        <p v-if="!plans.length" class="muted">
          还没有行程。可以手动选择地点，也可以让旅伴生成。
        </p>
      </aside>
      <main>
        <section v-if="creating" class="panel">
          <small class="label">安排属于你的半天</small>
          <h2>先选城市，再选地点</h2>
          <div class="form-grid">
            <label
              >行程名称<input
                v-model="form.title"
                maxlength="100"
                :disabled="busy"
            /></label>
            <label
              >城市<input
                v-model="form.city"
                placeholder="例如：常州"
                :disabled="busy || selected.length > 0"
            /></label>
            <label
              >同行人数<input
                v-model.number="form.people"
                type="number"
                min="1"
                max="20"
                :disabled="busy"
            /></label>
            <label
              >多人总预算（元）<input
                v-model="form.budget_yuan"
                type="number"
                min="0"
                max="1000000"
                placeholder="可留空"
                :disabled="busy"
            /></label>
            <label
              >开始时间<input
                v-model="form.start_time"
                type="time"
                :disabled="busy"
            /></label>
            <label
              >结束时间<input
                v-model="form.end_time"
                type="time"
                :disabled="busy"
            /></label>
            <label
              >出行方式<select v-model="form.mode" :disabled="busy">
                <option value="walking">步行</option>
                <option value="driving">驾车</option>
              </select></label
            >
            <label
              >额外休息（分钟）<input
                v-model.number="form.rest_minutes"
                type="number"
                min="0"
                max="180"
                :disabled="busy"
            /></label>
          </div>
          <div
            v-for="(row, index) in selected"
            :key="row.place.poi_id"
            class="selected-stop"
          >
            <strong>{{ index + 1 }}. {{ row.place.name }}</strong>
            <label
              >停留分钟<input
                v-model.number="row.stay_minutes"
                type="number"
                min="5"
                max="480"
                :disabled="busy"
            /></label>
            <select v-model="row.kind" aria-label="地点用途" :disabled="busy">
              <option value="visit">游览</option>
              <option value="meal">用餐</option>
              <option value="rest">休息</option>
            </select>
            <button :disabled="busy" @click="selected.splice(index, 1)">
              移除
            </button>
          </div>
          <button
            class="primary"
            :disabled="busy || !selected.length"
            @click="save"
          >
            核对路线并保存行程
          </button>
        </section>

        <section v-else-if="current" class="panel">
          <div class="plan-heading">
            <div>
              <small class="label"
                >{{ current.city }} · {{ current.day_count || 1 }} 天 ·
                {{ current.people }} 人</small
              >
              <h2>{{ current.title }}</h2>
            </div>
            <router-link
              :to="{ path: '/travel', query: { itinerary: current.id } }"
              class="ask"
              >让旅伴调整 ↗</router-link
            >
          </div>
          <div class="metrics">
            <div>
              <strong
                >{{ current.summary.completed_stops }}/{{
                  current.stops.length
                }}</strong
              ><span>已完成地点</span>
            </div>
            <div>
              <strong>{{ current.summary.known_total_minutes }} 分钟</strong
              ><span>{{
                current.summary.time_estimate_complete
                  ? '预计安排时长'
                  : '已知时长，仍有缺口'
              }}</span>
            </div>
            <div>
              <strong>¥{{ current.summary.known_reference_total_yuan }}</strong
              ><span>已知参考费用小计</span>
            </div>
          </div>
          <p class="muted">
            总预算
            {{
              current.budget_yuan == null ? '未设置' : `¥${current.budget_yuan}`
            }}
            · {{ current.mode === 'walking' ? '步行' : '驾车' }} · 额外休息 每天
            {{ current.rest_minutes }} 分钟
          </p>
          <p v-if="current.preferences?.length" class="muted">
            本次偏好：{{ current.preferences.join('、') }}
          </p>
          <ItineraryDayOverview :plan="current" compact />
          <ol class="timeline">
            <li
              v-for="(stop, index) in current.stops"
              :key="stop.id"
              :class="{ completed: stop.completed }"
            >
              <h3
                v-if="
                  index === 0 ||
                  (current.stops[index - 1].day || 1) !== (stop.day || 1)
                "
                class="day-heading"
              >
                第 {{ stop.day || 1 }} 天
              </h3>
              <div class="stop-heading">
                <span class="number">{{
                  stop.completed ? '✓' : index + 1
                }}</span>
                <div>
                  <h3>{{ stop.place.name }}</h3>
                  <p>{{ stop.place.address }}</p>
                </div>
              </div>
              <p class="muted">
                {{ kindNames[stop.kind] }} · 建议停留
                {{ stop.stay_minutes }} 分钟 ·
                {{
                  stop.place.cost_yuan == null
                    ? '价格待确认'
                    : `参考人均 ¥${stop.place.cost_yuan}`
                }}
              </p>
              <div class="stop-actions">
                <a
                  v-if="navigationFor(stop.place, current.mode)"
                  :href="navigationFor(stop.place, current.mode)"
                  target="_blank"
                  rel="noopener noreferrer"
                  >高德导航 ↗</a
                >
                <template v-if="!stop.completed"
                  ><button
                    :disabled="
                      busy || index !== current.summary.completed_stops
                    "
                    @click="change('complete_stop', { stop_id: stop.id })"
                  >
                    标记已完成
                  </button>
                  <button :disabled="busy" @click="openReplacement(stop)">
                    换个地方
                  </button>
                  <button
                    :disabled="
                      busy ||
                      index <= current.summary.completed_stops ||
                      (current.stops[index - 1]?.day || 1) !== (stop.day || 1)
                    "
                    @click="
                      change('move_stop', {
                        stop_id: stop.id,
                        target_index: index - 1
                      })
                    "
                  >
                    上移
                  </button>
                  <button
                    :disabled="
                      busy ||
                      index === current.stops.length - 1 ||
                      (current.stops[index + 1]?.day || 1) !== (stop.day || 1)
                    "
                    @click="
                      change('move_stop', {
                        stop_id: stop.id,
                        target_index: index + 1
                      })
                    "
                  >
                    下移
                  </button>
                  <button
                    :disabled="busy || dayStopCount(stop) === 1"
                    @click="change('remove_stop', { stop_id: stop.id })"
                  >
                    删除此站
                  </button>
                  <label
                    >停留<input
                      type="number"
                      min="5"
                      max="480"
                      :value="stop.stay_minutes"
                      :disabled="busy"
                      @change="
                        change('update_stop', {
                          stop_id: stop.id,
                          stay_minutes: Number($event.target.value)
                        })
                      "
                    />分钟</label
                  > </template
                ><span v-else class="locked">已完成，保留原安排</span>
              </div>
              <VisitFeedbackForm
                v-if="stop.completed"
                :key="`${current.id}:${stop.id}`"
                :plan="current"
                :stop="stop"
                :disabled="busy"
                @saved="feedbackSaved"
                @conflict="feedbackRefreshed"
              />
              <p v-if="legFrom(stop)" class="leg">
                ↓
                {{ legFrom(stop).mode === 'walking' ? '步行' : '驾车' }}至下一站
                · {{ formatDistance(legFrom(stop).distance_m) }} ·
                {{ formatDuration(legFrom(stop).duration_s) }}
              </p>
            </li>
          </ol>
          <div class="warnings">
            <p v-for="warning in current.summary.warnings" :key="warning">
              {{ warning }}
            </p>
          </div>
          <details class="settings">
            <summary>修改预算、时间和出行方式</summary>
            <div class="form-grid">
              <label
                >名称<input
                  v-model="settings.title"
                  maxlength="100"
                  :disabled="busy"
              /></label>
              <label
                >多人总预算<input
                  v-model="settings.budget_yuan"
                  type="number"
                  min="0"
                  max="1000000"
                  :disabled="busy"
              /></label>
              <label
                >开始<input
                  v-model="settings.start_time"
                  type="time"
                  :disabled="busy" /></label
              ><label
                >结束<input
                  v-model="settings.end_time"
                  type="time"
                  :disabled="busy"
              /></label>
              <label
                >出行方式<select v-model="settings.mode" :disabled="busy">
                  <option value="walking">步行</option>
                  <option value="driving">驾车</option>
                </select></label
              >
              <label
                >额外休息（分钟）<input
                  v-model.number="settings.rest_minutes"
                  type="number"
                  min="0"
                  max="180"
                  :disabled="busy"
              /></label>
            </div>
            <button :disabled="busy" @click="saveSettings">
              保存并更新路线
            </button>
          </details>
          <div class="bottom-actions">
            <button :disabled="busy" @click="change('refresh_routes')">
              刷新剩余路线</button
            ><button :disabled="busy" @click="removePlan">删除行程</button>
          </div>
          <details class="muted">
            <summary>调整记录（最近 {{ current.changes.length }} 条）</summary>
            <p v-for="(item, index) in current.changes" :key="index">
              {{ new Date(item.at).toLocaleString() }} ·
              {{
                {
                  created: '创建行程',
                  complete_stop: '标记完成',
                  remove_stop: '删除地点',
                  move_stop: '调整顺序',
                  replace_stop: '替换地点',
                  update_stop: '调整停留',
                  update_plan: '调整安排',
                  refresh_routes: '刷新路线',
                  visit_feedback: '记录出行体验'
                }[item.action] || item.action
              }}
            </p>
          </details>
        </section>
        <section v-else class="panel empty">
          <h2>下一次出发，从这里开始</h2>
          <p>保存一份行程，换店、调整顺序或途中休息，都能接着安排。</p>
          <button class="primary" @click="newPlan">新建一份行程</button>
        </section>

        <section v-if="creating || replacing" class="panel search-panel">
          <h2>
            {{
              replacing ? `替换「${replacing.place.name}」` : '添加想去的地方'
            }}
          </h2>
          <p class="muted">
            查询范围：{{
              activeCity || '请先填写城市'
            }}。地点来自高德，与平台优惠券独立。
          </p>
          <form class="search-form" @submit.prevent="find">
            <input
              v-model="search"
              maxlength="100"
              placeholder="餐馆、咖啡馆、公园…"
              :disabled="busy"
            /><button :disabled="busy || searching">
              {{ searching ? '查询中…' : '搜索地点' }}
            </button>
          </form>
          <button v-if="replacing" :disabled="busy" @click="replacing = null">
            取消替换
          </button>
          <article
            v-for="place in results"
            :key="place.poi_id"
            class="search-result"
          >
            <div>
              <strong>{{ place.name }}</strong>
              <p>{{ place.address }}</p>
            </div>
            <button
              :disabled="busy"
              @click="
                replacing
                  ? change('replace_stop', {
                      stop_id: replacing.id,
                      replacement: {
                        poi_id: place.poi_id,
                        stay_minutes: replacing.stay_minutes,
                        kind: replacing.kind
                      }
                    })
                  : add(place)
              "
            >
              {{ replacing ? '换成这里' : '加入行程' }}
            </button>
          </article>
          <p v-if="!searching && search && !results.length" class="muted">
            搜索后在这里选择准确地点。
          </p>
        </section>
      </main>
    </div>
    <FootBar :active-btn="2" />
  </div>
</template>

<style scoped>
.itinerary-page {
  min-height: 100vh;
  padding: 24px max(20px, calc((100vw - 1080px) / 2)) 110px;
  background: var(--tp-surface-soft);
  color: var(--tp-ink);
}
header,
.top-actions,
.plan-heading,
.stop-heading,
.search-form,
.search-result,
.bottom-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
header a {
  color: var(--tp-ink);
  text-decoration: none;
}
header span,
.label {
  font-size: 10px;
  letter-spacing: 1.4px;
  color: var(--tp-muted);
}
.intro {
  margin: 45px 0 28px;
}
.intro small {
  color: var(--tp-muted);
}
h1 {
  font-size: 38px;
  margin: 10px 0;
  font-weight: 600;
}
.intro p {
  color: var(--tp-muted);
  font-size: 14px;
}
.top-actions {
  justify-content: flex-start;
  margin-bottom: 24px;
}
button,
.ask {
  border: 1px solid var(--tp-line);
  border-radius: 8px;
  background: #fffdf9;
  padding: 9px 13px;
  color: var(--tp-ink);
  font-size: 12px;
  cursor: pointer;
  text-decoration: none;
}
button:disabled {
  opacity: 0.45;
  cursor: default;
}
.primary {
  background: var(--tp-ink);
  color: white;
  border-color: var(--tp-line);
  margin-top: 18px;
}
.layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 24px;
}
aside > a {
  display: block;
  padding: 18px 14px;
  margin: 8px 0;
  color: inherit;
  border: 1px solid transparent;
  text-decoration: none;
  border-radius: 12px;
}
aside a.active {
  background: var(--tp-surface-soft);
  border-color: var(--tp-line);
}
aside strong {
  display: block;
  font-size: 14px;
  margin-bottom: 9px;
}
aside span {
  font-size: 11px;
  color: var(--tp-muted);
}
.panel {
  background: #fffdf9;
  border: 1px solid var(--tp-line);
  border-radius: 18px;
  padding: 26px;
  margin-bottom: 20px;
}
h2 {
  font-size: 21px;
  margin: 10px 0 24px;
}
h3 {
  font-size: 16px;
  margin: 0 0 6px;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding: 22px 0;
  border-top: 1px solid var(--tp-line);
  border-bottom: 1px solid var(--tp-line);
}
.metrics strong,
.metrics span {
  display: block;
}
.metrics strong {
  font-size: 19px;
  color: var(--tp-ink);
}
.metrics span {
  font-size: 10px;
  color: var(--tp-muted);
  margin-top: 8px;
}
.muted,
.stop-heading p {
  font-size: 12px;
  line-height: 1.8;
  color: var(--tp-muted);
}
.timeline {
  padding: 0;
  list-style: none;
}
.timeline > li {
  padding-top: 24px;
}
.stop-heading {
  justify-content: flex-start;
}
.stop-heading p {
  margin: 0;
}
.number {
  min-width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  background: var(--tp-surface-soft);
  border-radius: 50%;
  color: var(--tp-ink);
}
.completed h3 {
  color: var(--tp-muted);
}
.stop-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.stop-actions button {
  font-size: 11px;
  padding: 7px 9px;
}
.stop-actions a {
  color: var(--tp-muted);
  font-size: 12px;
}
.stop-actions label {
  font-size: 11px;
}
.stop-actions input {
  width: 58px;
  margin: 0 5px;
}
.locked {
  font-size: 11px;
  color: var(--tp-muted);
}
.leg {
  margin: 18px 0 0 16px;
  padding: 14px 0 0 17px;
  border-left: 1px dashed var(--tp-line);
  font-size: 12px;
  color: var(--tp-muted);
}
.warnings {
  margin: 28px 0 18px;
  padding: 12px 16px;
  border-radius: 10px;
  background: #faf0e5;
  font-size: 11px;
  line-height: 1.7;
  color: #9c7858;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin: 18px 0;
}
label {
  display: block;
  font-size: 12px;
  color: var(--tp-muted);
}
input,
select {
  box-sizing: border-box;
  display: block;
  width: 100%;
  margin-top: 6px;
  padding: 10px;
  border: 1px solid var(--tp-line);
  border-radius: 7px;
  background: white;
  color: var(--tp-ink);
}
.selected-stop {
  padding: 15px 0;
  border-top: 1px solid var(--tp-line);
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}
.selected-stop strong {
  flex: 1;
  min-width: 160px;
  font-size: 13px;
}
.selected-stop label {
  width: 85px;
}
.selected-stop select {
  width: 80px;
}
.search-panel h2 {
  font-size: 18px;
  margin-bottom: 12px;
}
.search-form input {
  margin-top: 0;
  flex: 1;
}
.search-result {
  padding: 16px 0;
  border-bottom: 1px solid var(--tp-line);
}
.search-result strong {
  font-size: 14px;
}
.search-result p {
  font-size: 11px;
  color: var(--tp-muted);
}
.settings {
  margin: 20px 0;
  font-size: 12px;
}
summary {
  cursor: pointer;
}
.bottom-actions {
  margin: 20px 0;
}
.empty {
  text-align: center;
  padding: 60px 24px;
}
.empty p {
  font-size: 13px;
  line-height: 1.8;
  color: var(--tp-muted);
}
.error,
.notice {
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.7;
}
.error {
  background: #fae7df;
  color: #b15e40;
}
.notice {
  background: #eaf0e3;
  color: #5c754e;
}
@media (max-width: 720px) {
  .layout {
    display: block;
  }
  aside {
    display: flex;
    overflow-x: auto;
    gap: 8px;
    margin-bottom: 16px;
  }
  aside > a {
    min-width: 150px;
  }
  aside > .label {
    display: none;
  }
  .panel {
    padding: 18px;
  }
  .intro {
    margin: 30px 0 20px;
  }
  .metrics strong {
    font-size: 16px;
  }
  .form-grid {
    gap: 10px;
  }
  .plan-heading {
    align-items: flex-start;
  }
  header span {
    display: none;
  }
}
</style>
