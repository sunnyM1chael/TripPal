<script setup>
import { onUnmounted, ref, watch } from 'vue'
import { useUserStore } from '@/stores/modules/user'
import {
  getVoucherSubscription,
  prepareVoucherSubscription,
  confirmVoucherSubscription
} from '@/api/travel'

const props = defineProps({
  shopId: { type: String, required: true },
  voucherId: { type: String, required: true },
  initialAction: { type: Object, default: null },
  pending: Boolean
})
const user = useUserStore()
const action = ref(null)
const receipt = ref(null)
const current = ref(null)
const accepted = ref(false)
const busy = ref(false)
const error = ref('')
let generation = 0

function reset() {
  generation++
  action.value = null
  receipt.value = null
  current.value = null
  accepted.value = false
  busy.value = false
  error.value = ''
}
watch(
  () => [props.shopId, props.voucherId, props.initialAction],
  () => {
    reset()
    if (user.token && props.initialAction) action.value = props.initialAction
  },
  { immediate: true }
)
watch(() => user.token, reset)
onUnmounted(reset)

async function perform(operation, apply) {
  if (busy.value || props.pending) return
  const turn = ++generation
  const account = user.token
  busy.value = true
  error.value = ''
  try {
    const data = await operation()
    if (turn === generation && account === user.token) apply(data)
  } catch (err) {
    if (turn === generation && account === user.token) error.value = err.message
  } finally {
    if (turn === generation) busy.value = false
  }
}
function prepare(kind) {
  return perform(
    () => prepareVoucherSubscription(props.shopId, props.voucherId, kind),
    (data) => {
      action.value = data
      receipt.value = null
      accepted.value = false
      current.value = data.current
    }
  )
}
function refresh() {
  return perform(
    () => getVoucherSubscription(props.shopId, props.voucherId),
    (data) => {
      current.value = data
    }
  )
}
function dismiss() {
  action.value = null
  accepted.value = false
}
function confirm() {
  if (!action.value || (action.value.action === 'subscribe' && !accepted.value))
    return
  const id = action.value.action_id
  return perform(
    () => confirmVoucherSubscription(id, accepted.value),
    (data) => {
      receipt.value = data
      if (data.verified) current.value = data
      else current.value = null
      action.value = null
      accepted.value = false
    }
  )
}
const price = (value) =>
  value !== null && value !== '' && Number.isFinite(Number(value))
    ? `¥${(Number(value) / 100).toFixed(2)}`
    : '待确认'
</script>

<template>
  <section class="subscription-card" aria-label="优惠券候补操作">
    <div class="subscription-heading">
      <strong>优惠券候补</strong
      ><router-link :to="`/shopDetail/${shopId}`">查看商户 →</router-link>
    </div>
    <template v-if="user.token">
      <p v-if="current?.verified" class="status" role="status">
        {{ current.status_label }} ·
        {{ new Date(current.checked_at * 1000).toLocaleTimeString('zh-CN') }}
        回查
      </p>
      <p v-if="receipt" role="status" class="receipt">
        {{ receipt.message
        }}<span v-if="receipt.verified">
          当前：{{ receipt.status_label }}。</span
        >
      </p>
      <div v-if="action" class="confirmation">
        <strong
          >{{
            action.action === 'subscribe' ? '确认加入候补' : '确认退出候补'
          }}
          · {{ action.voucher.title }}</strong
        >
        <p>
          {{ action.voucher.shop_name }} · 券号 {{ action.voucher.voucher_id }}
        </p>
        <p>
          购买价 {{ price(action.voucher.payValue) }} · 面值
          {{ price(action.voucher.actualValue) }}
        </p>
        <p>
          有效期：{{ action.voucher.beginTime || '开始时间待确认' }} 至
          {{ action.voucher.endTime || '待确认' }}
        </p>
        <p>
          使用规则：{{ action.voucher.rules || '规则未提供，请向商户核实' }}
        </p>
        <p class="notice">{{ action.notice }}</p>
        <label v-if="action.action === 'subscribe'" class="acknowledge">
          <input v-model="accepted" type="checkbox" :disabled="busy" />
          <span
            >我已了解：有券时系统可能自动发券并创建券订单，且不保证候补成功。</span
          >
        </label>
        <small>本卡5分钟内有效；重启服务后需重新准备。</small>
        <div class="actions">
          <button
            type="button"
            class="primary"
            :disabled="
              busy || pending || (action.action === 'subscribe' && !accepted)
            "
            @click="confirm"
          >
            {{
              busy
                ? '核对处理中…'
                : action.action === 'subscribe'
                  ? '确认加入候补'
                  : '确认退出候补'
            }}
          </button>
          <button type="button" :disabled="busy" @click="dismiss">
            暂不操作
          </button>
        </div>
      </div>
      <div v-else class="actions">
        <button type="button" :disabled="busy || pending" @click="refresh">
          查询当前状态
        </button>
        <button
          v-if="current?.status !== 1 && current?.status !== 2"
          type="button"
          :disabled="busy || pending"
          @click="prepare('subscribe')"
        >
          准备候补订阅
        </button>
        <button
          v-if="current?.status === 1"
          type="button"
          :disabled="busy || pending"
          @click="prepare('unsubscribe')"
        >
          准备退出候补
        </button>
      </div>
      <p v-if="error" role="alert" class="error">{{ error }}</p>
    </template>
    <p v-else><router-link to="/login">登录后查看或订阅候补 →</router-link></p>
    <p class="scope">
      补库存时的候补队列，不是普通提醒。取消候补不会取消已有券订单。
    </p>
  </section>
</template>

<style scoped>
.subscription-card {
  margin: 10px 0 18px;
  padding: 16px;
  background: var(--tp-surface-soft);
  border: 1px solid var(--tp-line);
  border-radius: 14px;
  color: var(--tp-ink);
  font-size: 12px;
  line-height: 1.8;
}
.subscription-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.subscription-heading strong {
  font-size: 13px;
}
a {
  color: var(--tp-ink);
  text-decoration: none;
}
.status {
  font-weight: 600;
}
.receipt {
  background: white;
  border-radius: 8px;
  padding: 10px;
}
.confirmation {
  padding: 12px 0;
}
.confirmation p {
  margin: 6px 0;
  overflow-wrap: anywhere;
}
.notice {
  color: #805a31;
  background: #fff5df;
  padding: 10px;
  border-radius: 8px;
}
.acknowledge {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 12px 0;
  cursor: pointer;
}
.acknowledge input {
  margin-top: 5px;
  accent-color: var(--tp-ink);
  flex-shrink: 0;
}
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}
button {
  border: 1px solid var(--tp-line);
  border-radius: 9px;
  padding: 8px 12px;
  color: var(--tp-ink);
  background: white;
  font: inherit;
  cursor: pointer;
}
button.primary {
  background: var(--tp-ink);
  color: white;
  border-color: var(--tp-line);
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
.scope,
small {
  font-size: 10px;
  color: var(--tp-muted);
}
.error {
  color: #a04b32;
}
button:focus-visible,
a:focus-visible,
input:focus-visible {
  outline: 2px solid var(--tp-ink);
  outline-offset: 3px;
}
</style>
