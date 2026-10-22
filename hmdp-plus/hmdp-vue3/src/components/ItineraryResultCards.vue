<script setup>
import { computed } from 'vue'
import ItineraryDayOverview from './ItineraryDayOverview.vue'
const props = defineProps({ tools: { type: Array, default: () => [] } })
const plans = computed(() => {
  const found = new Map()
  for (const row of props.tools) {
    const plan = row.data?.itinerary
    if (plan?.id && /^[a-f0-9-]{36}$/i.test(plan.id)) found.set(plan.id, plan)
  }
  return [...found.values()]
})
</script>
<template>
  <article v-for="plan in plans" :key="plan.id" class="itinerary-result">
    <small
      >已保存的行程 · {{ plan.city }} · {{ plan.day_count || 1 }} 天 ·
      {{ plan.people }} 人</small
    >
    <h3>{{ plan.title }}</h3>
    <ItineraryDayOverview :plan="plan" />
    <p>
      已完成 {{ plan.summary.completed_stops }}/{{ plan.stops.length }} 站 ·
      已知安排约 {{ plan.summary.known_total_minutes }} 分钟
    </p>
    <p v-if="plan.summary.budget_status === 'over_known'" class="warning">
      已知参考费用超过总预算，需要调整
    </p>
    <p>
      全程总预算
      {{
        plan.budget_yuan == null ? '未设置' : `¥${plan.budget_yuan}`
      }}；已知参考消费 ¥{{ plan.summary.known_reference_total_yuan }}，未知价格
      {{ plan.summary.unknown_price_stops }} 站。住宿、交通和门票等仍需核实。
    </p>
    <router-link :to="{ path: '/travel/itineraries', query: { id: plan.id } }"
      >打开行程，换店或调整顺序 →</router-link
    >
    <small
      >此卡片记录生成时的安排，打开查看最新内容。价格与路线为查询时参考。</small
    >
  </article>
</template>
<style scoped>
.itinerary-result {
  margin: 14px 0;
  padding: 18px;
  border: 1px solid var(--tp-line);
  border-radius: 16px;
  background: #f5f9f3;
  color: var(--tp-ink);
}
h3 {
  margin: 8px 0;
  font-size: 17px;
}
p {
  font-size: 12px;
  line-height: 1.8;
}
small {
  display: block;
  font-size: 10px;
  opacity: 0.75;
  line-height: 1.8;
}
a {
  display: inline-block;
  margin: 10px 0;
  color: var(--tp-ink);
  font-size: 13px;
  font-weight: 600;
}
.warning {
  color: #ad563e;
}
</style>
