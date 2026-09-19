import { apiUrl, httpClient } from '../api/httpClient'
import type { AuthSessionResponseDTO, LoginRequestDTO, WsTicketResponseDTO } from '../dtos/auth.dto'

export const authService = {
  /** Abre a sessão. O token volta só no cookie HttpOnly, nunca no corpo. */
  login: (payload: LoginRequestDTO) =>
    httpClient.post<AuthSessionResponseDTO, LoginRequestDTO>('/auth/login', payload),

  /** Encerra a sessão no servidor e apaga o cookie. Idempotente. */
  logout: () => httpClient.post<void>('/auth/logout'),

  /** Quem está logado. Responde 401 se não houver sessão válida. */
  me: () => httpClient.get<AuthSessionResponseDTO>('/auth/me'),

  /** "Continuar conectado": renova o prazo de inatividade. */
  refresh: () => httpClient.post<AuthSessionResponseDTO>('/auth/refresh'),

  /** Ticket de curta duração para abrir o WebSocket do GraphQL (não renova a sessão). */
  wsTicket: () => httpClient.post<WsTicketResponseDTO>('/auth/ws-ticket'),

  /** Stream SSE pelo qual o backend avisa sobre a sessão (session / expiring / logout). */
  events: () => new EventSource(apiUrl('/auth/events'), { withCredentials: true }),
}
