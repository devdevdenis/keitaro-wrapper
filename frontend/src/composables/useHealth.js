import { ref } from 'vue'
import { api } from '@/api'

const health = ref(null)
let started = false

/** Состояние бэкенда и подключения к Keitaro (live / not_configured). */
export function useHealth() {
  async function refresh() {
    try {
      health.value = await api.health()
    } catch {
      health.value = { status: 'down', keitaro: 'unknown' }
    }
  }

  if (!started) {
    started = true
    refresh()
  }

  return { health, refresh }
}
