import { useEffect, useState } from 'react'

/** Hora atual, atualizada a cada `intervalMs` (para textos como "há 2 minutos"). */
export function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs)
    return () => window.clearInterval(timer)
  }, [intervalMs])
  return now
}
