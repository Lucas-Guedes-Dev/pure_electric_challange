from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Desafio Técnico Pure Eletric API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    debug: bool = False
    # Expõe Swagger UI (/api/docs), ReDoc (/api/redoc) e o schema (/api/openapi.json)
    docs_enabled: bool = True

    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "pure_eletric"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Lista separada por vírgula, ex.: "http://localhost:5173,http://127.0.0.1:5173"
    cors_origins: str = "http://localhost:5173"

    # --- Sessão (controlada 100% pelo backend, token opaco em cookie HttpOnly) ---
    # Desloga após N minutos sem nenhuma requisição autenticada (renova a cada request)
    session_idle_timeout_minutes: float = 30
    # Limite máximo de vida da sessão, mesmo com uso contínuo
    session_absolute_timeout_minutes: float = 8 * 60
    # Quantos segundos antes de expirar o backend envia o aviso "expiring" no stream de eventos
    session_warning_seconds: int = 120
    # De quanto em quanto tempo o stream de eventos confere o estado da sessão
    session_events_poll_seconds: float = 5
    session_cookie_name: str = "pe_session"
    # true em produção (HTTPS). Em dev (http://localhost) precisa ser false
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # --- Logs ---
    log_level: str = "INFO"
    # Aparece como service.name / service.environment nos logs do Kibana
    service_name: str = "pure-eletric-api"
    environment: str = "development"
    # Para onde os logs são enviados, ex.: "http://elasticsearch:9200". Vazio = só console
    elasticsearch_url: str | None = None
    # Data stream no padrão logs-<dataset>-<namespace> (usa o template de logs nativo do ES)
    elasticsearch_logs_data_stream: str = "logs-pure_eletric.api-default"

    # --- Segurança do login ---
    password_hash_rounds: int = 12
    rate_limit_enabled: bool = True
    login_rate_limit: str = "5/minute"

    # --- Pedidos (webhook + processamento assíncrono) ---
    # Chave que o sistema externo envia no header X-Webhook-Key. Vazio = webhook aberto (só dev)
    orders_webhook_key: str | None = None
    # Sistema interno (mock) para onde o worker encaminha os pedidos
    internal_system_url: str = "http://localhost:9000"
    internal_system_timeout_seconds: float = 5
    # Tentativas por pedido (a 1ª + retentativas) em falhas temporárias
    order_max_attempts: int = 3
    # Espera antes da retentativa: base * 2^(tentativa-1) segundos (5s, 10s, 20s...)
    order_retry_base_seconds: float = 5
    # Tempo que um pedido fica reservado para um worker. Se o worker morrer, outro
    # retoma depois disso. Precisa ser maior que o timeout do sistema interno.
    order_lease_seconds: float = 60
    worker_poll_seconds: float = 1
    worker_batch_size: int = 10
    # Simulador de pedidos na interface (mutation simulateOrders). Só para demonstração/dev
    order_simulator_enabled: bool = False

    # --- Eventos de pedidos em tempo real (Postgres LISTEN/NOTIFY -> subscription GraphQL) ---
    order_events_channel: str = "order_events"
    # Liga o listener do LISTEN na API. Desligado nos testes (não há Postgres)
    order_events_listener_enabled: bool = True

    # --- GraphQL (/api/graphql) ---
    graphql_max_depth: int = 8
    graphql_max_aliases: int = 15
    graphql_max_tokens: int = 2000
    # Introspection (o schema consultável). Vazio = segue DOCS_ENABLED
    graphql_introspection: bool | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def psycopg_conninfo(self) -> str:
        """URL para o psycopg puro (sem o "+psycopg" do SQLAlchemy), usada pelo LISTEN."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
