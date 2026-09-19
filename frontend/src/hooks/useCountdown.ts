import { useEffect, useState } from 'react'

/** Segundos que faltam até `target` (ISO 8601), atualizado a cada segundo. `null` sem alvo. */
export function useCountdown(target: string | null | undefined): number | null {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!target) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [target])

  if (!target) return null
  return Math.max(0, Math.ceil((Date.parse(target) - now) / 1000))
}
