import type { FieldError } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: FieldError[]
  readonly requestId: string | null

  constructor(
    status: number,
    code: string,
    message: string,
    details: FieldError[] = [],
    requestId: string | null = null,
  ) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
    this.requestId = requestId
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  json?: unknown
}

/** Call the backend. Every error, including a lost connection, becomes an ApiError. */
export async function api<T>(
  path: string,
  { method = 'GET', json }: RequestOptions = {},
): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers: json === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: json === undefined ? undefined : JSON.stringify(json),
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Нет связи с сервером. Проверьте, что бэкенд запущен.')
  }

  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const error = body?.error
    throw new ApiError(
      response.status,
      error?.code ?? 'http_error',
      error?.message ?? `Сервер ответил ошибкой ${response.status}`,
      error?.details ?? [],
      error?.request_id ?? response.headers.get('X-Request-ID'),
    )
  }
  return body as T
}
