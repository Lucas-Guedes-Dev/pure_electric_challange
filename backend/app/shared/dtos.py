from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseDTO(BaseModel):
    """Base de todos os DTOs: permite construir a partir de models do ORM."""

    model_config = ConfigDict(from_attributes=True)


class PageDTO(BaseDTO, Generic[T]):
    """Resposta paginada genérica, ex.: PageDTO[CompraResponseDTO]."""

    items: list[T]
    total: int = Field(description="Total de registros", examples=[42])
    page: int = Field(description="Página atual", examples=[1])
    size: int = Field(description="Itens por página", examples=[20])


class PaginationParamsDTO(BaseDTO):
    page: int = Field(default=1, ge=1, description="Número da página (começa em 1)")
    size: int = Field(default=20, ge=1, le=100, description="Itens por página (máx. 100)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class MessageResponseDTO(BaseDTO):
    message: str


class ErrorResponseDTO(BaseDTO):
    detail: str = Field(description="Mensagem do erro")
    code: str | None = Field(
        default=None,
        description="Código estável para o frontend tratar o erro (ex.: SESSION_EXPIRED)",
        examples=["SESSION_EXPIRED"],
    )
