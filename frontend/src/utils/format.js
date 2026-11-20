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

export const STREAM_TYPES = {
  forced: { label: 'Перехват', tone: 'amber' },
  regular: { label: 'Обычный', tone: 'teal' },
  default: { label: 'Резервный', tone: 'slate' },
}

export const STATES = {
  active: { label: 'Активна', tone: 'green' },
  disabled: { label: 'Выключена', tone: 'slate' },
  deleted: { label: 'В архиве', tone: 'red' },
}
