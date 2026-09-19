/** Formatação pt-BR de valores e datas vindos da API. */
import type { DecimalString } from '../dtos/common.dto'

const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const dateTime = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'medium' })
const time = new Intl.DateTimeFormat('pt-BR', { timeStyle: 'medium' })
const relative = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' })

/** "150.00" -> "R$ 150,00". Decimal chega como string; só vira número para exibir. */
export function formatCurrency(value: DecimalString): string {
  return currency.format(Number(value))
}

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso))
}

export function formatTime(iso: string): string {
  return time.format(new Date(iso))
}

/** "agora", "há 30 segundos", "há 2 minutos", "há 3 horas", "ontem"... */
export function formatRelative(iso: string, now: number = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000)
  // Um instante "no futuro" só acontece por diferença de relógio ou porque `now` é de alguns
  // segundos atrás (a tela atualiza o relógio a cada 30 s): para o usuário, é "agora".
  if (seconds > 0) return 'agora'
  const abs = Math.abs(seconds)
  if (abs < 10) return 'agora'
  if (abs < 60) return relative.format(seconds, 'second')
  if (abs < 3600) return relative.format(Math.round(seconds / 60), 'minute')
  if (abs < 86400) return relative.format(Math.round(seconds / 3600), 'hour')
  return relative.format(Math.round(seconds / 86400), 'day')
}

/** 175 -> "175 ms"; 5012 -> "5,0 s" */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1).replace('.', ',')} s`
}

/** 68 -> "1:08" */
export function formatCountdown(totalSeconds: number): string {
  const safe = Math.max(0, Math.ceil(totalSeconds))
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, '0')}`
}
