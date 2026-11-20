import { ref, shallowRef } from 'vue'

/**
 * Обёртка над асинхронной функцией: data / error / loading + run().
 * @param {(...args: any[]) => Promise<any>} fn
 * @param {{ immediate?: boolean, initial?: any }} options
 */
export function useAsync(fn, { immediate = false, initial = null } = {}) {
  const data = shallowRef(initial)
  const error = ref(null)
  const loading = ref(false)

  async function run(...args) {
    loading.value = true
    error.value = null
    try {
      data.value = await fn(...args)
      return data.value
    } catch (e) {
      error.value = e
      throw e
    } finally {
      loading.value = false
    }
  }

  if (immediate) run().catch(() => {})

  return { data, error, loading, run }
}
