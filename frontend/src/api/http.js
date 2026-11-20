export class ApiError extends Error {
  constructor(message, { status, payload } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

function extractMessage(payload, status) {
  const detail = payload?.detail
  if (typeof detail === 'string') return detail
  // ошибки валидации FastAPI: [{loc, msg}]
  if (Array.isArray(detail)) {
    return detail.map((e) => `${(e.loc || []).slice(1).join('.') || 'поле'}: ${e.msg}`).join('; ')
  }
  return `Ошибка запроса (${status})`
}

async function request(method, url, body) {
  const init = { method, headers: { Accept: 'application/json' } }
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(`/api${url}`, init)
  } catch {
    throw new ApiError('Сервер недоступен. Запущен ли бэкенд?', { status: 0 })
  }

  const text = await response.text()
  const payload = text ? JSON.parse(text) : null
  if (!response.ok) {
    throw new ApiError(extractMessage(payload, response.status), {
      status: response.status,
      payload,
    })
  }
  return payload
}

export const http = {
  get: (url) => request('GET', url),
  post: (url, body) => request('POST', url, body ?? {}),
  put: (url, body) => request('PUT', url, body ?? {}),
  delete: (url) => request('DELETE', url),
}
