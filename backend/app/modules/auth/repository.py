from sqlalchemy import select

from app.modules.auth.model import UserSession
from app.shared.repository import BaseRepository


class SessionRepository(BaseRepository[UserSession]):
    model = UserSession

    def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        stmt = select(UserSession).where(UserSession.token_hash == token_hash)
        return self.db.scalars(stmt).first()

    def save(self) -> None:
        self.db.commit()
