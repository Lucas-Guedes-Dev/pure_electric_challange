from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.model import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Acesso a dados genérico. Repositórios concretos herdam e adicionam queries específicas."""

    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, entity_id: Any) -> ModelT | None:
        return self.db.get(self.model, entity_id)

    def list(self, *, offset: int = 0, limit: int = 20) -> Sequence[ModelT]:
        stmt = select(self.model).order_by(self.model.id).offset(offset).limit(limit)  # type: ignore[attr-defined]
        return self.db.scalars(stmt).all()

    def count(self) -> int:
        return self.db.scalar(select(func.count()).select_from(self.model)) or 0

    def add(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: ModelT, data: dict[str, Any]) -> ModelT:
        for field, value in data.items():
            setattr(entity, field, value)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, entity: ModelT) -> None:
        self.db.delete(entity)
        self.db.commit()
