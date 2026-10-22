import axios from 'axios'
import { useUserStore } from '@/stores/modules/user'

// A separate adapter preserves HTTP failures instead of swallowing a login error.
export async function workshop(path, method = 'get', data) {
  const token = useUserStore().token
  try {
    const response = await axios({
      url: `/api/workshop${path}`,
      method,
      data,
      timeout: 15000,
      headers: token ? { Authorization: token } : {}
    })
    if (!response.data?.success)
      throw new Error(response.data?.errorMsg || '操作未完成，请稍后重试')
    return response.data.data
  } catch (error) {
    const status = error.response?.status
    if (status === 401) throw new Error('请先登录后再收藏、发布或加入行程。')
    if (status === 404 || status === 502 || status === 503) {
      throw new Error('吃玩工坊服务尚未就绪，请确认新版后端已启动。')
    }
    if (status >= 500) {
      throw new Error('吃玩工坊暂时无法加载，请稍后重试。')
    }
    throw new Error(
      error.response?.data?.errorMsg || error.message || '暂时无法连接服务'
    )
  }
}
export const stopTemplate = () => ({
  name: '',
  address: '',
  kind: 'FOOD',
  advice: '',
  longitude: null,
  latitude: null,
  minutes: 60,
  cost: 0
})
export const workTemplate = (city = '') => ({
  title: '',
  city,
  theme: 'FOOD',
  description: '',
  audience: '',
  allowRemix: true,
  status: 'DRAFT',
  version: 0,
  sourceId: null,
  changeNote: '',
  stops: [stopTemplate()]
})
export function navigationUrl(stop) {
  return `https://uri.amap.com/navigation?to=${encodeURIComponent(`${stop.longitude},${stop.latitude},${stop.name}`)}&mode=walk&coordinate=gaode&callnative=0`
}
