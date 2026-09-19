/**
 * Sessão do usuário no navegador.
 *
 * Quem manda na sessão é o backend: o token fica num cookie HttpOnly que o
 * JavaScript não lê. Aqui guardamos só uma cópia em memória do que o backend
 * respondeu em /api/auth/me (usuário, role e prazo), atualizada pelo
 * SessionProvider com os eventos do stream /api/auth/events.
 *
 * Tudo aqui é conveniência de navegação, nunca autorização: quem barra de
 * verdade é o backend, validando o cookie em cada rota.
 *
 * VITE_AUTH_ENABLED=false libera as rotas sem login (útil para desenvolver telas
 * sem backend). Por padrão o login é exigido.
 */
import { useSyncExternalStore } from 'react'
import { ApiError } from '../api/httpClient'
import type { AuthSessionResponseDTO, UserResponseDTO } from '../dtos/auth.dto'
import { authService } from '../services/authService'

export type SessionStatus = 'loading' | 'authenticated' | 'anonymous'

export interface SessionState {
  /** `loading` enquanto o app ainda não perguntou ao backend se há sessão */
  status: SessionStatus
  user: UserResponseDTO | null
  /** Quando a sessão expira se não houver nova requisição (ISO 8601) */
  expiresAt: string | null
  /** O backend avisou que a sessão está para expirar (evento `expiring`) */
  expiring: boolean
  /** Motivo do último logout forçado, para mostrar na tela de login */
  endReason: string | null
}

export function isAuthEnabled(): boolean {
  return import.meta.env.VITE_AUTH_ENABLED !== 'false'
}

let state: SessionState = {
  status: isAuthEnabled() ? 'loading' : 'anonymous',
  user: null,
  expiresAt: null,
  expiring: false,
  endReason: null,
}

const listeners = new Set<() => void>()

function setState(patch: Partial<SessionState>): void {
  state = { ...state, ...patch }
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function getSession(): SessionState {
  return state
}

/** Chamado após login ou /me: o backend confirmou a sessão. */
export function startSession({ user, session }: AuthSessionResponseDTO): void {
  setState({
    status: 'authenticated',
    user,
    expiresAt: session.expires_at,
    expiring: false,
    endReason: null,
  })
}

/** Atualiza o prazo (eventos `session` / `expiring` ou após /refresh). */
export function updateSession(patch: Partial<Pick<SessionState, 'expiresAt' | 'expiring'>>): void {
  if (state.status === 'authenticated') setState(patch)
}

/**
 * Apaga a sessão local. Com `reason`, a tela de login mostra o motivo
 * (ex.: "Sua sessão expirou por inatividade"). Leva o `user` junto: se ficar
 * para trás, o menu de administração continua aparecendo.
 */
export function clearSession(reason: string | null = null): void {
  setState({ status: 'anonymous', user: null, expiresAt: null, expiring: false, endReason: reason })
}

export function isAuthenticated(session: SessionState = state): boolean {
  return !isAuthEnabled() || session.status === 'authenticated'
}

export function isAdmin(session: SessionState = state): boolean {
  if (!isAuthEnabled()) return true
  return session.user?.role === 'ADMIN'
}

/** Pergunta ao backend se há sessão (o cookie HttpOnly vai sozinho). */
export async function loadSession(): Promise<void> {
  try {
    startSession(await authService.me())
  } catch (error) {
    // 401 = ninguém logado. Na abertura do app, qualquer falha (ex.: API fora do ar)
    // também cai no login. Já logado, uma falha de rede passageira não desloga.
    const unauthorized = error instanceof ApiError && error.status === 401
    if (unauthorized || state.status === 'loading') clearSession(state.endReason)
  }
}

/** Sai por vontade própria: encerra no servidor e limpa o estado local. */
export async function logout(): Promise<void> {
  try {
    await authService.logout()
  } finally {
    clearSession()
  }
}

/**
 * Sessão reativa para componentes: re-renderiza quando o usuário entra, sai
 * ou quando o backend manda o sinal de logout.
 */
export function useSession() {
  const session = useSyncExternalStore(subscribe, getSession)
  return {
    ...session,
    isAuthenticated: isAuthenticated(session),
    isAdmin: isAdmin(session),
  }
}
