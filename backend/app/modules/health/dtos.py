from typing import Literal

from app.shared.dtos import BaseDTO


class HealthResponseDTO(BaseDTO):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]
    version: str
