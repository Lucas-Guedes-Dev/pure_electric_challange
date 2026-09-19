from fastapi import APIRouter, Request, Response, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import SessionFactory
from app.core.rate_limit import limiter
from app.modules.auth.cookies import delete_session_cookie, set_session_cookie
from app.modules.auth.dependencies import CurrentAuth, SessionToken
from app.modules.auth.dtos import AuthSessionResponseDTO, LoginRequestDTO, WsTicketResponseDTO
from app.modules.auth.events import read_session_state, session_event_stream
from app.modules.auth.service import AuthServiceDep
from app.modules.auth.ws_ticket import issue_ticket
from app.shared.dtos import ErrorResponseDTO

router = APIRouter(prefix="/auth", tags=["Auth"])

UNAUTHORIZED = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponseDTO,
        "description": "Sem sessão (`NOT_AUTHENTICATED`) ou sessão expirada (`SESSION_EXPIRED`). "
        "A resposta apaga o cookie.",
    }
}


@router.post(
    "/login",
    response_model=AuthSessionResponseDTO,
    summary="Login",
    description=(
        "Valida usuário (ou e-mail) e senha e abre uma sessão no servidor. O token da sessão "
        "vai **somente** no cookie HttpOnly `Set-Cookie`, nunca no corpo: o JavaScript do "
        "navegador não tem acesso a ele.\n\n"
        f"A sessão expira após **{settings.session_idle_timeout_minutes:g} minutos sem "
        "requisições** (cada request autenticado renova o prazo) ou ao atingir o tempo máximo "
        "de vida. Limite de tentativas por IP: "
        f"`{settings.login_rate_limit}`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponseDTO,
            "description": "Usuário ou senha inválidos (`INVALID_CREDENTIALS`)",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponseDTO,
            "description": "Usuário inativo (`USER_INACTIVE`)",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ErrorResponseDTO,
            "description": "Muitas tentativas (`RATE_LIMITED`)",
        },
    },
)
@limiter.limit(settings.login_rate_limit)
def login(
    request: Request,
    response: Response,
    payload: LoginRequestDTO,
    service: AuthServiceDep,
    current_token: SessionToken,
) -> AuthSessionResponseDTO:
    token, result = service.login(
        payload,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        previous_token=current_token,
    )
    set_session_cookie(response, token)
    return result


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Encerra a sessão no servidor e apaga o cookie. Idempotente: responde 204 "
    "mesmo sem sessão ativa. Os streams de eventos abertos com essa sessão recebem `logout`.",
)
def logout(service: AuthServiceDep, token: SessionToken) -> Response:
    service.logout(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    delete_session_cookie(response)
    return response


@router.get(
    "/me",
    response_model=AuthSessionResponseDTO,
    summary="Usuário logado",
    description="Retorna o usuário e o estado da sessão. Use ao carregar o app para saber "
    "se há alguém logado. Conta como atividade (renova o prazo de inatividade).",
    responses=UNAUTHORIZED,
)
def me(auth: CurrentAuth, service: AuthServiceDep) -> AuthSessionResponseDTO:
    return service.build_response(auth.user, auth.session)


@router.post(
    "/refresh",
    response_model=AuthSessionResponseDTO,
    summary="Continuar conectado",
    description="Renova o prazo de inatividade sem fazer mais nada. Use no botão "
    '"continuar conectado" quando chegar o evento `expiring`.',
    responses=UNAUTHORIZED,
)
def refresh(auth: CurrentAuth, service: AuthServiceDep) -> AuthSessionResponseDTO:
    return service.build_response(auth.user, auth.session)


@router.post(
    "/ws-ticket",
    response_model=WsTicketResponseDTO,
    summary="Ticket do WebSocket",
    description=(
        "Ticket de curta duração para abrir o WebSocket do GraphQL (`/api/graphql`) quando ele "
        "está em outro domínio que o cookie de sessão (ex.: frontend no Vercel com a API no "
        "Railway). Envie no `connection_init`: `{\"ticket\": \"...\"}`. Não renova a sessão."
    ),
    responses=UNAUTHORIZED,
)
def ws_ticket(service: AuthServiceDep, token: SessionToken) -> WsTicketResponseDTO:
    _, session = service.authenticate(token, touch=False)
    return WsTicketResponseDTO(ticket=issue_ticket(session.id), expires_in_seconds=settings.ws_ticket_ttl_seconds)


@router.get(
    "/events",
    summary="Eventos da sessão (SSE)",
    description=(
        "Stream **Server-Sent Events** (`text/event-stream`) pelo qual o backend avisa o "
        "navegador sobre a sessão. Abra com `new EventSource('/api/auth/events')`.\n\n"
        "| Evento | Quando | `data` |\n"
        "|---|---|---|\n"
        "| `session` | ao conectar e sempre que o prazo muda | `{ expires_at, remaining_seconds }` |\n"
        f"| `expiring` | faltam {settings.session_warning_seconds}s para expirar "
        "| `{ expires_at, remaining_seconds }` |\n"
        "| `logout` | a sessão acabou (inatividade, tempo máximo, logout em outra aba, "
        "usuário desativado) | `{ reason, detail }` |\n\n"
        "Ao receber `logout`, o frontend deve chamar `eventSource.close()` e ir para o login. "
        "Ficar conectado aqui **não** renova a sessão. Sem cookie de sessão a resposta é "
        "`204`, o que faz o `EventSource` parar de reconectar."
    ),
    response_class=StreamingResponse,
    responses={
        status.HTTP_200_OK: {
            "content": {"text/event-stream": {}},
            "description": "Stream de eventos",
        },
        status.HTTP_204_NO_CONTENT: {"description": "Sem cookie de sessão"},
    },
)
async def session_events(
    request: Request, factory: SessionFactory, token: SessionToken
) -> Response:
    if not token:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    initial_state = await run_in_threadpool(read_session_state, factory, token)
    response = StreamingResponse(
        session_event_stream(request, factory, token, initial_state),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    if not initial_state.active:
        delete_session_cookie(response)
    return response
