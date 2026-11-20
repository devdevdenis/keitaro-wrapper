import { ref } from 'vue'

const toasts = ref([])
let seq = 0

export function useToast() {
  function dismiss(id) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  function push(message, tone = 'success', timeout = 4000) {
    const id = ++seq
    toasts.value = [...toasts.value, { id, message, tone }]
    if (timeout) setTimeout(() => dismiss(id), timeout)
  }

  return {
    toasts,
    dismiss,
    success: (message) => push(message, 'success'),
    error: (message) => push(message, 'error', 7000),
  }
}
