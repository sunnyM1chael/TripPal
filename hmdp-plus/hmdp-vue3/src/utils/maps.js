export function safeMapUrl(value) {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' &&
      url.hostname === 'uri.amap.com' &&
      url.pathname === '/navigation'
      ? url.href
      : ''
  } catch {
    return ''
  }
}

export function navigationFor(place, mode = 'driving') {
  const link = safeMapUrl(place?.navigation_url)
  if (!link) return ''
  const url = new URL(link)
  url.searchParams.set('mode', mode === 'walking' ? 'walk' : 'car')
  return url.href
}

export function navigationForShop(shop) {
  if (shop?.x == null || shop?.y == null) return ''
  const longitude = Number(shop.x),
    latitude = Number(shop.y)
  if (
    !Number.isFinite(longitude) ||
    !Number.isFinite(latitude) ||
    Math.abs(longitude) > 180 ||
    Math.abs(latitude) > 90
  )
    return ''
  const url = new URL('https://uri.amap.com/navigation')
  url.searchParams.set(
    'to',
    `${longitude},${latitude},${String(shop.name || '目的地').replaceAll(',', ' ')}`
  )
  url.searchParams.set('mode', 'car')
  url.searchParams.set('src', 'TripPal')
  url.searchParams.set('callnative', '1')
  return url.href
}

export const formatDistance = (meters) =>
  typeof meters === 'number'
    ? meters < 1000
      ? `${Math.round(meters)} 米`
      : `${(meters / 1000).toFixed(1)} 公里`
    : '距离待确认'
export const formatDuration = (seconds) =>
  typeof seconds === 'number'
    ? seconds >= 3600
      ? `${Math.floor(seconds / 3600)} 小时 ${Math.ceil((seconds % 3600) / 60)} 分钟`
      : `约 ${Math.max(1, Math.ceil(seconds / 60))} 分钟`
    : '耗时待确认'
