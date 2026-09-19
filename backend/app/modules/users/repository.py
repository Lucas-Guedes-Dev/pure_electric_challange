from sqlalchemy import func, or_, select

from app.modules.users.model import User
from app.shared.repository import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_login(self, login: str) -> User | None:
        """Busca por username ou e-mail, sem diferenciar maiúsculas."""
        value = login.strip().lower()
        stmt = select(User).where(
            or_(func.lower(User.username) == value, func.lower(User.email) == value)
        )
        return self.db.scalars(stmt).first()
