import { defineStore } from 'pinia'
import { ref } from 'vue'
import { listNotifications } from '@/api/travel'
import { useUserStore } from '@/stores/modules/user'

export const useNotificationStore = defineStore('notifications', () => {
  const unread = ref(0)
  async function refresh() {
    const account = useUserStore().token
    try {
      const data = await listNotifications({ unread_only: true })
      if (account === useUserStore().token) unread.value = data.unread_count
    } catch {
      if (account === useUserStore().token) unread.value = 0
    }
  }
  return { unread, refresh }
})
