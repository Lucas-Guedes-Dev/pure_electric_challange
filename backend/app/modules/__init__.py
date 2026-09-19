import importlib
import pkgutil

from fastapi import APIRouter

from app.modules.auth.controller import router as auth_router
from app.modules.health.controller import router as health_router
from app.modules.orders.controller import router as orders_router

# Registre aqui o router de cada módulo novo
api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(orders_router)


def import_all_models() -> None:
    """Importa o model.py de todos os módulos para registrá-los no Base.metadata
    (usado pelo Alembic e pelos testes). Módulos novos entram automaticamente."""
    for module in pkgutil.iter_modules(__path__):
        if module.ispkg:
            try:
                importlib.import_module(f"{__name__}.{module.name}.model")
            except ModuleNotFoundError as exc:
                if exc.name != f"{__name__}.{module.name}.model":
                    raise


__all__ = ["api_router", "import_all_models"]
