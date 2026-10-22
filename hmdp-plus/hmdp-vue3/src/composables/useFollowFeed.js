import { ref } from 'vue'

export function useFollowFeed(fetchPage) {
  const blogs = ref([])
  const loading = ref(false)
  const finished = ref(false)
  const error = ref('')
  let cursor = { lastId: Date.now(), offset: 0 }

  const load = async (reset = false) => {
    if (loading.value || (!reset && finished.value)) return
    if (reset) {
      cursor = { lastId: Date.now(), offset: 0 }
      blogs.value = []
      finished.value = false
    }
    loading.value = true
    error.value = ''
    try {
      const response = await fetchPage({ ...cursor })
      if (!response || response.success === false) {
        throw new Error(response?.errorMsg || '获取关注博客失败')
      }
      const data = response.data
      const list = data?.list ?? []
      if (!Array.isArray(list)) throw new Error('关注动态数据格式异常')
      if (!list.length) {
        finished.value = true
        return
      }
      const seen = new Set(blogs.value.map((blog) => String(blog.id)))
      blogs.value.push(...list.filter((blog) => !seen.has(String(blog.id))))
      cursor = { lastId: data.minTime, offset: data.offset }
    } catch (cause) {
      error.value = cause.message || '获取关注博客失败'
    } finally {
      loading.value = false
    }
  }

  return { blogs, loading, finished, error, load }
}
