import { httpClient } from '../api/httpClient'
import type { HealthResponseDTO } from '../dtos/health.dto'

export const healthService = {
  check: () => httpClient.get<HealthResponseDTO>('/health'),
}
