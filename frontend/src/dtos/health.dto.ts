// Espelha backend/app/dtos/health_dto.py

export interface HealthResponseDTO {
  status: 'ok' | 'degraded'
  database: 'up' | 'down'
  version: string
}
