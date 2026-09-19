const API_BASE_URL = import.meta.env.VITE_API_URL ?? '/api'

type QueryParams = Record<string, string | number | boolean | undefined | null>

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown
  /** `code` do ErrorResponseDTO do backend, quando houver (ex.: "SESSION_EXPIRED") */
  readonly code: string | null

  constructor(status: number, message: string, body: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
    this.code = extractCode(body)
  }
}

/** URL absoluta de um caminho da API (ex.: para abrir um EventSource) */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

// Chamado quando o backend responde 401 de sessão (expirou, foi encerrada ou não existe).
// Registrado pelo SessionProvider, que desloga o usuário no app.
type UnauthorizedHandler = (error: ApiError) => void
let unauthorizedHandler: UnauthorizedHandler | null = null

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler
}

const SESSION_ERROR_CODES = new Set(['SESSION_EXPIRED', 'NOT_AUTHENTICATED'])

function buildUrl(path: string, params?: QueryParams): string {
  const url = apiUrl(path)
  if (!params) return url
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) search.append(key, String(value))
  }
  const query = search.toString()
  return query ? `${url}?${query}` : url
}

function extractMessage(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const { detail } = body as { detail: unknown }
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? String(d)).join('; ')
  }
  return fallback
}

function extractCode(body: unknown): string | null {
  if (body && typeof body === 'object' && 'code' in body) {
    const { code } = body as { code: unknown }
    if (typeof code === 'string') return code
  }
  return null
}

async function request<TResponse>(
  method: string,
  path: string,
  options: { body?: unknown; params?: QueryParams } = {},
): Promise<TResponse> {
  const response = await fetch(buildUrl(path, options.params), {
    method,
    // Envia o cookie HttpOnly de sessão (também se a API estiver em outra origem)
    credentials: 'include',
    headers: options.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (response.status === 204) return undefined as TResponse

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const error = new ApiError(response.status, extractMessage(body, response.statusText), body)
    if (response.status === 401 && error.code && SESSION_ERROR_CODES.has(error.code)) {
      unauthorizedHandler?.(error)
    }
    throw error
  }
  return body as TResponse
}

export const httpClient = {
  get: <TResponse>(path: string, params?: QueryParams) =>
    request<TResponse>('GET', path, { params }),
  post: <TResponse, TBody = unknown>(path: string, body?: TBody) =>
    request<TResponse>('POST', path, { body }),
  put: <TResponse, TBody = unknown>(path: string, body: TBody) =>
    request<TResponse>('PUT', path, { body }),
  patch: <TResponse, TBody = unknown>(path: string, body: TBody) =>
    request<TResponse>('PATCH', path, { body }),
  delete: <TResponse = void>(path: string) => request<TResponse>('DELETE', path),
}
