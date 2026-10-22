<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useTravelStore } from '@/stores/modules/travel'
import { searchPlaces } from '@/api/travel'
import {
  workshop,
  workTemplate,
  stopTemplate,
  navigationUrl
} from '@/api/workshop'

const route = useRoute(),
  travel = useTravelStore()
const city = ref(travel.selectedCity || '南京')
const theme = ref(route.query.theme === 'PLAY' ? 'PLAY' : 'FOOD')
const tab = ref('discover'),
  page = ref(1),
  works = ref([]),
  trips = ref([])
const selected = ref(null),
  feedback = ref([]),
  editor = ref(null),
  editId = ref(null)
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  feedbackForm = ref(null)
const placeResults = ref([]),
  placeIndex = ref(null)
const labels = {
  WORTH: '值得专程来',
  OK: '顺路可以',
  AVOID: '不太推荐',
  CORRECTION: '信息纠错 · 待核实'
}
const clone = (value) => JSON.parse(JSON.stringify(value))
const total = (stops, key) =>
  stops.reduce((sum, stop) => sum + Number(stop[key] || 0), 0)
const heading = computed(
  () =>
    ({
      discover: '跟着熟悉这座城的人出发',
      mine: '我的吃玩作品',
      saved: '留给下次出发',
      trips: '我的出行'
    })[tab.value]
)
async function run(action) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await action()
  } catch (e) {
    error.value = e.message || '操作失败，请稍后重试'
  } finally {
    busy.value = false
  }
}
async function load() {
  if (tab.value === 'trips') trips.value = await workshop('/trips')
  else
    works.value = await workshop(
      tab.value === 'discover'
        ? `/works?city=${encodeURIComponent(city.value.trim())}&theme=${theme.value}&page=${page.value}`
        : `/${tab.value}`
    )
}
function switchTab(value) {
  run(async () => {
    tab.value = value
    page.value = 1
    selected.value = null
    editor.value = null
    works.value = []
    await load()
  })
}
function search() {
  run(async () => {
    page.value = 1
    selected.value = null
    await load()
  })
}
function open(work) {
  run(async () => {
    const latest = await workshop(`/works/${work.id}`)
    const notes = await workshop(`/works/${work.id}/feedback`)
    selected.value = latest
    feedback.value = notes
  })
}
function startEdit(work, remix = false) {
  if (busy.value) return
  error.value = ''
  selected.value = null
  placeResults.value = []
  placeIndex.value = null
  editId.value = remix ? null : work?.id || null
  editor.value = work ? clone(work.content) : workTemplate(city.value)
  if (!work) editor.value.theme = theme.value
  editor.value.version = work?.version || 0
  if (remix) {
    editor.value.sourceId = work.id
    editor.value.title += ' · 我的版本'
    editor.value.status = 'DRAFT'
    editor.value.changeNote = ''
    editor.value.version = 0
  }
}
function saveWork(status) {
  run(async () => {
    const payload = { ...editor.value, status }
    const result = await workshop(
      editId.value ? `/works/${editId.value}` : '/works',
      editId.value ? 'put' : 'post',
      payload
    )
    editor.value = null
    tab.value = 'mine'
    await load()
    selected.value = result
    feedback.value = await workshop(`/works/${result.id}/feedback`)
    notice.value =
      status === 'DRAFT'
        ? '草稿已保存，仅自己可见。'
        : '作品已发布，其他旅行者可以使用了。'
  })
}
function saveFavorite(id, remove = false) {
  run(async () => {
    await workshop(`/works/${id}/saved`, remove ? 'delete' : 'put')
    notice.value = remove ? '已取消收藏' : '已收藏'
    if (tab.value === 'saved') await load()
  })
}
function join(id) {
  run(async () => {
    await workshop(`/works/${id}/trips`, 'post')
    selected.value = null
    tab.value = 'trips'
    await load()
    notice.value = '行程已保存。重复加入会保留之前的进度和调整。'
  })
}
async function putTrip(trip, stops, completed) {
  const result = await workshop(`/trips/${trip.id}`, 'put', {
    stops,
    completed,
    version: trip.version
  })
  trips.value = trips.value.map((t) => (t.id === trip.id ? result : t))
}
function checkIn(trip, index) {
  run(() => putTrip(trip, trip.stops, [...new Set([...trip.completed, index])]))
}
function move(trip, index, delta) {
  run(async () => {
    const stops = clone(trip.stops)
    ;[stops[index], stops[index + delta]] = [stops[index + delta], stops[index]]
    await putTrip(trip, stops, [])
  })
}
function removeStop(trip, index) {
  run(() =>
    putTrip(
      trip,
      trip.stops.filter((_, i) => i !== index),
      []
    )
  )
}
function submitFeedback() {
  run(async () => {
    await workshop('/feedback', 'post', feedbackForm.value)
    feedbackForm.value = null
    notice.value = '反馈已保存。同一站再次反馈会更新原记录。'
  })
}
function findPlace(index) {
  run(async () => {
    placeIndex.value = index
    placeResults.value = []
    const result = await searchPlaces(
      editor.value.city,
      editor.value.stops[index].name
    )
    placeResults.value = result.places || []
    if (!placeResults.value.length)
      notice.value = '未找到地点，请调整关键词或手动填写。'
  })
}
function choosePlace(place) {
  const stop = editor.value.stops[placeIndex.value]
  const [lng, lat] = place.location.split(',').map(Number)
  Object.assign(stop, {
    name: place.name,
    address: place.address || place.name,
    longitude: lng,
    latitude: lat
  })
  placeResults.value = []
  placeIndex.value = null
}
function removeEditorStop(index) {
  editor.value.stops.splice(index, 1)
  placeResults.value = []
  placeIndex.value = null
}
onMounted(() => run(load))
</script>

<template>
  <main class="workshop" :aria-busy="busy">
    <header class="top">
      <router-link to="/index">← 首页</router-link
      ><strong>旅伴 · 城市吃玩工坊</strong
      ><button :disabled="busy" @click="startEdit()">＋ 发布推荐</button>
    </header>
    <section class="hero">
      <span class="eyebrow">由旅行者一起丰富的城市指南</span>
      <h1>这一城，跟着你去吃玩。</h1>
      <p>分享一家舍不得藏的店，也分享一条值得慢慢走的路。</p>
    </section>
    <nav aria-label="工坊导航">
      <button
        v-for="(label, key) in {
          discover: '发现吃玩',
          saved: '我的收藏',
          trips: '我的出行',
          mine: '我的作品'
        }"
        :key="key"
        :class="{ active: tab === key }"
        :disabled="busy"
        @click="switchTab(key)"
      >
        {{ label }}
      </button>
    </nav>
    <p v-if="error" role="alert" class="error">
      {{ error }} <button :disabled="busy" @click="run(load)">重试</button>
      <router-link v-if="error.includes('登录')" to="/login"
        >前往登录</router-link
      >
    </p>
    <p v-if="notice" role="status" class="notice">{{ notice }}</p>
    <p v-if="busy" role="status">正在处理…</p>

    <form
      v-if="editor"
      class="panel editor"
      @submit.prevent="saveWork('PUBLISHED')"
    >
      <div class="row">
        <h2>
          {{
            editId
              ? '编辑作品'
              : editor.sourceId
                ? '创作我的版本'
                : '分享我的城市经验'
          }}
        </h2>
        <button
          type="button"
          class="quiet"
          :disabled="busy"
          @click="editor = null"
        >
          取消
        </button>
      </div>
      <p>一个站点就是单点推荐，多个站点组成路线。费用与时间均为你的估计。</p>
      <label
        >作品名称<input
          v-model.trim="editor.title"
          required
          maxlength="80"
          placeholder="例如：老城里的早餐与半日漫步"
      /></label>
      <div class="fields">
        <label
          >城市<input
            v-model.trim="editor.city"
            required
            maxlength="40" /></label
        ><label
          >主线<select v-model="editor.theme">
            <option value="FOOD">本地人带吃</option>
            <option value="PLAY">本地人带玩</option>
          </select></label
        >
      </div>
      <label
        >推荐理由<textarea
          v-model.trim="editor.description"
          required
          maxlength="2000"
          placeholder="这份吃法或玩法有什么特别之处？"
        />
      </label>
      <label
        >适合谁<input
          v-model.trim="editor.audience"
          maxlength="100"
          placeholder="第一次来 / 朋友出游 / 喜欢慢逛"
      /></label>
      <label v-if="editor.sourceId"
        >改编说明<input
          v-model.trim="editor.changeNote"
          required
          maxlength="300"
          placeholder="说明替换了哪些站点、为什么调整"
      /></label>
      <label class="check"
        ><input
          v-model="editor.allowRemix"
          type="checkbox"
        />允许其他用户署名改编</label
      >
      <fieldset v-for="(stop, i) in editor.stops" :key="i">
        <legend>第 {{ i + 1 }} 站</legend>
        <div class="fields">
          <label
            >地点名称<input
              v-model.trim="stop.name"
              required
              maxlength="80" /></label
          ><label
            >类型<select v-model="stop.kind">
              <option value="FOOD">吃美食</option>
              <option value="PLAY">逛景点</option>
            </select></label
          >
        </div>
        <button
          type="button"
          class="quiet"
          :disabled="busy || !stop.name || !editor.city"
          @click="findPlace(i)"
        >
          搜索地点并填入地址
        </button>
        <div
          v-if="placeIndex === i && placeResults.length"
          class="place-results"
        >
          <button
            v-for="place in placeResults"
            :key="place.poi_id"
            type="button"
            class="quiet"
            @click="choosePlace(place)"
          >
            {{ place.name }} · {{ place.address }}
          </button>
        </div>
        <label
          >详细地址<input v-model.trim="stop.address" required maxlength="200"
        /></label>
        <label
          >怎么吃 / 怎么玩<textarea
            v-model.trim="stop.advice"
            required
            maxlength="1000"
            placeholder="必点菜、游览顺序、入口或其他亲测建议"
          />
        </label>
        <div class="fields">
          <label
            >高德经度<input
              v-model.number="stop.longitude"
              type="number"
              min="-180"
              max="180"
              step="any"
              required /></label
          ><label
            >高德纬度<input
              v-model.number="stop.latitude"
              type="number"
              min="-90"
              max="90"
              step="any"
              required
          /></label>
        </div>
        <small>选择搜索结果可自动填写坐标，用于导航。</small>
        <div class="fields">
          <label
            >停留分钟<input
              v-model.number="stop.minutes"
              type="number"
              min="5"
              max="1440"
              required /></label
          ><label
            >人均费用（元）<input
              v-model.number="stop.cost"
              type="number"
              min="0"
              max="100000"
              step="0.01"
              required
          /></label>
        </div>
        <button
          v-if="editor.stops.length > 1"
          type="button"
          class="quiet"
          :disabled="busy"
          @click="removeEditorStop(i)"
        >
          移除本站
        </button>
      </fieldset>
      <button
        type="button"
        :disabled="busy || editor.stops.length >= 20"
        class="quiet"
        @click="editor.stops.push(stopTemplate())"
      >
        ＋ 添加一站
      </button>
      <p>
        共 {{ editor.stops.length }} 站 · 预计人均 ¥{{
          total(editor.stops, 'cost')
        }}
        · 停留 {{ total(editor.stops, 'minutes') }} 分钟（不含交通）
      </p>
      <div class="actions">
        <button
          type="button"
          :disabled="busy"
          class="quiet"
          @click="saveWork('DRAFT')"
        >
          保存草稿 / 撤回公开</button
        ><button type="submit" :disabled="busy">发布作品</button>
      </div>
    </form>

    <section v-else-if="selected" class="panel detail">
      <button class="quiet" :disabled="busy" @click="selected = null">
        ← 返回列表
      </button>
      <p class="eyebrow">
        {{ selected.content.city }} ·
        {{ selected.content.theme === 'FOOD' ? '本地人带吃' : '本地人带玩' }}
      </p>
      <h2>{{ selected.content.title }}</h2>
      <p>
        由 {{ selected.authorName }} 分享 · 版本 {{ selected.version + 1 }} ·
        {{ selected.updatedAt }}
      </p>
      <p>{{ selected.content.description }}</p>
      <p>
        {{ selected.content.audience || '适合对这座城市好奇的你' }} · 人均约 ¥{{
          total(selected.content.stops, 'cost')
        }}
        · 停留约 {{ total(selected.content.stops, 'minutes') }} 分钟，不含交通
      </p>
      <p v-if="selected.content.sourceId">
        改编自
        <button
          class="quiet"
          :disabled="busy"
          @click="open({ id: selected.content.sourceId })"
        >
          查看原作品
        </button>
        · {{ selected.content.changeNote
        }}<small>来源撤回后可能无法查看。</small>
      </p>
      <article
        v-for="(stop, i) in selected.content.stops"
        :key="i"
        class="stop"
      >
        <span class="number">{{ i + 1 }}</span>
        <div>
          <h3>{{ stop.name }}</h3>
          <p>{{ stop.address }}</p>
          <p>{{ stop.advice }}</p>
          <small>{{ stop.minutes }} 分钟 · 约 ¥{{ stop.cost }}</small
          ><a
            :href="navigationUrl(stop)"
            target="_blank"
            rel="noopener noreferrer"
            >高德导航 ↗</a
          >
        </div>
      </article>
      <div v-if="selected.content.status === 'PUBLISHED'" class="actions">
        <button :disabled="busy" @click="join(selected.id)">加入我的出行</button
        ><button
          :disabled="busy"
          class="quiet"
          @click="saveFavorite(selected.id)"
        >
          收藏</button
        ><button
          v-if="selected.content.allowRemix"
          :disabled="busy"
          class="quiet"
          @click="startEdit(selected, true)"
        >
          改编成我的版本
        </button>
      </div>
      <h3>去过的人怎么说</h3>
      <p>
        <small
          >反馈来自用户自行标记的到访；个人行程可能调整过站点。纠错尚未经平台核实。</small
        >
      </p>
      <p v-if="!feedback.length">还没有反馈，体验后回来补充第一条吧。</p>
      <article v-for="note in feedback" :key="note.id" class="feedback">
        <strong>{{ note.stopName }} · {{ labels[note.verdict] }}</strong>
        <p>{{ note.note || '用户留下了体验判断' }}</p>
        <small
          >{{ note.authorName }} · {{ note.createdAt
          }}<span v-if="note.actualCost != null">
            · 实际花费 ¥{{ note.actualCost }}</span
          ></small
        >
      </article>
    </section>

    <section v-else>
      <div class="row">
        <h2>{{ heading }}</h2>
        <span v-if="tab !== 'discover'" class="muted">最近 100 条</span>
      </div>
      <form v-if="tab === 'discover'" class="filters" @submit.prevent="search">
        <label
          >目的地<input
            v-model.trim="city"
            required
            maxlength="40"
            placeholder="例如南京" /></label
        ><label
          >想体验<select v-model="theme">
            <option value="FOOD">本地人带吃</option>
            <option value="PLAY">本地人带玩</option>
          </select></label
        ><button :disabled="busy">寻找灵感</button>
      </form>
      <template v-if="tab === 'trips'">
        <article v-for="trip in trips" :key="trip.id" class="panel">
          <h3>{{ trip.snapshot.content.title }}</h3>
          <p>
            来自 {{ trip.snapshot.authorName }} · 已去过
            {{ trip.completed.length }}/{{ trip.stops.length }} 站 ·
            使用时的版本 {{ trip.snapshot.version + 1 }}
          </p>
          <p class="muted">
            开始打卡前可调整顺序或移除站点；打卡后保留站点与反馈的对应关系。
          </p>
          <article v-for="(stop, i) in trip.stops" :key="i" class="stop">
            <span class="number">{{ i + 1 }}</span>
            <div>
              <h4>{{ stop.name }}</h4>
              <p>{{ stop.advice }}</p>
              <small>{{ stop.address }}</small>
              <div class="actions">
                <a
                  :href="navigationUrl(stop)"
                  target="_blank"
                  rel="noopener noreferrer"
                  >去这里 ↗</a
                ><button
                  v-if="!trip.completed.includes(i)"
                  :disabled="busy"
                  @click="checkIn(trip, i)"
                >
                  标记去过</button
                ><button
                  v-else
                  class="quiet"
                  :disabled="busy"
                  @click="
                    feedbackForm = {
                      tripId: trip.id,
                      stopIndex: i,
                      verdict: 'WORTH',
                      note: '',
                      actualCost: null
                    }
                  "
                >
                  已去过 · 留反馈</button
                ><template v-if="!trip.completed.length"
                  ><button
                    :disabled="busy || i === 0"
                    class="quiet"
                    @click="move(trip, i, -1)"
                  >
                    ↑</button
                  ><button
                    :disabled="busy || i === trip.stops.length - 1"
                    class="quiet"
                    @click="move(trip, i, 1)"
                  >
                    ↓</button
                  ><button
                    v-if="trip.stops.length > 1"
                    :disabled="busy"
                    class="quiet"
                    @click="removeStop(trip, i)"
                  >
                    移除
                  </button></template
                >
              </div>
            </div>
          </article>
        </article>
        <div v-if="!trips.length && !busy && !error" class="empty">
          还没有行程。在“发现吃玩”中选一份喜欢的作品，加入出行。
        </div>
      </template>
      <template v-else>
        <div class="grid">
          <article v-for="work in works" :key="work.id" class="card">
            <span class="tag"
              >{{ work.content.theme === 'FOOD' ? '本地人带吃' : '本地人带玩' }}
              ·
              {{
                work.content.stops.length === 1
                  ? '单点推荐'
                  : `${work.content.stops.length} 站路线`
              }}</span
            >
            <h3>
              <button class="title" :disabled="busy" @click="open(work)">
                {{ work.content.title }}
              </button>
            </h3>
            <p class="summary">{{ work.content.description }}</p>
            <p class="muted">{{ work.content.city }} · {{ work.authorName }}</p>
            <div class="metrics">
              <span>约 ¥{{ total(work.content.stops, 'cost') }}/人</span
              ><span>{{ total(work.content.stops, 'minutes') }} 分钟停留</span>
            </div>
            <div class="actions">
              <button :disabled="busy" @click="open(work)">看看怎么走 →</button
              ><button
                v-if="tab === 'mine'"
                :disabled="busy"
                class="quiet"
                @click="startEdit(work)"
              >
                {{
                  work.content.status === 'DRAFT' ? '继续编辑草稿' : '编辑'
                }}</button
              ><button
                v-if="tab === 'saved'"
                :disabled="busy"
                class="quiet"
                @click="saveFavorite(work.id, true)"
              >
                取消收藏
              </button>
            </div>
          </article>
        </div>
        <div v-if="!works.length && !busy && !error" class="empty">
          <h3>这里还等着一位城市分享者</h3>
          <p>把你熟悉的一家店、一个景点，变成别人的出发灵感。</p>
          <button @click="startEdit()">发布第一份推荐</button>
        </div>
        <div v-if="tab === 'discover'" class="actions pagination">
          <button
            :disabled="busy || page <= 1"
            class="quiet"
            @click="
              run(async () => {
                page--
                await load()
              })
            "
          >
            上一页</button
          ><span>第 {{ page }} 页</span
          ><button
            :disabled="busy || works.length < 20 || page >= 500"
            class="quiet"
            @click="
              run(async () => {
                page++
                await load()
              })
            "
          >
            下一页
          </button>
        </div>
      </template>
    </section>
    <div v-if="feedbackForm" class="overlay">
      <form
        class="panel feedback-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="留下到访反馈"
        @submit.prevent="submitFeedback"
      >
        <h2>这站体验怎么样？</h2>
        <label
          >你的感受<select v-model="feedbackForm.verdict">
            <option v-for="(label, key) in labels" :key="key" :value="key">
              {{ label }}
            </option>
          </select></label
        ><label
          >补充一句<textarea
            v-model.trim="feedbackForm.note"
            :required="feedbackForm.verdict === 'CORRECTION'"
            maxlength="1000"
            placeholder="推荐吃法，或需要纠正的信息"
          /></label
        ><label
          >实际花费（选填）<input
            v-model.number="feedbackForm.actualCost"
            type="number"
            min="0"
            max="100000"
            step="0.01"
            @change="
              feedbackForm.actualCost =
                feedbackForm.actualCost === '' ? null : feedbackForm.actualCost
            "
        /></label>
        <p v-if="error" role="alert" class="error">{{ error }}</p>
        <div class="actions">
          <button :disabled="busy">保存反馈</button
          ><button
            type="button"
            class="quiet"
            :disabled="busy"
            @click="feedbackForm = null"
          >
            取消
          </button>
        </div>
      </form>
    </div>
  </main>
</template>

<style scoped>
.workshop {
  --green: var(--tp-ink);
  --ink: var(--tp-ink);
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 24px 80px;
  color: var(--ink);
  background: #f6f9f3;
  min-height: 100vh;
  font-family: system-ui, sans-serif;
  box-sizing: border-box;
}
.top,
.row,
.actions,
.metrics {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.top {
  flex-wrap: wrap;
}
.hero {
  padding: 48px 24px 36px;
  background: var(--tp-surface-soft);
  border-radius: 24px;
  margin-top: 24px;
}
.eyebrow {
  color: var(--tp-ink);
  font-size: 13px;
  letter-spacing: 2px;
}
h1 {
  font-size: clamp(26px, 4vw, 42px);
  margin: 14px 0;
  font-weight: 700;
}
h2 {
  font-size: 24px;
}
h3,
h4 {
  margin: 12px 0;
}
p {
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
button,
a,
input,
select,
textarea {
  font: inherit;
}
button {
  border: 1px solid transparent;
  border-radius: 10px;
  background: var(--green);
  color: white;
  padding: 10px 16px;
  cursor: pointer;
}
button:disabled {
  opacity: 0.45;
  cursor: wait;
}
button.quiet {
  background: var(--tp-surface-soft);
  color: var(--green);
}
button.title {
  padding: 0;
  background: none;
  color: var(--ink);
  text-align: left;
  font-size: 21px;
  font-weight: 650;
}
a {
  color: var(--green);
  display: inline-block;
  margin: 8px 12px 8px 0;
}
nav {
  display: flex;
  gap: 8px;
  margin: 24px 0;
  flex-wrap: wrap;
}
nav button {
  background: transparent;
  color: var(--tp-ink);
}
nav button.active {
  background: var(--green);
  color: white;
}
.filters,
.fields {
  display: flex;
  gap: 16px;
  align-items: end;
}
.filters {
  margin: 20px 0 28px;
}
.filters label,
.fields label {
  flex: 1;
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}
.card,
.panel {
  background: #fff;
  border: 1px solid var(--tp-line);
  border-radius: 18px;
  padding: 24px;
  margin-bottom: 18px;
}
.card {
  display: flex;
  flex-direction: column;
}
.card .actions {
  margin-top: auto;
  padding-top: 20px;
  flex-wrap: wrap;
}
.tag {
  font-size: 12px;
  color: var(--tp-ink);
}
.summary {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.muted,
small {
  color: var(--tp-muted);
  font-size: 13px;
}
.metrics {
  font-size: 14px;
  border-top: 1px solid var(--tp-line);
  padding-top: 14px;
}
.stop {
  display: flex;
  gap: 16px;
  padding: 18px 0;
  border-bottom: 1px solid var(--tp-line);
}
.stop > div {
  flex: 1;
  min-width: 0;
}
.number {
  background: var(--tp-surface-soft);
  border-radius: 50%;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  text-align: center;
  line-height: 32px;
  color: var(--green);
}
.actions {
  justify-content: flex-start;
  flex-wrap: wrap;
  margin-top: 14px;
}
.empty {
  text-align: center;
  padding: 55px 20px;
  background: var(--tp-surface-soft);
  border-radius: 18px;
}
.pagination {
  justify-content: center;
}
.error {
  background: #fff0eb;
  color: #a23f29;
  padding: 14px;
  border-radius: 10px;
}
.notice {
  background: #e3f3df;
  padding: 14px;
  border-radius: 10px;
}
label {
  display: block;
  margin: 14px 0;
  font-size: 14px;
}
input,
select,
textarea {
  display: block;
  box-sizing: border-box;
  width: 100%;
  padding: 11px;
  margin-top: 7px;
  border: 1px solid var(--tp-line);
  border-radius: 8px;
  background: white;
  color: var(--ink);
}
textarea {
  min-height: 90px;
  resize: vertical;
}
.check {
  display: flex;
  align-items: center;
  gap: 8px;
}
.check input {
  width: auto;
  margin: 0;
}
fieldset {
  border: 1px solid var(--tp-line);
  border-radius: 12px;
  margin: 24px 0;
  padding: 16px;
}
legend {
  padding: 0 8px;
}
.feedback {
  padding: 15px;
  background: var(--tp-surface-soft);
  border-radius: 12px;
  margin: 12px 0;
}
.overlay {
  position: fixed;
  inset: 0;
  background: #292c2890;
  display: grid;
  place-items: center;
  padding: 20px;
  z-index: 1000;
}
.feedback-dialog {
  width: min(460px, 90vw);
  max-height: 85vh;
  overflow: auto;
}
.detail > p {
  max-width: 850px;
}
.place-results button {
  display: block;
  margin: 8px 0;
  text-align: left;
}
button:focus-visible,
a:focus-visible {
  outline: 3px solid var(--tp-ink);
  outline-offset: 3px;
}
@media (max-width: 650px) {
  .workshop {
    padding: 16px 14px 70px;
  }
  .grid {
    grid-template-columns: 1fr;
  }
  .filters {
    flex-wrap: wrap;
  }
  .filters label {
    min-width: 40%;
  }
  .fields {
    flex-wrap: wrap;
  }
  .fields label {
    min-width: 40%;
  }
  .panel,
  .card {
    padding: 18px;
  }
  .hero {
    padding: 30px 20px;
  }
  .top strong {
    font-size: 14px;
  }
  .top button {
    padding: 8px;
  }
  .stop .actions {
    gap: 6px;
  }
}
</style>
