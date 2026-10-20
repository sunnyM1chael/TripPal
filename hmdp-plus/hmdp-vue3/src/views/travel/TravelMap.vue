<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Location, RefreshRight } from '@element-plus/icons-vue'
import CityPicker from '@/components/CityPicker.vue'
import { useTravelStore } from '@/stores/modules/travel'
import { searchPlaces, placeDetail, planMapRoute } from '@/api/travel'
import {
  navigationFor,
  safeMapUrl,
  formatDistance,
  formatDuration
} from '@/utils/maps'

const chat = useTravelStore()
const route = useRoute()
const router = useRouter()
const cityOpen = ref(false)
const keyword = ref('')
const field = ref('destination')
const origin = ref(null)
const destination = ref(null)
const mode = ref(route.query.mode === 'walking' ? 'walking' : 'driving')
const places = ref([])
const result = ref(null)
const pending = ref(false)
const error = ref('')
const previewFailed = ref(false)
let searchVersion = 0
const navigation = computed(() =>
  result.value
    ? safeMapUrl(result.value.navigation_url)
    : navigationFor(destination.value, mode.value)
)
const preview = computed(() =>
  result.value?.preview_url?.startsWith('/agent-api/api/v1/maps/preview?')
    ? result.value.preview_url
    : ''
)

function invalidate() {
  result.value = null
  error.value = ''
  previewFailed.value = false
}
function setMode(value) {
  mode.value = value
  invalidate()
}
function cityChanged() {
  searchVersion++
  places.value = []
  keyword.value = ''
  origin.value = null
  destination.value = null
  invalidate()
}
async function search() {
  if (!keyword.value.trim() || pending.value) return
  if (!chat.selectedCity) {
    cityOpen.value = true
    error.value = '请先选择城市。'
    return
  }
  const turn = ++searchVersion
  pending.value = true
  error.value = ''
  try {
    const data = await searchPlaces(chat.selectedCity, keyword.value.trim())
    if (turn === searchVersion) places.value = data.places
  } catch (err) {
    if (turn === searchVersion) error.value = err.message
  } finally {
    pending.value = false
  }
}
function select(place) {
  if (field.value === 'origin') origin.value = place
  else destination.value = place
  places.value = []
  keyword.value = ''
  invalidate()
}
async function calculate() {
  if (!origin.value || !destination.value || pending.value) return
  pending.value = true
  error.value = ''
  previewFailed.value = false
  try {
    result.value = await planMapRoute({
      origin_poi_id: origin.value.poi_id,
      destination_poi_id: destination.value.poi_id,
      mode: mode.value
    })
  } catch (err) {
    error.value = err.message
    result.value = null
  } finally {
    pending.value = false
  }
}
function askTravel() {
  const names = [origin.value?.name, destination.value?.name]
    .filter(Boolean)
    .join('到')
  chat.draft = `我想在${chat.selectedCity || '这个城市'}从${names || '已选地点'}出行，请帮我规划探店安排。`
  router.push('/travel')
}
onMounted(async () => {
  await chat.initialize()
  if (typeof route.query.city === 'string' && route.query.city.length <= 40)
    chat.selectedCity = route.query.city
  try {
    if (/^[A-Za-z0-9_-]{5,40}$/.test(route.query.origin || ''))
      origin.value = await placeDetail(route.query.origin)
    if (/^[A-Za-z0-9_-]{5,40}$/.test(route.query.destination || ''))
      destination.value = await placeDetail(route.query.destination)
    if (origin.value && destination.value) await calculate()
  } catch (err) {
    error.value = err.message
  }
})
</script>
<template>
  <div class="travel-map-page">
    <header>
      <button
        type="button"
        aria-label="返回旅伴"
        @click="router.push('/travel')"
      >
        <el-icon><ArrowLeft /></el-icon>
      </button>
      <h1>城市与地图出行</h1>
      <button type="button" class="city-toggle" @click="cityOpen = true">
        <el-icon><Location /></el-icon>{{ chat.selectedCity || '选城市' }}
      </button>
    </header>
    <main>
      <section class="route-search">
        <div class="mode-tabs">
          <button
            :class="{ selected: mode === 'driving' }"
            :disabled="pending"
            @click="setMode('driving')"
          >
            驾车</button
          ><button
            :class="{ selected: mode === 'walking' }"
            :disabled="pending"
            @click="setMode('walking')"
          >
            步行
          </button>
        </div>
        <div class="point-fields">
          <button
            type="button"
            :class="{ focused: field === 'origin' }"
            @click="field = 'origin'"
          >
            <i class="origin-dot"></i
            ><span>{{ origin?.name || '选择出发地点' }}</span></button
          ><button
            type="button"
            :class="{ focused: field === 'destination' }"
            @click="field = 'destination'"
          >
            <i class="destination-dot"></i
            ><span>{{ destination?.name || '选择到达地点' }}</span>
          </button>
        </div>
        <form @submit.prevent="search">
          <label for="place-keyword"
            >搜索{{ field === 'origin' ? '出发地' : '目的地' }}</label
          >
          <div>
            <input
              id="place-keyword"
              v-model="keyword"
              maxlength="100"
              :placeholder="`在${chat.selectedCity || '所选城市'}搜索店铺、景点、车站`"
            /><button :disabled="pending || !keyword.trim()">
              {{ pending ? '查询中…' : '搜索' }}
            </button>
          </div>
        </form>
        <p v-if="error" class="map-error" role="alert">{{ error }}</p>
        <div v-if="places.length" class="place-search-results">
          <p>请选择准确地址，避免同名地点混淆</p>
          <button
            v-for="place in places"
            :key="place.poi_id"
            type="button"
            @click="select(place)"
          >
            <strong>{{ place.name }}</strong
            ><span
              >{{ place.city }} · {{ place.district }} ·
              {{ place.address }}</span
            >
          </button>
        </div>
        <button
          class="calculate-route"
          :disabled="!origin || !destination || pending"
          @click="calculate"
        >
          <el-icon><RefreshRight /></el-icon
          >{{
            pending ? '查询路线中…' : result ? '刷新路线与耗时' : '查询路线'
          }}
        </button>
      </section>
      <section v-if="result" class="route-result">
        <div class="route-stats">
          <strong>{{ formatDuration(result.duration_s) }}</strong
          ><span
            >{{ formatDistance(result.distance_m) }} ·
            {{ result.mode === 'walking' ? '步行' : '驾车' }}</span
          >
        </div>
        <p class="route-time">
          {{ new Date(result.computed_at).toLocaleTimeString('zh-CN') }} 查询 ·
          路况变化时请刷新
        </p>
        <img
          v-if="preview && !previewFailed"
          class="route-preview"
          :src="preview"
          alt="高德地图起终点与路线位置预览"
          @error="previewFailed = true"
        />
        <p v-if="previewFailed" class="preview-unavailable">
          地图预览暂不可用，仍可查看路线并打开高德导航。
        </p>
        <ol class="route-steps">
          <li v-for="(step, i) in result.steps" :key="i">
            <span>{{ step.instruction || step.road || '沿路线前进' }}</span
            ><small>{{ formatDistance(step.distance_m) }}</small>
          </li>
        </ol>
      </section>
      <div v-if="destination" class="navigation-actions">
        <a
          v-if="navigation"
          :href="navigation"
          target="_blank"
          rel="noopener noreferrer"
          >{{
            origin && result ? '进入高德实时导航 ↗' : '从当前位置在高德导航 ↗'
          }}</a
        ><button type="button" @click="askTravel">让旅伴安排沿途探店</button>
      </div>
      <section v-if="!destination && !places.length" class="map-empty">
        <el-icon><Location /></el-icon>
        <h2>先选城市，再选想去的地方</h2>
        <p>
          找餐馆、搜景点、选起终点。<br />路线在这里查看，持续定位和语音指引由高德导航提供。
        </p>
      </section>
      <p class="map-caption">
        地点与路线来自高德地图。App
        内展示查询时的路线；打开高德后获取持续定位、语音指引和实时重算。浏览器不会自动获取或保存你的当前位置。
      </p>
    </main>
    <CityPicker v-model="cityOpen" @select="cityChanged" />
  </div>
</template>
<style scoped>
.travel-map-page {
  min-height: 100vh;
  background: #faf7f4;
  color: #54434e;
  font-family: -apple-system, BlinkMacSystemFont, 'Microsoft YaHei', sans-serif;
  font-size: 14px;
}
.travel-map-page * {
  box-sizing: border-box;
}
header {
  display: flex;
  gap: 12px;
  align-items: center;
  background: white;
  border-bottom: 1px solid #eee5e1;
  padding: 19px max(16px, calc((100% - 720px) / 2));
}
header h1 {
  flex: 1;
  margin: 0;
  font-size: 17px;
}
header button {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  background: none;
  border: 0;
  color: #a27888;
  cursor: pointer;
}
header button:first-child {
  font-size: 20px;
}
main {
  max-width: 720px;
  margin: auto;
  padding: 20px 16px 45px;
}
.route-search,
.route-result {
  padding: 20px;
  border: 1px solid #eaded7;
  border-radius: 17px;
  background: #fff;
  margin-bottom: 18px;
}
.mode-tabs {
  display: flex;
  gap: 12px;
  margin-bottom: 18px;
}
.mode-tabs button {
  border: 1px solid #e9dfe5;
  color: #a88b9b;
  padding: 8px 22px;
  border-radius: 18px;
  background: white;
  cursor: pointer;
}
.mode-tabs .selected {
  background: #fff0e5;
  border-color: #edbca0;
  color: #c77952;
}
.point-fields {
  display: grid;
  gap: 8px;
}
.point-fields button {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 13px;
  border: 1px solid #eae2e8;
  border-radius: 10px;
  text-align: left;
  background: #fdfbfc;
  color: #76616f;
  cursor: pointer;
}
.point-fields .focused {
  border-color: #d9a8bc;
  background: #fff8fb;
}
.point-fields i {
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.origin-dot {
  background: #5dab91;
}
.destination-dot {
  background: #e99565;
}
form {
  margin: 20px 0;
}
form label {
  display: block;
  font-size: 11px;
  margin-bottom: 8px;
  color: #a6909c;
}
form > div {
  display: flex;
  gap: 8px;
}
input {
  flex: 1;
  width: 0;
  border: 1px solid #eadce5;
  padding: 12px;
  border-radius: 10px;
  font-size: 13px;
}
form button {
  border: 0;
  background: #e38d6b;
  color: white;
  padding: 0 17px;
  border-radius: 9px;
}
.map-error {
  color: #b36556;
  line-height: 1.8;
  font-size: 12px;
}
.calculate-route {
  width: 100%;
  border: 0;
  border-radius: 10px;
  color: #a67459;
  background: #ffeddf;
  padding: 13px;
  display: flex;
  gap: 7px;
  justify-content: center;
  align-items: center;
  cursor: pointer;
}
.place-search-results {
  margin: 15px 0;
}
.place-search-results > p {
  color: #ac99a5;
  font-size: 11px;
}
.place-search-results > button {
  display: block;
  width: 100%;
  text-align: left;
  padding: 12px 0;
  border: 0;
  background: white;
  border-bottom: 1px solid #eee;
  cursor: pointer;
}
.place-search-results strong {
  display: block;
  font-size: 13px;
  color: #7d5b70;
}
.place-search-results span {
  display: block;
  color: #ac98a4;
  font-size: 11px;
  margin-top: 7px;
  line-height: 1.6;
}
.route-stats {
  display: flex;
  gap: 17px;
  align-items: baseline;
  flex-wrap: wrap;
}
.route-stats strong {
  color: #b46f52;
  font-size: 25px;
}
.route-stats span {
  color: #9d8190;
  font-size: 12px;
}
.route-time {
  color: #b09ba7;
  font-size: 10px;
}
.route-preview {
  width: 100%;
  height: auto;
  margin-top: 10px;
  border-radius: 12px;
}
.route-steps {
  padding-left: 22px;
  margin-top: 22px;
  color: #a58795;
}
.route-steps li {
  padding: 10px 0 10px 5px;
  border-bottom: 1px solid #f1e9ed;
}
.route-steps span {
  color: #7f6878;
  font-size: 12px;
  line-height: 1.8;
}
.route-steps small {
  color: #ad97a5;
  font-size: 10px;
  display: block;
  margin-top: 4px;
}
.navigation-actions {
  display: grid;
  gap: 12px;
  margin: 20px 0;
}
.navigation-actions a {
  display: block;
  text-decoration: none;
  text-align: center;
  background: #df8865;
  color: white;
  padding: 15px;
  border-radius: 12px;
}
.navigation-actions button {
  background: #f4edf7;
  border: 1px solid #e8dcea;
  color: #a184a8;
  border-radius: 12px;
  padding: 13px;
  cursor: pointer;
}
.map-caption,
.preview-unavailable {
  font-size: 11px;
  line-height: 1.9;
  color: #af9aa7;
}
.map-empty {
  text-align: center;
  color: #b598a8;
  padding: 34px 10px;
}
.map-empty > .el-icon {
  font-size: 42px;
  color: #d5b6c3;
}
.map-empty h2 {
  font-size: 16px;
  font-weight: 500;
}
.map-empty p {
  line-height: 1.9;
  font-size: 12px;
}
button:disabled {
  opacity: 0.45;
  cursor: default;
}
</style>
