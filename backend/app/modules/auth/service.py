from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import Depends

from app.core.config import settings
from app.core.database import DbSession
from app.modules.auth.dtos import AuthSessionResponseDTO, LoginRequestDTO, SessionInfoDTO
from app.modules.auth.exceptions import (
    InactiveUserException,
    InvalidCredentialsException,
    NotAuthenticatedException,
    SessionExpiredException,
)
from app.modules.auth.model import SessionEndReason, UserSession
from app.modules.auth.repository import SessionRepository
from app.modules.auth.security import (
    burn_password_check,
    generate_session_token,
    hash_session_token,
    verify_password,
)
from app.modules.users.dtos import UserResponseDTO
from app.modules.users.model import User
from app.modules.users.repository import UserRepository


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def idle_timeout() -> timedelta:
    return timedelta(minutes=settings.session_idle_timeout_minutes)


def absolute_timeout() -> timedelta:
    return timedelta(minutes=settings.session_absolute_timeout_minutes)


def compute_expires_at(created_at: datetime, last_activity_at: datetime) -> datetime:
    return min(as_utc(last_activity_at) + idle_timeout(), as_utc(created_at) + absolute_timeout())


def remaining_seconds(expires_at: datetime, now: datetime) -> int:
    return max(0, int((as_utc(expires_at) - now).total_seconds()))


@dataclass(frozen=True)
class SessionState:
    active: bool
    expires_at: datetime | None = None
    reason: SessionEndReason | Literal["not_authenticated"] | None = None


class AuthService:
    def __init__(self, users: UserRepository, sessions: SessionRepository) -> None:
        self.users = users
        self.sessions = sessions

    def login(
        self,
        payload: LoginRequestDTO,
        ip_address: str | None,
        user_agent: str | None,
        previous_token: str | None = None,
    ) -> tuple[str, AuthSessionResponseDTO]:
        """Valida as credenciais e abre uma sessão nova. Devolve o token (vai só no
        cookie) e o DTO de resposta. A sessão anterior do mesmo navegador é encerrada."""
        user = self.users.get_by_login(payload.username)
        if user is None:
            burn_password_check(payload.password)
            raise InvalidCredentialsException()
        if not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsException()
        if not user.is_active:
            raise InactiveUserException()

        self.logout(previous_token)
        token = generate_session_token()
        now = utcnow()
        session = self.sessions.add(
            UserSession(
                token_hash=hash_session_token(token),
                user_id=user.id,
                created_at=now,
                last_activity_at=now,
                expires_at=compute_expires_at(now, now),
                ip_address=ip_address,
                user_agent=(user_agent or "")[:512] or None,
            )
        )
        return token, self.build_response(user, session)

    def logout(self, token: str | None) -> None:
        """Encerra a sessão do token, se existir. Idempotente."""
        if not token:
            return
        session = self.sessions.get_by_token_hash(hash_session_token(token))
        if session is not None:
            self._end(session, SessionEndReason.LOGOUT, utcnow())

    # ---------- validação ----------

    def authenticate(self, token: str | None, *, touch: bool) -> tuple[User, UserSession]:
        """Valida o token do cookie. Com `touch=True` registra atividade e empurra a
        expiração por inatividade para frente (é o que acontece em todo request autenticado)."""
        if not token:
            raise NotAuthenticatedException()
        return self._validate(self.sessions.get_by_token_hash(hash_session_token(token)), touch=touch)

    def authenticate_session_id(self, session_id: int, *, touch: bool) -> tuple[User, UserSession]:
        """Como `authenticate`, mas pela sessão do ticket de conexão do WebSocket."""
        return self._validate(self.sessions.get_by_id(session_id), touch=touch)

    def _validate(self, session: UserSession | None, *, touch: bool) -> tuple[User, UserSession]:
        if session is None:
            raise NotAuthenticatedException()

        now = utcnow()
        user = self.users.get_by_id(session.user_id)
        reason = self._end_reason(session, now)
        if reason is None and (user is None or not user.is_active):
            reason = SessionEndReason.REVOKED
        if reason is not None:
            self._end(session, reason, now)
            raise SessionExpiredException(reason)
        assert user is not None

        if touch:
            session.last_activity_at = now
            session.expires_at = compute_expires_at(session.created_at, now)
            self.sessions.save()
        return user, session

    def peek(self, token: str | None) -> SessionState:
        try:
            _, session = self.authenticate(token, touch=False)
        except SessionExpiredException as exc:
            return SessionState(active=False, reason=exc.reason)
        except NotAuthenticatedException:
            return SessionState(active=False, reason="not_authenticated")
        return SessionState(active=True, expires_at=as_utc(session.expires_at))

    def build_response(self, user: User, session: UserSession) -> AuthSessionResponseDTO:
        return AuthSessionResponseDTO(
            user=UserResponseDTO.model_validate(user),
            session=SessionInfoDTO(
                created_at=as_utc(session.created_at),
                expires_at=as_utc(session.expires_at),
                remaining_seconds=remaining_seconds(
                    session.expires_at, utcnow()),
                idle_timeout_minutes=settings.session_idle_timeout_minutes,
            ),
        )

    @staticmethod
    def _end_reason(session: UserSession, now: datetime) -> SessionEndReason | None:
        if session.ended_at is not None:
            return session.end_reason or SessionEndReason.REVOKED
        if now >= as_utc(session.created_at) + absolute_timeout():
            return SessionEndReason.ABSOLUTE_TIMEOUT
        if now >= as_utc(session.last_activity_at) + idle_timeout():
            return SessionEndReason.IDLE_TIMEOUT
        return None

    def _end(self, session: UserSession, reason: SessionEndReason, now: datetime) -> None:
        if session.ended_at is None:
            session.ended_at = now
            session.end_reason = reason
            self.sessions.save()


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(UserRepository(db), SessionRepository(db))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
