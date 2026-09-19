from pydantic import Field

from app.modules.users.model import UserRole
from app.shared.dtos import BaseDTO


class UserResponseDTO(BaseDTO):
    """Dados públicos do usuário. Nunca inclui a senha."""

    id: int = Field(examples=[1])
    username: str = Field(examples=["admin"])
    email: str = Field(examples=["admin@pureelectric.com.br"])
    full_name: str | None = Field(default=None, examples=["Administrador"])
    role: UserRole = Field(
        description="Serve só para o frontend decidir o que exibir; quem autoriza é o backend",
        examples=[UserRole.ADMIN],
    )
    is_active: bool = Field(examples=[True])
