import { useEffect, useState } from 'react'
import type { HealthResponseDTO } from '../dtos/health.dto'
import { healthService } from '../services/healthService'
import { Badge } from './ui'

export function HealthBadge() {
  const [health, setHealth] = useState<HealthResponseDTO | null>(null)
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    healthService
      .check()
      .then(setHealth)
      .catch(() => setOffline(true))
  }, [])

  if (offline) return <Badge $variant="danger">API offline</Badge>
  if (!health) return <Badge>Verificando API…</Badge>

  const ok = health.status === 'ok'
  return (
    <Badge $variant={ok ? 'success' : 'danger'}>
      API v{health.version} · banco {health.database === 'up' ? 'conectado' : 'indisponível'}
    </Badge>
  )
}
