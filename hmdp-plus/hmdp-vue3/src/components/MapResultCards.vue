<script setup>
import { computed } from 'vue'
import { safeMapUrl, formatDistance, formatDuration } from '@/utils/maps'
const props = defineProps({ tools: { type: Array, default: () => [] } })
const places = computed(() => {
  const found = new Map()
  for (const result of props.tools.filter(
    (row) => row.tool === 'search_city_places' && !row.data?.error
  )) {
    for (const place of result.data.places || []) {
      if (/^[A-Za-z0-9_-]{5,40}$/.test(place.poi_id))
        found.set(place.poi_id, place)
    }
  }
  return [...found.values()]
})
const routes = computed(() =>
  props.tools
    .filter(
      (row) =>
        row.tool === 'plan_route' &&
        row.data?.origin &&
        row.data?.destination &&
        !row.data.error
    )
    .map((row) => row.data)
)
</script>
<template>
  <div v-if="places.length || routes.length" class="map-cards">
    <p v-if="places.length" class="map-source">
      高德地点 · {{ places.length }} 个结果，与平台入驻商户独立
    </p>
    <article v-for="place in places" :key="place.poi_id" class="place-card">
      <strong>{{ place.name }}</strong>
      <p>
        {{ place.city }} {{ place.district }} ·
        {{ place.address || '地址待确认' }}
      </p>
      <div class="place-meta">
        <span>{{
          place.cost_yuan == null
            ? '人均待确认'
            : `参考人均 ¥${place.cost_yuan}`
        }}</span
        ><span v-if="place.rating != null">{{ place.rating }} 分</span>
      </div>
      <div class="place-actions">
        <router-link
          :to="{
            path: '/travel/map',
            query: { destination: place.poi_id, city: place.city }
          }"
          >查路线</router-link
        ><a
          v-if="safeMapUrl(place.navigation_url)"
          :href="safeMapUrl(place.navigation_url)"
          target="_blank"
          rel="noopener noreferrer"
          >高德导航 ↗</a
        >
      </div>
    </article>
    <article v-for="(route, index) in routes" :key="index" class="route-card">
      <small
        >{{ route.mode === 'walking' ? '步行' : '驾车' }}路线 · 高德地图</small
      ><strong>{{ route.origin.name }} → {{ route.destination.name }}</strong>
      <p>
        {{ formatDistance(route.distance_m) }} ·
        {{ formatDuration(route.duration_s) }}
      </p>
      <router-link
        :to="{
          path: '/travel/map',
          query: {
            origin: route.origin.poi_id,
            destination: route.destination.poi_id,
            mode: route.mode,
            city: route.destination.city
          }
        }"
        >查看地图与路线</router-link
      ><a
        v-if="safeMapUrl(route.navigation_url)"
        :href="safeMapUrl(route.navigation_url)"
        target="_blank"
        rel="noopener noreferrer"
        >进入高德导航 ↗</a
      >
      <p class="map-source">此为查询时估算，出发前请刷新路线。</p>
    </article>
  </div>
</template>
<style scoped>
.map-cards {
  margin-top: 14px;
}
.map-source {
  font-size: 10px;
  color: var(--tp-muted);
  line-height: 1.7;
}
.place-card,
.route-card {
  border: 1px solid var(--tp-line);
  background: #fffdf9;
  padding: 15px;
  border-radius: 13px;
  margin: 10px 0;
}
.place-card > strong,
.route-card > strong {
  display: block;
  font-size: 14px;
  color: var(--tp-ink);
  line-height: 1.7;
}
.place-card p {
  font-size: 11px;
  color: var(--tp-muted);
  line-height: 1.7;
}
.place-meta {
  display: flex;
  gap: 14px;
  color: var(--tp-muted);
  font-size: 11px;
}
.place-actions {
  display: flex;
  gap: 20px;
  margin-top: 13px;
}
.map-cards a {
  color: var(--tp-muted);
  font-size: 12px;
  text-decoration: none;
}
.route-card {
  background: var(--tp-surface-soft);
}
.route-card > small {
  display: block;
  color: var(--tp-muted);
  font-size: 11px;
  margin-bottom: 8px;
}
.route-card > p {
  color: var(--tp-muted);
  font-size: 12px;
}
.route-card > a {
  margin-right: 18px;
}
</style>
