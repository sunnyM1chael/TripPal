<script setup>
import { reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTravelStore } from '@/stores/modules/travel'

const props = defineProps({
  modelValue: Boolean,
  initialTab: { type: String, default: 'preferences' }
})
const emit = defineEmits(['update:modelValue'])
const chat = useTravelStore()
const tab = ref('preferences')
const working = ref(false)
const error = ref('')
const form = reactive({
  city: '',
  budget: '',
  cuisines: '',
  dietary: '',
  transport: ''
})
function fill() {
  const prefs = chat.preferences
  Object.assign(form, {
    city: prefs.default_city || '',
    budget: prefs.budget_per_person ?? '',
    cuisines: (prefs.cuisines || []).join('，'),
    dietary: (prefs.dietary_notes || []).join('，'),
    transport: prefs.transport || ''
  })
}
watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    tab.value = props.initialTab
    error.value = ''
    try {
      await chat.refreshState()
      fill()
    } catch (err) {
      error.value = err.message
    }
  }
)
const list = (value) =>
  value
    .split(/[,，、\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
async function save() {
  working.value = true
  error.value = ''
  try {
    await chat.updatePreferences({
      default_city: form.city.trim() || null,
      budget_per_person: form.budget === '' ? null : Number(form.budget),
      cuisines: list(form.cuisines),
      dietary_notes: list(form.dietary),
      transport: form.transport || null
    })
    ElMessage.success('出行偏好已保存，下次对话也会参考')
  } catch (err) {
    error.value = err.message
  } finally {
    working.value = false
  }
}
async function open(id) {
  try {
    await chat.openConversation(id)
    emit('update:modelValue', false)
  } catch (err) {
    error.value = err.message
  }
}
async function remove(id) {
  try {
    await ElMessageBox.confirm(
      '删除后，这段对话将不再用于历史回忆。',
      '删除这段对话？',
      { confirmButtonText: '删除', cancelButtonText: '保留', type: 'warning' }
    )
    await chat.deleteConversation(id)
  } catch (err) {
    if (err instanceof Error) error.value = err.message
  }
}
async function forget() {
  try {
    await ElMessageBox.confirm(
      '将清除当前身份下的出行偏好、全部历史对话和已保存行程，无法恢复。',
      '清除全部记忆？',
      {
        confirmButtonText: '清除全部',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    working.value = true
    await chat.forget()
    fill()
    ElMessage.success('记忆已清除')
  } catch (err) {
    if (err instanceof Error) error.value = err.message
  } finally {
    working.value = false
  }
}
</script>
<template>
  <el-drawer
    :model-value="modelValue"
    title="旅伴的记忆"
    direction="rtl"
    size="min(440px, 100%)"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="memory-panel">
      <div class="memory-tabs">
        <button
          :class="{ selected: tab === 'preferences' }"
          @click="tab = 'preferences'"
        >
          出行偏好</button
        ><button
          :class="{ selected: tab === 'history' }"
          @click="tab = 'history'"
        >
          历史对话
        </button>
      </div>
      <p class="memory-caption">
        {{
          chat.guest
            ? '访客可以保留聊天历史。登录后可保存长期出行偏好，账号记忆独立存储。'
            : '记忆归属当前登录账号，可跨浏览器恢复。'
        }}
      </p>
      <p v-if="error" class="memory-error" role="alert">{{ error }}</p>
      <div v-if="tab === 'preferences' && chat.guest" class="memory-caption">
        <p>登录后，旅伴可以跨对话记住你的城市、预算和口味。</p>
        <router-link to="/login">登录并设置偏好</router-link>
      </div>
      <form
        v-else-if="tab === 'preferences'"
        class="preference-form"
        @submit.prevent="save"
      >
        <label
          >常用出行城市<input
            v-model="form.city"
            maxlength="40"
            placeholder="例如：南京"
        /></label>
        <label
          >通常的人均预算（元）<input
            v-model="form.budget"
            type="number"
            min="0"
            max="100000"
            step="0.01"
            placeholder="未设置"
        /></label>
        <label
          >喜欢的口味<input
            v-model="form.cuisines"
            maxlength="500"
            placeholder="例如：火锅，淮扬菜，咖啡"
          /><small>多个项目用逗号分隔，最多12项</small></label
        >
        <label
          >饮食注意事项<input
            v-model="form.dietary"
            maxlength="500"
            placeholder="例如：不吃辣，不吃香菜"
        /></label>
        <label
          >常用出行方式<select v-model="form.transport">
            <option value="">每次再决定</option>
            <option value="walking">步行</option>
            <option value="driving">驾车</option>
          </select></label
        >
        <button
          class="save-preferences"
          :disabled="working || chat.pending || chat.busy"
        >
          {{ working ? '保存中…' : '保存偏好' }}
        </button>
        <p class="memory-caption">
          也可以在对话中说“记住，我喜欢淮扬菜，人均预算100元”。当前需求始终优先于已保存偏好。
        </p>
      </form>
      <div v-else class="history-list">
        <p v-if="!chat.conversations.length" class="memory-caption">
          还没有保存的对话，和旅伴聊聊就会出现在这里。
        </p>
        <article
          v-for="conversation in chat.conversations"
          :key="conversation.id"
          :class="{ current: conversation.id === chat.conversationId }"
        >
          <button
            class="history-open"
            :disabled="chat.pending"
            @click="open(conversation.id)"
          >
            <strong>{{ conversation.title }}</strong
            ><span>{{
              new Date(conversation.updated * 1000).toLocaleString('zh-CN')
            }}</span></button
          ><button
            class="history-delete"
            :disabled="working || chat.pending || chat.busy"
            aria-label="删除这段对话"
            @click="remove(conversation.id)"
          >
            删除
          </button>
        </article>
        <p class="memory-caption">
          展示最近50段，最多保留100段。默认保留90天；删除对话后不再参与回忆。
        </p>
      </div>
      <button
        class="forget-memory"
        :disabled="working || chat.pending || chat.busy"
        @click="forget"
      >
        清除全部记忆与历史
      </button>
    </div>
  </el-drawer>
</template>
<style scoped>
.memory-panel {
  color: var(--tp-ink);
}
.memory-tabs {
  display: flex;
  border-bottom: 1px solid var(--tp-line);
  gap: 14px;
}
.memory-tabs button {
  border: 0;
  padding: 10px 5px;
  background: none;
  color: var(--tp-muted);
  cursor: pointer;
}
.memory-tabs .selected {
  color: var(--tp-muted);
  border-bottom: 2px solid var(--tp-line);
}
.memory-caption {
  font-size: 11px;
  color: var(--tp-muted);
  line-height: 1.8;
}
.memory-error {
  color: #b76659;
  font-size: 12px;
  line-height: 1.8;
}
.preference-form {
  display: grid;
  gap: 16px;
  margin-top: 20px;
}
.preference-form label {
  display: grid;
  gap: 8px;
  font-size: 12px;
}
.preference-form input,
.preference-form select {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--tp-line);
  padding: 11px;
  border-radius: 9px;
  background: #fffdfc;
  font: inherit;
  color: var(--tp-ink);
}
.preference-form small {
  color: var(--tp-muted);
  font-size: 10px;
}
.save-preferences {
  border: 0;
  background: var(--tp-muted);
  color: white;
  border-radius: 10px;
  padding: 12px;
  cursor: pointer;
}
.forget-memory {
  display: block;
  background: none;
  border: 1px solid var(--tp-line);
  border-radius: 9px;
  color: var(--tp-muted);
  padding: 11px 14px;
  margin-top: 30px;
  cursor: pointer;
  width: 100%;
}
.history-list article {
  display: flex;
  align-items: center;
  border-bottom: 1px solid #eee;
  border-radius: 8px;
}
.history-list .current {
  background: var(--tp-surface-soft);
}
.history-open {
  flex: 1;
  min-width: 0;
  border: 0;
  background: none;
  text-align: left;
  padding: 15px 9px;
  cursor: pointer;
}
.history-open strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--tp-ink);
  font-size: 13px;
  font-weight: 500;
}
.history-open span {
  display: block;
  font-size: 10px;
  color: var(--tp-muted);
  margin-top: 8px;
}
.history-delete {
  background: none;
  border: 0;
  color: var(--tp-muted);
  font-size: 11px;
  padding: 12px;
  cursor: pointer;
}
button:disabled {
  opacity: 0.45;
  cursor: default;
}
</style>
