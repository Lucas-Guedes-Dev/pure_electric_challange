"""Ticket de conexão do WebSocket (subscriptions GraphQL).

Em produção o frontend (Vercel) fala com a API pelo rewrite `/api/*` do próprio Vercel, então
o cookie de sessão fica no domínio do frontend. O Vercel não repassa WebSocket: a conexão vai
direto ao domínio da API, e o navegador não manda esse cookie para lá.

Solução: o frontend pede um ticket em `POST /api/auth/ws-ticket` (pelo rewrite, com o cookie)
e o envia no `connection_init` do WebSocket. O ticket:
- é assinado (HMAC-SHA256 com SECRET_KEY): não dá para forjar nem alterar;
- vale poucos segundos (WS_TICKET_TTL_SECONDS): só serve para abrir a conexão;
- aponta para a sessão, não para o usuário: se a sessão acabar, a conexão é encerrada como
  sempre (as subscriptions continuam conferindo a sessão).
O token da sessão nunca vai para o JavaScript.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import settings
from app.modules.auth.exceptions import NotAuthenticatedException

# Sem SECRET_KEY: segredo aleatório deste processo (tickets valem só nesta réplica da API)
_FALLBACK_SECRET = secrets.token_bytes(32)


def _secret() -> bytes:
    return settings.secret_key.encode() if settings.secret_key else _FALLBACK_SECRET


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())


def issue_ticket(session_id: int, now: float | None = None) -> str:
    expires_at = int((now if now is not None else time.time()) + settings.ws_ticket_ttl_seconds)
    payload = _b64(json.dumps({"sid": session_id, "exp": expires_at}, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload)}"


def read_ticket(ticket: str, now: float | None = None) -> int:
    """Devolve o id da sessão do ticket. Ticket inválido ou vencido: NotAuthenticatedException."""
    payload, _, signature = ticket.partition(".")
    if not payload or not signature or not hmac.compare_digest(signature, _sign(payload)):
        raise NotAuthenticatedException()
    try:
        data = json.loads(_unb64(payload))
        session_id, expires_at = int(data["sid"]), int(data["exp"])
    except (ValueError, KeyError, TypeError):
        raise NotAuthenticatedException() from None
    if (now if now is not None else time.time()) > expires_at:
        raise NotAuthenticatedException()
    return session_id
