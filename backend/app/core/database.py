from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, echo=settings.debug)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency do FastAPI que abre uma sessão por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]


def get_session_factory() -> sessionmaker[Session]:
    """Para código que precisa abrir sessões próprias fora do ciclo do request
    (ex.: streams de eventos longos). Sobrescrito nos testes."""
    return SessionLocal


SessionFactory = Annotated[sessionmaker[Session], Depends(get_session_factory)]
