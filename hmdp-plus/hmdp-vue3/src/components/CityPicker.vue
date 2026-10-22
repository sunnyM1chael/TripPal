<script setup>
import { ref, watch } from 'vue'
import { searchCities } from '@/api/travel'
import { useTravelStore } from '@/stores/modules/travel'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'select'])
const chat = useTravelStore()
const keyword = ref('')
const results = ref([])
const pending = ref(false)
const error = ref('')
const popular = [
  '杭州',
  '南京',
  '上海',
  '北京',
  '苏州',
  '无锡',
  '合肥',
  '安庆',
  '成都',
  '广州',
  '深圳',
  '重庆'
]
let version = 0
watch(
  () => props.modelValue,
  () => {
    version++
    error.value = ''
    pending.value = false
  }
)
async function search() {
  if (!keyword.value.trim()) return
  const turn = ++version
  pending.value = true
  error.value = ''
  try {
    const data = await searchCities(keyword.value.trim())
    if (turn === version) results.value = data.cities
  } catch (err) {
    if (turn === version) error.value = err.message
  } finally {
    if (turn === version) pending.value = false
  }
}
function select(city) {
  chat.selectedCity = city
  emit('select', city)
  emit('update:modelValue', false)
}
</script>
<template>
  <el-drawer
    :model-value="modelValue"
    title="选择出行城市"
    direction="btt"
    size="65%"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="city-picker">
      <form class="city-search" @submit.prevent="search">
        <label class="sr" for="city-keyword">城市或区县名称</label
        ><input
          id="city-keyword"
          v-model="keyword"
          maxlength="40"
          placeholder="搜索城市 / 区县，例如南京、鼓楼区"
        /><button :disabled="pending">
          {{ pending ? '搜索中…' : '搜索' }}
        </button>
      </form>
      <p v-if="error" class="city-error" role="alert">{{ error }}</p>
      <h3>常用目的地</h3>
      <div class="popular">
        <button
          v-for="city in popular"
          :key="city"
          type="button"
          @click="select(city)"
        >
          {{ city }}
        </button>
      </div>
      <h3 v-if="results.length">搜索结果</h3>
      <button
        v-for="city in results"
        :key="city.adcode"
        type="button"
        class="city-result"
        @click="select(city.name)"
      >
        <strong>{{ city.name }}</strong
        ><span
          >{{ city.level === 'district' ? '区县' : '城市 / 省份' }} ·
          {{ city.adcode }}</span
        >
      </button>
      <p class="city-help">
        选择后，城市地点搜索和旅伴推荐将使用该目的地。平台原有社区内容不按城市筛选。
      </p>
    </div>
  </el-drawer>
</template>
<style scoped>
.city-picker {
  max-width: 620px;
  margin: auto;
  color: var(--tp-ink);
}
.city-search {
  display: flex;
  gap: 8px;
}
.city-search input {
  min-width: 0;
  flex: 1;
  border: 1px solid var(--tp-line);
  border-radius: 10px;
  padding: 12px;
  font-size: 14px;
}
.city-search button {
  background: var(--tp-muted);
  color: white;
  border: 0;
  border-radius: 10px;
  padding: 0 18px;
}
h3 {
  font-size: 13px;
  margin-top: 24px;
  color: var(--tp-muted);
}
.popular {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.popular button {
  border: 1px solid var(--tp-line);
  background: var(--tp-surface-soft);
  color: var(--tp-muted);
  border-radius: 8px;
  padding: 10px 17px;
  cursor: pointer;
}
.city-result {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 0;
  border-bottom: 1px solid #eee;
  background: white;
  padding: 15px 2px;
  cursor: pointer;
}
.city-result span {
  font-size: 11px;
  color: var(--tp-muted);
}
.city-error {
  color: #b06458;
  line-height: 1.7;
}
.city-help {
  color: var(--tp-muted);
  font-size: 11px;
  line-height: 1.7;
  margin-top: 22px;
}
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}
</style>
