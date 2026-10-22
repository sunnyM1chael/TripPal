<script setup>
import { computed } from 'vue'
import VoucherSubscriptionCard from './VoucherSubscriptionCard.vue'

const props = defineProps({
  tools: { type: Array, default: () => [] },
  pending: Boolean
})
const entries = computed(() => {
  const found = new Map()
  const valid = (value) => /^[1-9]\d{0,18}$/.test(String(value ?? ''))
  for (const row of props.tools) {
    if (row.data?.error) continue
    if (row.tool === 'shop_vouchers') {
      for (const voucher of row.data?.vouchers || []) {
        if (
          String(voucher.type) === '1' &&
          valid(voucher.id) &&
          valid(voucher.shopId)
        )
          found.set(String(voucher.id), {
            shopId: String(voucher.shopId),
            voucherId: String(voucher.id),
            title: voucher.title
          })
      }
    }
    const action = row.data?.subscription_action
    const voucher = action?.voucher || row.data?.subscription_status?.voucher
    if (voucher && valid(voucher.shop_id) && valid(voucher.voucher_id)) {
      const previous = found.get(String(voucher.voucher_id))
      found.set(String(voucher.voucher_id), {
        ...previous,
        shopId: String(voucher.shop_id),
        voucherId: String(voucher.voucher_id),
        title: voucher.title,
        initialAction: action || previous?.initialAction
      })
    }
  }
  return [...found.values()]
})
</script>

<template>
  <div v-if="entries.length" class="subscription-results">
    <div v-for="entry in entries" :key="entry.voucherId">
      <p class="voucher-title">{{ entry.title || '秒杀优惠券' }}</p>
      <VoucherSubscriptionCard
        :shop-id="entry.shopId"
        :voucher-id="entry.voucherId"
        :initial-action="entry.initialAction"
        :pending="pending"
      />
    </div>
  </div>
</template>

<style scoped>
.subscription-results {
  margin-top: 16px;
}
.voucher-title {
  font-size: 12px;
  color: var(--tp-ink);
  margin-bottom: 0;
}
</style>
