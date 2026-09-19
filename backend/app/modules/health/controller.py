from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import DbSession
from app.modules.health.dtos import HealthResponseDTO

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=HealthResponseDTO,
    summary="Healthcheck",
    description="Retorna `ok` quando a API e o banco respondem, ou `degraded` se o banco estiver fora.",
)
def health_check(db: DbSession) -> HealthResponseDTO:
    try:
        db.execute(text("SELECT 1"))
        database = "up"
    except SQLAlchemyError:
        database = "down"
    return HealthResponseDTO(
        status="ok" if database == "up" else "degraded",
        database=database,
        version=settings.app_version,
    )
