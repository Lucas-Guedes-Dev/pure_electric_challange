// Espelham backend/app/modules/auth/dtos.py e backend/app/modules/users/dtos.py

export type UserRole = 'ADMIN' | 'USER'

export interface UserResponseDTO {
  id: number
  username: string
  email: string
  full_name: string | null
  role: UserRole
  is_active: boolean
}

export interface LoginRequestDTO {
  /** Username ou e-mail */
  username: string
  password: string
}

export interface SessionInfoDTO {
  created_at: string
  /** Renova a cada request autenticado */
  expires_at: string
  remaining_seconds: number
  idle_timeout_minutes: number
}

/** Resposta de login, /me e /refresh */
export interface AuthSessionResponseDTO {
  user: UserResponseDTO
  session: SessionInfoDTO
}

/** POST /api/auth/ws-ticket: abre o WebSocket quando ele está em outro domínio que o cookie */
export interface WsTicketResponseDTO {
  ticket: string
  expires_in_seconds: number
}

// ---------- Eventos do stream SSE (GET /api/auth/events) ----------

/** `event: session` e `event: expiring` */
export interface SessionEventDTO {
  expires_at: string
  remaining_seconds: number
}

export type SessionEndReason =
  | 'logout'
  | 'idle_timeout'
  | 'absolute_timeout'
  | 'revoked'
  | 'not_authenticated'

/** `event: logout` */
export interface LogoutEventDTO {
  reason: SessionEndReason
  detail: string
}
