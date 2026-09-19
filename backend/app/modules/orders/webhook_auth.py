"""Autenticação de quem envia pedidos (REST e GraphQL usam a mesma regra)."""

import hmac

from fastapi import status

from app.core.config import settings
from app.shared.exceptions import AppException

WEBHOOK_KEY_HEADER = "X-Webhook-Key"


class InvalidWebhookKeyException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_WEBHOOK_KEY"


def check_webhook_key(key: str | None) -> None:
    expected = settings.orders_webhook_key
    if not expected:
        return  # sem chave configurada: webhook aberto (apenas desenvolvimento)
    # compare_digest: comparação em tempo constante, não vaza a chave pelo tempo de resposta
    if not key or not hmac.compare_digest(key.encode(), expected.encode()):
        raise InvalidWebhookKeyException(
            f"Chave do webhook ausente ou inválida (header {WEBHOOK_KEY_HEADER})"
        )
