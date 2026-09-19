"""Primitivas de segurança: hash de senha (bcrypt) e token opaco de sessão."""

import hashlib
import secrets
from functools import lru_cache

import bcrypt

from app.core.config import settings

# bcrypt só considera os primeiros 72 bytes da senha
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"A senha pode ter no máximo {BCRYPT_MAX_BYTES} bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=settings.password_hash_rounds)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


@lru_cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


def burn_password_check(password: str) -> None:
    """Gasta o mesmo tempo de um bcrypt real quando o usuário não existe, para
    não revelar pelo tempo de resposta quais usernames estão cadastrados."""
    verify_password(password, _dummy_hash())


def generate_session_token() -> str:
    """Token opaco de 256 bits. Vai só no cookie; o banco guarda o hash."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
