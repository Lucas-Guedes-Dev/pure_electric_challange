from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Alguns bancos (ex.: SQLite nos testes) devolvem datetime sem fuso."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
