<script setup>
import { computed } from 'vue'
import { formatDistance, formatDuration, safeMapUrl } from '@/utils/maps'

const props = defineProps({
  plan: { type: Object, required: true },
  compact: Boolean
})
const days = computed(() =>
  Array.from({ length: props.plan.day_count || 1 }, (_, index) => {
    const day = index + 1
    return {
      day,
      stops: props.plan.stops.filter((stop) => (stop.day || 1) === day),
      summary: props.plan.summary?.days?.find((item) => item.day === day)
    }
  })
)
const legFrom = (stop) =>
  props.plan.legs?.find((leg) => leg.origin_stop_id === stop.id)
const slot = (day, stop) =>
  day.summary?.schedule?.find((item) => item.stop_id === stop.id)
</script>

<template>
  <div class="day-overview">
    <section v-for="day in days" :key="day.day" class="day-card">
      <header>
        <strong>第 {{ day.day }} 天</strong
        ><span>{{ day.summary?.date || '日期待定' }}</span>
      </header>
      <p v-if="day.summary" class="day-stats">
        已知安排 {{ day.summary.known_total_minutes }} 分钟 · 参考消费 ¥{{
          day.summary.known_reference_total_yuan
        }}
      </p>
      <p v-if="day.summary?.within_time === false" class="warning">
        当天安排超时，需要删减或调整。
      </p>
      <p v-if="day.summary?.time_estimate_complete === false" class="warning">
        部分路线尚未核实，耗时不完整。
      </p>
      <p v-if="compact" class="day-chain">
        {{ day.stops.map((stop) => stop.place.name).join(' → ') }}
      </p>
      <ol v-else>
        <li v-for="stop in day.stops" :key="stop.id">
          <strong>{{ stop.place.name }}</strong
          ><span class="time"
            >{{ slot(day, stop)?.arrival_time || '钟点待定' }} · 停留
            {{ stop.stay_minutes }} 分钟</span
          >
          <small>{{ stop.place.address || '地址待确认' }}</small>
          <small v-if="slot(day, stop)?.rest_after_minutes"
            >本站后额外休息 {{ slot(day, stop).rest_after_minutes }} 分钟</small
          >
          <div v-if="legFrom(stop)" class="route-leg">
            {{ legFrom(stop).mode === 'walking' ? '步行' : '驾车' }}至下一站 ·
            {{ formatDuration(legFrom(stop).duration_s) }} ·
            {{ formatDistance(legFrom(stop).distance_m) }}
            <a
              v-if="safeMapUrl(legFrom(stop).navigation_url)"
              :href="safeMapUrl(legFrom(stop).navigation_url)"
              target="_blank"
              rel="noopener noreferrer"
              >查看高德路线 ↗</a
            >
            <small v-if="legFrom(stop).computed_at"
              >{{
                new Date(legFrom(stop).computed_at).toLocaleString('zh-CN')
              }}
              查询</small
            >
          </div>
        </li>
      </ol>
    </section>
    <p class="day-note">
      每天单独计算站点间路线，不含首站前接驳、末站返程；钟点为规划建议。
    </p>
  </div>
</template>

<style scoped>
.day-overview {
  margin: 16px 0;
}
.day-card {
  border: 1px solid var(--tp-line);
  border-radius: 13px;
  background: #ffffffb8;
  padding: 14px;
  margin: 10px 0;
  color: var(--tp-ink);
  font-size: 12px;
}
.day-card header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.day-card header strong {
  font-size: 14px;
}
.day-card header span {
  font-size: 11px;
  color: var(--tp-muted);
}
.day-stats,
.day-chain {
  line-height: 1.8;
}
.day-card ol {
  padding-left: 20px;
}
.day-card li {
  padding: 8px 0;
}
.time,
small {
  display: block;
  font-size: 11px;
  color: var(--tp-muted);
  margin-top: 4px;
}
.route-leg {
  margin-top: 9px;
  padding: 9px;
  border-radius: 8px;
  background: var(--tp-surface-soft);
  line-height: 1.7;
}
.route-leg a {
  display: block;
  text-decoration: none;
  color: var(--tp-ink);
}
.warning {
  color: #9d593b;
}
.day-note {
  font-size: 10px;
  line-height: 1.7;
  color: var(--tp-muted);
}
.day-chain {
  overflow-wrap: anywhere;
}
a:focus-visible {
  outline: 2px solid var(--tp-ink);
  outline-offset: 2px;
}
</style>
