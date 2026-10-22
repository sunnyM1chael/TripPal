<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/modules/user'
import { getItinerary, saveVisitFeedback, savePreferences } from '@/api/travel'

const props = defineProps({
  plan: { type: Object, required: true },
  stop: { type: Object, required: true },
  disabled: Boolean
})
const emit = defineEmits(['saved', 'conflict'])
const router = useRouter(),
  user = useUserStore()
const existing = computed(() => props.stop.feedback)
const form = reactive({
  rating: existing.value?.rating || 4,
  actual_cost_yuan: existing.value?.actual_cost_yuan ?? '',
  cost_scope: existing.value?.cost_scope || 'person',
  queue_minutes: existing.value?.queue_minutes ?? '',
  experience: existing.value?.experience || '',
  would_return:
    existing.value?.would_return == null
      ? ''
      : String(existing.value.would_return),
  draft_title: existing.value?.draft?.title || '',
  draft_content: existing.value?.draft?.content || ''
})
const busy = ref(false),
  error = ref(''),
  message = ref(''),
  preferenceBudget = ref('')

async function save() {
  if (busy.value || props.disabled) return
  const token = user.token
  busy.value = true
  error.value = ''
  try {
    const result = await saveVisitFeedback(props.plan.id, props.stop.id, {
      ...form,
      expected_revision: props.plan.revision,
      rating: Number(form.rating),
      actual_cost_yuan:
        form.actual_cost_yuan === '' ? null : String(form.actual_cost_yuan),
      queue_minutes:
        form.queue_minutes === '' ? null : Number(form.queue_minutes),
      would_return:
        form.would_return === '' ? null : form.would_return === 'true',
      draft_title: form.draft_title.trim() || null,
      draft_content: form.draft_content.trim() || null
    })
    if (token === user.token) {
      const draft = result.stops.find((stop) => stop.id === props.stop.id)
        ?.feedback?.draft
      if (draft) {
        form.draft_title = draft.title
        form.draft_content = draft.content
      }
      message.value = '体验与私有草稿已保存。'
      emit('saved', result)
    }
  } catch (e) {
    if (token !== user.token) return
    error.value = e.response?.data?.message || e.message
    if (e.response?.status === 409) {
      try {
        const latest = await getItinerary(props.plan.id)
        if (token === user.token) {
          emit('conflict', latest)
          error.value =
            '已加载最新版本，你的输入仍保留。请核对下方已保存体验，再决定是否重新保存。'
        }
      } catch {
        error.value = '行程已更新，暂时无法读取最新版本。请保留输入后刷新。'
      }
    }
  } finally {
    busy.value = false
  }
}

async function rememberBudget() {
  if (busy.value || preferenceBudget.value === '') return
  const token = user.token
  busy.value = true
  error.value = ''
  try {
    await savePreferences({ budget_per_person: Number(preferenceBudget.value) })
    if (token === user.token)
      message.value = '以后的人均预算已保存，可在我的记忆中修改。'
  } catch (e) {
    if (token === user.token) error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <details class="visit-feedback">
    <summary>
      {{ existing ? '查看 / 修改这次体验' : '去过了，记一下体验' }}
    </summary>
    <p>仅自己可见。记录实际体验后生成草稿，公开发布前可以继续编辑。</p>
    <form @submit.prevent="save">
      <fieldset :disabled="busy || disabled">
        <div class="fields">
          <label
            >我的评分<select v-model="form.rating">
              <option v-for="n in 5" :key="n" :value="n">{{ n }} 分</option>
            </select></label
          >
          <label
            >实际花费（元，可不填）<input
              v-model="form.actual_cost_yuan"
              type="number"
              min="0"
              max="1000000"
              step="0.01"
          /></label>
          <label
            >花费口径<select v-model="form.cost_scope">
              <option value="person">人均</option>
              <option value="party">同行人合计</option>
            </select></label
          >
          <label
            >排队分钟（可不填）<input
              v-model="form.queue_minutes"
              type="number"
              min="0"
              max="1440"
              step="1"
          /></label>
          <label
            >还愿意去吗<select v-model="form.would_return">
              <option value="">暂不评价</option>
              <option value="true">愿意</option>
              <option value="false">不考虑</option>
            </select></label
          >
        </div>
        <label
          >实际体验<textarea
            v-model="form.experience"
            required
            maxlength="1500"
            rows="3"
            placeholder="吃了什么、哪里满意、哪里需要改进？只记录你自己的经历。"
          />
        </label>
        <details>
          <summary>编辑探店草稿（留空则按体验生成）</summary>
          <label
            >标题<input v-model="form.draft_title" maxlength="100"
          /></label>
          <label
            >正文<textarea
              v-model="form.draft_content"
              maxlength="2500"
              rows="5"
            />
          </label>
          <p>修改体验后，如需重新生成正文，请清空草稿正文再保存。</p>
        </details>
        <button type="submit">{{ busy ? '保存中…' : '保存体验与草稿' }}</button>
        <button
          v-if="existing && user.token"
          type="button"
          @click="
            router.push({
              path: '/blogEdit',
              query: { itinerary: plan.id, stop: stop.id }
            })
          "
        >
          打开已保存草稿去发布
        </button>
      </fieldset>
    </form>
    <p v-if="existing">已保存体验：{{ existing.experience }}</p>
    <p v-if="existing && !user.token">
      游客反馈保存在当前游客身份下。公开发布需要登录账号；登录后不会自动转移游客记录。
    </p>
    <form v-if="user.token" @submit.prevent="rememberBudget">
      <label
        >希望驴友以后记住的人均预算（可选）<input
          v-model="preferenceBudget"
          type="number"
          min="0"
          max="100000"
          step="0.01"
      /></label>
      <button :disabled="busy || disabled || preferenceBudget === ''">
        确认保存为长期偏好
      </button>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
  </details>
</template>

<style scoped>
.visit-feedback {
  margin-top: 14px;
  padding: 16px;
  background: var(--tp-surface-soft);
  border: 1px solid var(--tp-line);
  border-radius: 12px;
  color: var(--tp-ink);
}
summary {
  cursor: pointer;
  font-size: 14px;
}
p,
label {
  font-size: 12px;
  line-height: 1.7;
}
fieldset {
  border: 0;
  padding: 0;
  min-width: 0;
}
.fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 12px;
}
label {
  display: block;
  margin: 10px 0;
}
input,
select,
textarea {
  box-sizing: border-box;
  display: block;
  width: 100%;
  padding: 9px;
  border: 1px solid var(--tp-line);
  border-radius: 7px;
  background: white;
  color: var(--tp-ink);
  font: inherit;
}
button {
  margin: 10px 8px 0 0;
  padding: 9px 12px;
  border: 1px solid var(--tp-line);
  border-radius: 8px;
  background: #fff;
  color: var(--tp-ink);
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
