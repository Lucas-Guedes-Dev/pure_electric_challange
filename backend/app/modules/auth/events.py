"""Stream SSE (Server-Sent Events) com o estado da sessão.

O backend é quem decide quando a sessão acaba e avisa o navegador por aqui:
    event: session   -> estado atual (reenviado sempre que a expiração muda)
    event: expiring  -> faltam `session_warning_seconds` para expirar
    event: logout    -> sessão encerrada; o frontend deve fechar o stream e ir para o login

O stream só LÊ a sessão: ficar conectado nele não conta como atividade.
"""

import asyncio
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.modules.auth.dtos import LogoutEventDTO, SessionEventDTO
from app.modules.auth.exceptions import END_REASON_MESSAGES
from app.modules.auth.repository import SessionRepository
from app.modules.auth.service import AuthService, SessionState, remaining_seconds, utcnow
from app.modules.users.repository import UserRepository
from app.shared.dtos import BaseDTO

# Tempo que o navegador espera antes de reconectar se a conexão cair
RETRY_MS = 5000


def format_sse(event: str, data: BaseDTO) -> str:
    return f"event: {event}\ndata: {data.model_dump_json()}\n\n"


def read_session_state(factory: sessionmaker[Session], token: str | None) -> SessionState:
    # Abre uma sessão de banco própria a cada leitura: o stream fica aberto por muito
    # tempo e não pode segurar uma conexão do pool.
    with factory() as db:
        return AuthService(UserRepository(db), SessionRepository(db)).peek(token)


def logout_event(state: SessionState) -> str:
    assert state.reason is not None
    if state.reason == "not_authenticated":
        detail = "Você não está logado."
    else:
        detail = END_REASON_MESSAGES[state.reason]
    return format_sse("logout", LogoutEventDTO(reason=state.reason, detail=detail))


async def session_event_stream(
    request: Request,
    factory: sessionmaker[Session],
    token: str | None,
    initial_state: SessionState,
) -> AsyncIterator[str]:
    yield f"retry: {RETRY_MS}\n\n"

    state = initial_state
    last_expires_at = None
    warned = False

    while True:
        if not state.active:
            yield logout_event(state)
            return

        assert state.expires_at is not None
        now = utcnow()
        remaining = remaining_seconds(state.expires_at, now)

        if state.expires_at != last_expires_at:
            # A sessão foi renovada (ou é o primeiro envio): manda o novo prazo
            last_expires_at = state.expires_at
            warned = warned and remaining <= settings.session_warning_seconds
            yield format_sse(
                "session", SessionEventDTO(expires_at=state.expires_at, remaining_seconds=remaining)
            )

        if not warned and remaining <= settings.session_warning_seconds:
            warned = True
            yield format_sse(
                "expiring", SessionEventDTO(expires_at=state.expires_at, remaining_seconds=remaining)
            )

        # Comentário SSE: mantém a conexão viva em proxies e detecta cliente desconectado
        yield ": ping\n\n"
        if await request.is_disconnected():
            return

        # Dorme até a próxima checagem ou até o instante exato da expiração
        seconds_left = (state.expires_at - utcnow()).total_seconds()
        await asyncio.sleep(max(0.05, min(settings.session_events_poll_seconds, seconds_left + 0.05)))
        state = await run_in_threadpool(read_session_state, factory, token)
