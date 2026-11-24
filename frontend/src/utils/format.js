/** 'DE' → 🇩🇪 */
export function flag(code) {
  if (!code || code.length !== 2) return ''
  return String.fromCodePoint(...[...code.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65))
}

export function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value.includes('T') ? value : value.replace(' ', 'T') + 'Z')
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
}

/** '24.11.2026, 15:33' */
export function formatDateShort(value) {
  if (!value) return '—'
  const date = new Date(value.includes('T') ? value : value.replace(' ', 'T') + 'Z')
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export const STREAM_TYPES = {
  forced: { label: 'Перехватывающий', tone: 'blue' },
  regular: { label: 'Обычный', tone: 'teal' },
  default: { label: 'Резервный', tone: 'slate' },
}

export const STATES = {
  active: { label: 'Активна', tone: 'green' },
  disabled: { label: 'Выключена', tone: 'slate' },
  deleted: { label: 'В архиве', tone: 'red' },
}
