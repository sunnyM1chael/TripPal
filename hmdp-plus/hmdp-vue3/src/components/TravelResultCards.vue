<script setup>
import { computed } from 'vue'
import VoucherSubscriptionResults from './VoucherSubscriptionResults.vue'
import { navigationForShop } from '@/utils/maps'
import { ArrowRight, Location, Shop, Tickets } from '@element-plus/icons-vue'

const props = defineProps({
  tools: { type: Array, default: () => [] },
  pending: Boolean
})
defineEmits(['ask'])
const shopId = (value) =>
  /^[1-9]\d{0,19}$/.test(String(value ?? '')) ? String(value) : null
const shops = computed(() => {
  const found = new Map()
  for (const result of props.tools) {
    if (result.data?.error) continue
    let rows = []
    if (['search_shops', 'shops_by_category'].includes(result.tool))
      rows = result.data?.shops
    if (result.tool === 'shop_detail') rows = [result.data?.shop]
    if (result.tool === 'plan_day') rows = result.data?.stops
    for (const row of Array.isArray(rows) ? rows : []) {
      if (row && shopId(row.id) && typeof row.name === 'string')
        found.set(shopId(row.id), row)
    }
  }
  return [...found.values()]
})
const categories = computed(
  () =>
    props.tools.findLast(
      (row) => row.tool === 'list_categories' && !row.data?.error
    )?.data?.categories || []
)
const vouchers = computed(() => {
  const found = new Map()
  for (const result of props.tools.filter(
    (row) => row.tool === 'shop_vouchers' && !row.data?.error
  )) {
    for (const voucher of result.data?.vouchers || []) {
      if (shopId(voucher?.id) && shopId(voucher?.shopId))
        found.set(String(voucher.id), voucher)
    }
  }
  return [...found.values()]
})
const plan = computed(
  () =>
    props.tools.findLast((row) => row.tool === 'plan_day' && !row.data?.error)
      ?.data
)
const money = (value) =>
  typeof value === 'number' && Number.isFinite(value)
    ? `¥${value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`
    : '价格待确认'
</script>

<template>
  <div class="travel-results">
    <div v-if="categories.length" class="category-options">
      <button
        v-for="category in categories"
        :key="category.id"
        type="button"
        :disabled="pending"
        @click="
          $emit(
            'ask',
            `请查询分类ID为${category.id}的${category.name}商户，帮我比较人均价格和评分。`
          )
        "
      >
        {{ category.name }} <el-icon><ArrowRight /></el-icon>
      </button>
    </div>
    <section v-if="plan" class="plan-summary">
      <span>探店预算草案 · {{ plan.people }} 人</span>
      <strong
        >{{ money(plan.known_estimate_yuan)
        }}<small>{{
          plan.estimate_complete ? ' 预计消费' : ' 已知费用'
        }}</small></strong
      >
      <p v-if="plan.within_budget === false">
        已知消费超过预算，可以继续让旅伴调整。
      </p>
      <p v-else>
        {{
          plan.estimate_complete
            ? '根据商户均价估算，不含交通与住宿。'
            : '部分商户缺少价格，完整预算仍需确认。'
        }}
      </p>
    </section>
    <section v-if="shops.length" class="shop-results">
      <div class="section-caption">
        本次查询的商户 <span>{{ shops.length }} 家</span>
      </div>
      <article
        v-for="(shop, index) in shops"
        :key="shop.id"
        class="result-card"
      >
        <router-link :to="`/shopDetail/${shop.id}`" class="shop-link">
          <span class="shop-marker"
            ><el-icon><Shop /></el-icon
            ><small>{{ String(index + 1).padStart(2, '0') }}</small></span
          >
          <div class="shop-copy">
            <h4>{{ shop.name }}</h4>
            <div class="shop-meta">
              <span class="rating">{{
                typeof shop.score === 'number'
                  ? `${shop.score.toFixed(1)} 分`
                  : '暂无评分'
              }}</span
              ><span>{{
                shop.avgPrice == null
                  ? '人均待确认'
                  : `${money(shop.avgPrice)}/人`
              }}</span>
            </div>
            <p>
              <el-icon><Location /></el-icon
              >{{ shop.address || shop.area || '地址待确认' }}
            </p>
          </div>
          <el-icon class="card-arrow"><ArrowRight /></el-icon>
        </router-link>
        <div class="card-actions">
          <a
            v-if="navigationForShop(shop)"
            :href="navigationForShop(shop)"
            target="_blank"
            rel="noopener noreferrer"
            >高德导航 ↗</a
          >
          <span v-if="shop.openHours">{{ shop.openHours }}</span
          ><span v-else>营业时间待确认</span
          ><button
            type="button"
            :disabled="pending"
            @click="
              $emit(
                'ask',
                `请查询商户ID为${shop.id}的${shop.name}有哪些优惠券，说明价格和使用规则。`
              )
            "
          >
            查优惠券 <el-icon><Tickets /></el-icon>
          </button>
        </div>
      </article>
    </section>
    <section v-if="vouchers.length" class="voucher-results">
      <div class="section-caption">
        查到的优惠券 <span>使用前请核对有效期与规则</span>
      </div>
      <router-link
        v-for="voucher in vouchers"
        :key="voucher.id"
        :to="`/shopDetail/${voucher.shopId}`"
        class="voucher-card"
      >
        <span class="voucher-price"
          >{{ money(voucher.pay_yuan)
          }}<small>抵 {{ money(voucher.value_yuan) }}</small></span
        >
        <span class="voucher-info"
          ><strong>{{ voucher.title || '商户优惠券' }}</strong
          ><span>{{ voucher.subTitle || '前往商户页查看详情' }}</span
          ><small>{{ voucher.rules || '具体使用条件请咨询商户' }}</small></span
        >
        <el-icon><ArrowRight /></el-icon>
      </router-link>
    </section>
    <VoucherSubscriptionResults :tools="tools" :pending="pending" />
  </div>
</template>

<style scoped>
.card-actions a {
  text-decoration: none;
  color: var(--tp-muted);
  font-size: 11px;
  flex-shrink: 0;
}
.travel-results {
  margin-top: 14px;
}
.category-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.category-options button {
  border: 1px solid var(--tp-line);
  background: var(--tp-surface-soft);
  padding: 8px 11px;
  border-radius: 9px;
  color: var(--tp-ink);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.section-caption {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 16px 0 9px;
  font-size: 12px;
  color: #76717b;
}
.section-caption span {
  font-size: 11px;
  color: #99919c;
}
.result-card {
  border: 1px solid var(--tp-line);
  background: #fff;
  border-radius: 14px;
  overflow: hidden;
  margin: 9px 0;
}
.shop-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px;
  color: inherit;
  text-decoration: none;
}
.shop-marker {
  flex-shrink: 0;
  background: var(--tp-surface-soft);
  color: var(--tp-muted);
  border-radius: 12px;
  width: 49px;
  height: 58px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}
.shop-marker small {
  font-size: 10px;
  letter-spacing: 1px;
}
.shop-copy {
  flex: 1;
  min-width: 0;
}
h4 {
  margin: 0 0 5px;
  font-size: 14px;
}
.shop-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #77717a;
}
.rating {
  color: var(--tp-muted);
  font-weight: 600;
}
.shop-copy p {
  margin: 6px 0 0;
  font-size: 11px;
  color: #918993;
  display: flex;
  align-items: flex-start;
  gap: 4px;
}
.shop-copy p .el-icon {
  flex-shrink: 0;
  margin-top: 2px;
}
.card-arrow {
  color: var(--tp-muted);
}
.card-actions {
  border-top: 1px solid var(--tp-line);
  padding: 8px 14px;
  display: flex;
  gap: 8px;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  color: #968b91;
}
.card-actions button {
  border: none;
  background: none;
  padding: 4px 0;
  cursor: pointer;
  color: var(--tp-muted);
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  flex-shrink: 0;
}
.plan-summary {
  padding: 15px 17px;
  background: var(--tp-surface-soft);
  border-radius: 13px;
  color: var(--tp-ink);
  margin-top: 12px;
}
.plan-summary > span {
  font-size: 12px;
}
.plan-summary strong {
  display: block;
  font-size: 25px;
  margin-top: 5px;
}
.plan-summary small {
  font-size: 12px;
  font-weight: 400;
}
.plan-summary p {
  font-size: 11px;
  margin: 6px 0 0;
  line-height: 1.6;
}
.voucher-card {
  display: flex;
  gap: 13px;
  align-items: center;
  text-decoration: none;
  color: inherit;
  border: 1px solid var(--tp-line);
  border-radius: 12px;
  padding: 13px;
  background: var(--tp-surface-soft);
  margin: 8px 0;
}
.voucher-price {
  color: var(--tp-muted);
  font-size: 21px;
  font-weight: 600;
  flex-shrink: 0;
  padding-right: 12px;
  border-right: 1px dashed var(--tp-line);
}
.voucher-price small {
  display: block;
  font-size: 10px;
  font-weight: 400;
  margin-top: 3px;
}
.voucher-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-wrap: anywhere;
}
.voucher-info strong {
  font-size: 13px;
}
.voucher-info span {
  font-size: 11px;
  color: var(--tp-muted);
}
.voucher-info small {
  font-size: 10px;
  color: var(--tp-muted);
}
button:disabled {
  opacity: 0.45;
  cursor: default;
}
</style>
