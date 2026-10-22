import axios from 'axios'
import JSONbig from 'json-bigint'
import { useUserStore } from '@/stores/modules/user'

// Separate from the Java client: the Agent returns its own envelope and may take two minutes.
const travelClient = axios.create({
  baseURL: '/agent-api',
  timeout: 125000,
  transformResponse: [
    (data) => (data ? JSONbig({ storeAsString: true }).parse(data) : data)
  ]
})

travelClient.interceptors.request.use((config) => {
  const token = useUserStore().token
  if (token) config.headers.Authorization = token
  return config
})

travelClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const code = error.response?.data?.code
    if (
      [
        'map_not_configured',
        'map_unavailable',
        'conversation_busy',
        'request_limit',
        'authentication_required',
        'memory_unavailable',
        'preference_clear_pending',
        'not_found'
      ].includes(code) ||
      code?.startsWith('itinerary_') ||
      code?.startsWith('operation_')
    ) {
      error.message = error.response.data.message
    } else if (error.response?.status === 401) {
      error.message = '登录状态已过期，请重新登录。'
    } else if (error.response?.status === 422) {
      error.message = '输入格式有误，请检查后重试。'
    } else {
      error.message = '暂时无法连接服务，请稍后重试。'
    }
    return Promise.reject(error)
  }
)

export const loadTravelState = () =>
  travelClient.get('/api/v1/travel/state').then((r) => r.data)
export const getVoucherSubscription = (shopId, voucherId) =>
  travelClient
    .get('/api/v1/voucher-subscriptions/status', {
      params: { shop_id: shopId, voucher_id: voucherId }
    })
    .then((r) => r.data)
export const prepareVoucherSubscription = (shopId, voucherId, action) =>
  travelClient
    .post('/api/v1/voucher-subscriptions/prepare', {
      shop_id: shopId,
      voucher_id: voucherId,
      action
    })
    .then((r) => r.data)
export const confirmVoucherSubscription = (actionId, acceptAutoIssue) =>
  travelClient
    .post(
      `/api/v1/voucher-subscriptions/${encodeURIComponent(actionId)}/confirm`,
      {
        confirmed: true,
        accept_auto_issue: acceptAutoIssue
      }
    )
    .then((r) => r.data)
export const listNotifications = (params = {}) =>
  travelClient
    .get('/api/v1/notifications', { params, timeout: 15000 })
    .then((r) => r.data)
export const readNotification = (id) =>
  travelClient.post(`/api/v1/notifications/${encodeURIComponent(id)}/read`)
export const readAllNotifications = () =>
  travelClient.post('/api/v1/notifications/read-all')
export const listItineraries = () =>
  travelClient.get('/api/v1/itineraries').then((r) => r.data.itineraries)
export const getItinerary = (id) =>
  travelClient
    .get(`/api/v1/itineraries/${encodeURIComponent(id)}`)
    .then((r) => r.data)
export const saveVisitFeedback = (id, stopId, payload) =>
  travelClient
    .put(
      `/api/v1/itineraries/${encodeURIComponent(id)}/stops/${encodeURIComponent(stopId)}/feedback`,
      payload
    )
    .then((r) => r.data)
export const createItinerary = (payload) =>
  travelClient.post('/api/v1/itineraries', payload).then((r) => r.data)
export const editItinerary = (id, payload) =>
  travelClient
    .patch(`/api/v1/itineraries/${encodeURIComponent(id)}`, payload)
    .then((r) => r.data)
export const deleteItinerary = (id, revision) =>
  travelClient.delete(`/api/v1/itineraries/${encodeURIComponent(id)}`, {
    params: { expected_revision: revision }
  })
export const loadConversation = (id) =>
  travelClient
    .get(`/api/v1/travel/conversations/${encodeURIComponent(id)}`)
    .then((r) => r.data)
export const removeConversation = (id) =>
  travelClient.delete(`/api/v1/travel/conversations/${encodeURIComponent(id)}`)
export const savePreferences = (preferences) =>
  travelClient
    .put('/api/v1/travel/preferences', preferences)
    .then((r) => r.data)
export const forgetTravelMemory = () =>
  travelClient.delete('/api/v1/travel/memory')
export const searchCities = (keyword) =>
  travelClient
    .get('/api/v1/maps/cities', { params: { keyword } })
    .then((r) => r.data)
export const searchPlaces = (city, keyword, page = 1) =>
  travelClient
    .get('/api/v1/maps/places', { params: { city, keyword, page } })
    .then((r) => r.data)
export const placeDetail = (id) =>
  travelClient
    .get(`/api/v1/maps/places/${encodeURIComponent(id)}`)
    .then((r) => r.data)
export const planMapRoute = (payload) =>
  travelClient.post('/api/v1/maps/route', payload).then((r) => r.data)

export async function chatWithTravel(payload, signal) {
  const token = useUserStore().token
  try {
    const { data } = await travelClient.post('/api/v1/travel/chat', payload, {
      signal,
      headers: token ? { Authorization: token } : {}
    })
    if (typeof data?.output !== 'string' || !Array.isArray(data.tool_results)) {
      throw new Error('暂时无法读取回复，请稍后重试。')
    }
    return data
  } catch (error) {
    if (axios.isCancel(error)) throw error
    if (error.code === 'ECONNABORTED' || error.response?.status === 504) {
      throw new Error('这次查询用时较长，请缩小范围后重试。')
    }
    if (error.response?.status === 401) {
      throw new Error('登录状态已过期，请重新登录后再试。')
    }
    if (error.response?.status === 422) {
      throw new Error('消息过长或格式有误，请精简后再试。')
    }
    if (
      ['conversation_busy', 'request_limit', 'not_found'].includes(
        error.response?.data?.code
      )
    ) {
      throw new Error(error.message)
    }
    if (error.response?.data?.code?.startsWith('llm_')) {
      throw new Error('AI 服务暂时无法回复，请稍后重试。')
    }
    if (!error.response || error.response.status >= 500) {
      throw new Error('暂时连接不上旅伴，请稍后重试。')
    }
    throw new Error('消息发送失败，请稍后重试。')
  }
}
