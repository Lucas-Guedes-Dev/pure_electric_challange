from datetime import datetime
from typing import Literal

from pydantic import Field

from app.modules.auth.model import SessionEndReason
from app.modules.users.dtos import UserResponseDTO
from app.shared.dtos import BaseDTO


class LoginRequestDTO(BaseDTO):
    username: str = Field(
        min_length=1,
        max_length=255,
        description="Username ou e-mail",
        examples=["admin"],
    )
    password: str = Field(min_length=1, max_length=128,
                          examples=["senha-forte-123"])


class SessionInfoDTO(BaseDTO):
    created_at: datetime = Field(
        description="Quando a sessão foi aberta (login)")
    expires_at: datetime = Field(
        description="Quando a sessão expira se não houver nova requisição. Renova a cada request autenticado."
    )
    remaining_seconds: int = Field(
        description="Segundos até `expires_at`", examples=[1800])
    idle_timeout_minutes: float = Field(
        description="Minutos de inatividade até deslogar", examples=[30]
    )


class WsTicketResponseDTO(BaseDTO):
    ticket: str = Field(description="Enviar no connection_init do WebSocket: `{ \"ticket\": \"...\" }`")
    expires_in_seconds: int = Field(description="Validade do ticket (só para abrir a conexão)", examples=[60])


class AuthSessionResponseDTO(BaseDTO):
    """Resposta de login, /me e /refresh: quem está logado e até quando."""

    user: UserResponseDTO
    session: SessionInfoDTO


# ---------- Eventos do stream SSE (GET /api/auth/events) ----------


class SessionEventDTO(BaseDTO):
    """`event: session` (estado atual) e `event: expiring` (aviso antes de expirar)."""

    expires_at: datetime
    remaining_seconds: int


class LogoutEventDTO(BaseDTO):
    """`event: logout`: o frontend deve limpar o estado e ir para o login."""

    reason: SessionEndReason | Literal["not_authenticated"]
    detail: str
