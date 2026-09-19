// Espelham os DTOs do backend (backend/app/shared/dtos.py)

/** Valores Decimal do backend chegam como string para não perder precisão (ex.: "199.90") */
export type DecimalString = string

export interface PageDTO<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface PaginationParamsDTO {
  page?: number
  size?: number
}

export interface ErrorResponseDTO {
  detail: string
  /** Código estável para tratar o erro, ex.: "SESSION_EXPIRED", "INVALID_CREDENTIALS" */
  code?: string | null
}

/** Formato do erro 422 de validação do FastAPI/Pydantic */
export interface ValidationErrorDTO {
  detail: Array<{ loc: (string | number)[]; msg: string; type: string }>
}
