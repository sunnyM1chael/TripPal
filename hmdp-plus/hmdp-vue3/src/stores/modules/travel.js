import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import {
  chatWithTravel,
  loadTravelState,
  loadConversation,
  removeConversation,
  savePreferences,
  forgetTravelMemory
} from '@/api/travel'
import { useUserStore } from './user'

export const useTravelStore = defineStore('travel-chat', () => {
  const messages = ref([])
  const draft = ref('')
  const pending = ref(false)
  const busy = ref(false)
  const conversationId = ref(null)
  const conversations = ref([])
  const preferences = ref({})
  const guest = ref(true)
  const initialized = ref(false)
  const memoryError = ref('')
  const mapsConfigured = ref(false)
  const selectedCity = ref('')
  const canRetry = computed(() => messages.value.at(-1)?.state === 'error')
  let controller = null
  let generation = 0
  let nextId = 0
  let initialization = null
  let pollTimer = null

  function cancel() {
    generation++
    controller?.abort()
    controller = null
    pending.value = false
    const last = messages.value.at(-1)
    if (last?.state === 'pending') {
      last.state = 'cancelled'
      last.content =
        '已停止等待。服务端可能仍在生成，可从历史对话重新打开查看。'
    }
  }

  function reset() {
    cancel()
    clearTimeout(pollTimer)
    busy.value = false
    conversationId.value = null
    messages.value = []
    draft.value = ''
  }

  async function refreshState() {
    const account = useUserStore().token
    const data = await loadTravelState()
    if (account !== useUserStore().token) return
    conversations.value = data.conversations
    preferences.value = data.preferences
    guest.value = data.guest
    mapsConfigured.value = data.maps_configured
    if (!selectedCity.value)
      selectedCity.value = data.preferences.default_city || ''
    initialized.value = true
    memoryError.value = ''
    return data
  }

  async function initialize() {
    if (initialized.value) return
    if (initialization) return initialization
    initialization = (async () => {
      try {
        const data = await refreshState()
        if (
          !conversationId.value &&
          !messages.value.length &&
          data?.conversations.length
        ) {
          await openConversation(data.conversations[0].id)
        }
      } catch (error) {
        memoryError.value = error.message
      } finally {
        initialization = null
      }
    })()
    return initialization
  }

  async function openConversation(id) {
    if (pending.value) throw new Error('请等当前回复完成后再切换历史。')
    const account = useUserStore().token
    const turn = ++generation
    clearTimeout(pollTimer)
    const data = await loadConversation(id)
    if (account !== useUserStore().token || turn !== generation) return
    conversationId.value = data.id
    busy.value = data.busy
    draft.value = ''
    messages.value = data.turns.flatMap((row) => [
      { id: ++nextId, role: 'user', content: row.prompt, state: 'complete' },
      {
        id: ++nextId,
        role: 'assistant',
        content: row.output,
        state: row.mode === 'live' ? 'complete' : 'configuration',
        tools: row.tools,
        skills: [
          ...new Set(
            row.tools
              .filter(
                (item) => item.tool === 'load_travel_skill' && item.data?.loaded
              )
              .map((item) => item.data.skill)
          )
        ],
        stopped: Boolean(row.stopped)
      }
    ])
    if (data.busy) {
      pollTimer = setTimeout(() => {
        if (conversationId.value === id && !pending.value) {
          openConversation(id).catch((error) => {
            memoryError.value = error.message
          })
        }
      }, 4000)
    }
  }

  async function send(text, skill = null) {
    const account = useUserStore().token
    const prompt = text.trim()
    if (!prompt || prompt.length > 4000 || pending.value || busy.value) return
    if (!initialized.value) await initialize()
    if (account !== useUserStore().token) return
    if (pending.value || busy.value) return
    const user = {
      id: ++nextId,
      role: 'user',
      content: prompt,
      skill,
      state: 'complete'
    }
    const reply = {
      id: ++nextId,
      role: 'assistant',
      content: '',
      state: 'pending',
      tools: []
    }
    messages.value.push(user, reply)
    const assistantMessage = messages.value.at(-1)
    draft.value = ''
    pending.value = true
    const turn = ++generation
    controller = new AbortController()
    try {
      const result = await chatWithTravel(
        {
          prompt,
          skill,
          conversation_id: conversationId.value,
          city: selectedCity.value || null
        },
        controller.signal
      )
      if (generation !== turn) return
      conversationId.value = result.conversation_id || conversationId.value
      assistantMessage.content = result.output
      assistantMessage.tools = result.tool_results
      assistantMessage.skills = result.loaded_skills || []
      assistantMessage.state =
        result.mode === 'live' ? 'complete' : 'configuration'
      assistantMessage.stopped = Boolean(result.stopped)
      await refreshState().catch((error) => {
        memoryError.value = error.message
      })
    } catch (error) {
      if (generation !== turn) return
      assistantMessage.state = 'error'
      assistantMessage.content = error.message || '消息发送失败，请稍后重试。'
    } finally {
      if (generation === turn) {
        pending.value = false
        controller = null
      }
    }
  }

  function retry() {
    if (!canRetry.value || pending.value) return
    const previous = messages.value.at(-2)
    const prompt = previous?.content
    if (!prompt) return
    messages.value.splice(-2)
    return send(prompt, previous.skill)
  }

  async function updatePreferences(patch) {
    const account = useUserStore().token
    const data = await savePreferences(patch)
    if (account !== useUserStore().token) return
    preferences.value = data.preferences
    if ('default_city' in patch) selectedCity.value = patch.default_city || ''
  }

  async function deleteConversation(id) {
    await removeConversation(id)
    if (conversationId.value === id) reset()
    await refreshState()
  }

  async function forget() {
    const account = useUserStore().token
    try {
      await forgetTravelMemory()
    } catch (error) {
      if (
        account === useUserStore().token &&
        error.response?.data?.code === 'preference_clear_pending'
      ) {
        reset()
        conversations.value = []
      }
      throw error
    }
    if (account !== useUserStore().token) return
    reset()
    preferences.value = {}
    conversations.value = []
    selectedCity.value = ''
  }

  watch(
    () => useUserStore().token,
    () => {
      reset()
      initialized.value = false
      initialization = null
      preferences.value = {}
      conversations.value = []
      selectedCity.value = ''
      memoryError.value = ''
    },
    { flush: 'sync' }
  )
  return {
    messages,
    draft,
    pending,
    busy,
    canRetry,
    conversationId,
    conversations,
    preferences,
    guest,
    initialized,
    memoryError,
    mapsConfigured,
    selectedCity,
    initialize,
    refreshState,
    openConversation,
    send,
    retry,
    cancel,
    reset,
    updatePreferences,
    deleteConversation,
    forget
  }
})
