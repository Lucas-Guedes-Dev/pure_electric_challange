import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.model import Base


class SessionEndReason(str, enum.Enum):
    LOGOUT = "logout"  # usuário clicou em sair
    IDLE_TIMEOUT = "idle_timeout"  # ficou sem requisições além do limite (padrão: 30 min)
    ABSOLUTE_TIMEOUT = "absolute_timeout"  # passou do tempo máximo de vida da sessão
    REVOKED = "revoked"  # encerrada pelo backend (ex.: usuário desativado)


class UserSession(Base):
    """Sessão de login guardada no banco. O cookie do navegador carrega só um token
    aleatório; aqui fica apenas o hash SHA-256 dele, então um vazamento do banco não
    permite sequestrar sessões."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_reason: Mapped[SessionEndReason | None] = mapped_column(
        Enum(SessionEndReason, name="session_end_reason"), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
