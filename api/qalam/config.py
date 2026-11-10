from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Everything here comes from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(
        default="postgresql+psycopg://qalam:qalam@localhost:5432/qalam",
        validation_alias=AliasChoices("QALAM_DATABASE_URL", "DATABASE_URL"),
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("QALAM_REDIS_URL", "REDIS_URL"),
    )
    storage_dir: str = Field(default="var/uploads", validation_alias="QALAM_STORAGE_DIR")
    samples_dir: str = Field(default="samples", validation_alias="QALAM_SAMPLES_DIR")
    host: str = Field(default="0.0.0.0", validation_alias="QALAM_HOST")
    port: int = Field(default=8000, validation_alias="QALAM_PORT")
    log_level: str = Field(default="INFO", validation_alias="QALAM_LOG_LEVEL")
    cors_origins: str = Field(default="http://localhost", validation_alias="QALAM_CORS_ORIGINS")
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, validation_alias="QALAM_MAX_UPLOAD_BYTES")
    rate_limit_per_minute: int = Field(default=60, validation_alias="QALAM_RATE_LIMIT_PER_MINUTE")
    tasks_eager: bool = Field(default=False, validation_alias="QALAM_TASKS_EAGER")
    seed_demo: bool = Field(default=False, validation_alias="QALAM_SEED_DEMO")

    bootstrap_email: str = Field(default="", validation_alias="QALAM_BOOTSTRAP_EMAIL")
    bootstrap_name: str = Field(default="Admin", validation_alias="QALAM_BOOTSTRAP_NAME")
    bootstrap_api_key: str = Field(default="", validation_alias="QALAM_BOOTSTRAP_API_KEY")
    bootstrap_workspace: str = Field(default="Library", validation_alias="QALAM_BOOTSTRAP_WORKSPACE")

    embedding_backend: str = Field(
        default="sentence-transformers",
        validation_alias="QALAM_EMBEDDING_BACKEND",
    )
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        validation_alias="QALAM_EMBEDDING_MODEL",
    )
    embedding_dim: int = Field(default=384, validation_alias="QALAM_EMBEDDING_DIM")

    chunk_size: int = Field(default=1200, validation_alias="QALAM_CHUNK_SIZE")
    chunk_overlap: int = Field(default=150, validation_alias="QALAM_CHUNK_OVERLAP")
    retrieval_top_k: int = Field(default=5, validation_alias="QALAM_RETRIEVAL_TOP_K")
    llm_input_chars: int = Field(default=14000, validation_alias="QALAM_LLM_INPUT_CHARS")

    llm_chain: str = Field(
        default="inception,nvidia,exaone,openrouter,mock",
        validation_alias="QALAM_LLM_CHAIN",
    )
    llm_timeout_s: float = Field(default=45.0, validation_alias="QALAM_LLM_TIMEOUT_S")
    llm_retries: int = Field(default=2, validation_alias="QALAM_LLM_RETRIES")
    llm_retry_backoff_s: float = Field(default=0.5, validation_alias="QALAM_LLM_RETRY_BACKOFF_S")
    llm_breaker_threshold: int = Field(default=4, validation_alias="QALAM_LLM_BREAKER_THRESHOLD")
    llm_breaker_cooldown_s: float = Field(default=30.0, validation_alias="QALAM_LLM_BREAKER_COOLDOWN_S")

    inception_api_key: str = Field(default="", validation_alias="INCEPTION_API_KEY")
    inception_base_url: str = Field(
        default="https://api.inceptionlabs.ai/v1",
        validation_alias="INCEPTION_BASE_URL",
    )
    inception_model: str = Field(default="mercury-3", validation_alias="INCEPTION_MODEL")
    inception_timeout_s: float | None = Field(default=None, validation_alias="INCEPTION_TIMEOUT_S")
    inception_retries: int | None = Field(default=None, validation_alias="INCEPTION_RETRIES")

    nvidia_api_key: str = Field(default="", validation_alias="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        validation_alias="NVIDIA_BASE_URL",
    )
    nvidia_model: str = Field(
        default="nvidia/llama-3.1-nemotron-70b-instruct",
        validation_alias="NVIDIA_MODEL",
    )
    nvidia_timeout_s: float | None = Field(default=None, validation_alias="NVIDIA_TIMEOUT_S")
    nvidia_retries: int | None = Field(default=None, validation_alias="NVIDIA_RETRIES")

    exaone_api_key: str = Field(default="", validation_alias="EXAONE_API_KEY")
    exaone_base_url: str = Field(
        default="https://api.friendli.ai/serverless/v1",
        validation_alias="EXAONE_BASE_URL",
    )
    exaone_model: str = Field(
        default="LGAI-EXAONE/EXAONE-4.0.1-32B",
        validation_alias="EXAONE_MODEL",
    )
    exaone_timeout_s: float | None = Field(default=None, validation_alias="EXAONE_TIMEOUT_S")
    exaone_retries: int | None = Field(default=None, validation_alias="EXAONE_RETRIES")

    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias="OPENROUTER_BASE_URL",
    )
    openrouter_model: str = Field(default="openrouter/free", validation_alias="OPENROUTER_MODEL")
    openrouter_timeout_s: float | None = Field(default=None, validation_alias="OPENROUTER_TIMEOUT_S")
    openrouter_retries: int | None = Field(default=None, validation_alias="OPENROUTER_RETRIES")

    @field_validator("database_url", mode="before")
    @classmethod
    def psycopg_driver(cls, value: Any) -> Any:
        # Hosted Postgres providers hand out postgres:// or postgresql:// URLs.
        # SQLAlchemy needs the psycopg driver named explicitly.
        if isinstance(value, str):
            for prefix in ("postgres://", "postgresql://"):
                if value.startswith(prefix):
                    return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @field_validator(
        "inception_timeout_s",
        "inception_retries",
        "nvidia_timeout_s",
        "nvidia_retries",
        "exaone_timeout_s",
        "exaone_retries",
        "openrouter_timeout_s",
        "openrouter_retries",
        mode="before",
    )
    @classmethod
    def blank_optional(cls, value: Any) -> Any:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        return value

    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        return init_settings, env_settings, dotenv_settings, file_secret_settings


def get_settings() -> Settings:
    return Settings()
