/** Estado da conexão em tempo real (WebSocket do GraphQL), para o indicador "ao vivo". */
import { useSyncExternalStore } from 'react'

export type LiveStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting'

let status: LiveStatus = 'idle'
const listeners = new Set<() => void>()

export function setLiveStatus(next: LiveStatus): void {
  if (next === status) return
  status = next
  listeners.forEach((listener) => listener())
}

export function useLiveStatus(): LiveStatus {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => status,
  )
}
