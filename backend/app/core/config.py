from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET_KEY = "change-this-in-production"


class Settings(BaseSettings):
    app_name: str = "Advanced Business RAG Chatbot API"
    app_version: str = "0.3.0"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False
    log_level: str = "INFO"
    log_format: str = "json"
    database_echo: bool = False
    jwt_secret_key: str = DEFAULT_JWT_SECRET_KEY
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_minutes: int = 60 * 24 * 7
    jwt_issuer: str = "advanced-business-rag-chatbot"
    jwt_audience: str = "workspace-users"
    frontend_url: str = "http://localhost:3000"
    cors_allowed_origins: list[str] = ["http://localhost:3000"]
    widget_public_api_base_url: str = "http://localhost:8000"
    widget_script_url: str = "http://localhost:3000/widget.js"
    widget_sdk_version: str = "1.0.0"
    widget_token_expire_minutes: int = 60
    enforce_https_in_production: bool = True
    allow_destructive_migrations: bool = False
    secure_cookie_samesite: str = "lax"
    security_hsts_seconds: int = 31536000
    login_rate_limit_count: int = 5
    login_rate_limit_window_seconds: int = 300
    api_rate_limit_count: int = 300
    api_rate_limit_window_seconds: int = 60
    chat_rate_limit_count: int = 30
    chat_rate_limit_window_seconds: int = 60
    max_login_failures: int = 5
    account_lock_minutes: int = 15
    webhook_signing_secret: str = ""
    openai_api_key: str = ""
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0
    redis_url: str = "redis://localhost:6379/0"
    task_queue_enabled: bool = False
    task_queue_name: str = "rag-tasks"
    task_queue_timeout_seconds: int = 5
    worker_mode: str = "inline"
    database_url: str | None = None
    postgres_db: str = "rag_chatbot"
    postgres_user: str = "rag_admin"
    postgres_password: str = "rag_password"
    postgres_port: int = 5432
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_collection_name: str = "document_chunks"
    qdrant_distance_metric: str = "Cosine"
    embedding_provider: str = "local"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_batch_size: int = 16
    local_embedding_model: str = "BAAI/bge-small-en-v1.5"
    local_embedding_cache_dir: str = "/tmp/fastembed-cache"
    openai_max_retries: int = 4
    openai_reranker_model: str = "gpt-4.1-mini"
    openai_chat_model: str = "gpt-4.1-mini"
    openai_transcription_model: str = "gpt-4o-mini-transcribe"
    openai_tts_model: str = "gpt-4o-mini-tts"
    voice_default_tts_format: str = "mp3"
    voice_backend_input_provider: str = "openai"
    voice_backend_output_provider: str = "openai"
    retrieval_vector_top_k: int = 20
    retrieval_keyword_top_k: int = 20
    retrieval_hybrid_top_k: int = 10
    retrieval_final_top_k: int = 5
    retrieval_context_token_limit: int = 3200
    website_crawler_max_pages: int = 25
    website_crawler_max_depth: int = 1
    website_crawler_timeout_seconds: int = 15
    website_crawler_request_delay_seconds: float = 0.6
    website_crawler_max_parallel_requests: int = 3
    website_crawler_user_agent: str = "AdvancedBusinessRAGBot/1.0"
    chat_recent_message_limit: int = 8
    chat_memory_token_limit: int = 1800
    chat_summary_trigger_message_count: int = 12
    lead_capture_default_after_messages: int = 4
    lead_capture_manual_handoff_text: str = "Would you like a human expert to contact you?"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from_address: str = "noreply@example.com"
    admin_notification_webhook_url: str = ""
    notification_email_provider: str = "auto"
    notification_email_timeout_seconds: int = 15
    notification_email_max_retries: int = 3
    notification_email_retry_backoff_seconds: float = 1.5
    notification_webhook_timeout_seconds: int = 10
    notification_webhook_max_retries: int = 3
    notification_webhook_retry_backoff_seconds: float = 1.0
    notification_queue_poll_interval_seconds: float = 1.0
    notification_queue_batch_size: int = 10
    notification_queue_enabled: bool = True
    integration_queue_poll_interval_seconds: float = 1.0
    integration_queue_batch_size: int = 10
    integration_queue_enabled: bool = True
    integration_retry_backoff_seconds: float = 2.0
    integration_default_rate_limit_count: int = 20
    integration_default_rate_limit_window_seconds: int = 60
    integration_encryption_key: str = ""
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = ""
    aws_region: str = ""
    aws_ses_from_email: str = ""
    storage_backend: str = "local"
    storage_dir: str = "../storage/uploads"
    export_storage_dir: str = "../storage/exports"
    storage_signed_url_ttl_seconds: int = 900
    s3_bucket_name: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    supabase_url: str = ""
    supabase_bucket_name: str = ""
    supabase_service_role_key: str = ""
    export_job_max_retries: int = 3
    export_rate_limit_per_hour: int = 20
    export_active_job_limit_per_user: int = 3
    export_download_ttl_minutes: int = 120
    max_upload_size_mb: int = 10
    file_storage_permissions_mode: str = "600"
    worker_heartbeat_key: str = "rag-worker-heartbeat"
    worker_heartbeat_ttl_seconds: int = 30

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def has_insecure_jwt_secret(self) -> bool:
        secret = self.jwt_secret_key.strip()
        return not secret or secret == DEFAULT_JWT_SECRET_KEY

    def resolved_integration_encryption_secret(self) -> str:
        secret = self.integration_encryption_key.strip()
        if secret:
            return secret
        if self.is_production:
            raise ValueError("INTEGRATION_ENCRYPTION_KEY is required in production.")
        return self.jwt_secret_key

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            if self.database_url.startswith("postgresql://"):
                return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@localhost:{self.postgres_port}/{self.postgres_db}"
        )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value):  # noqa: ANN001
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                return value
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    @field_validator("worker_mode")
    @classmethod
    def validate_worker_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"inline", "external", "disabled"}
        if normalized not in allowed:
            raise ValueError(f"worker_mode must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("storage_backend")
    @classmethod
    def validate_storage_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"local", "s3", "supabase"}
        if normalized not in allowed:
            raise ValueError(f"storage_backend must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"openai", "local"}
        if normalized not in allowed:
            raise ValueError(f"embedding_provider must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @model_validator(mode="after")
    def validate_environment_rules(self) -> "Settings":
        if self.is_production:
            if self.has_insecure_jwt_secret:
                raise ValueError("JWT_SECRET_KEY must be set to a non-default value in production.")
            if not self.integration_encryption_key.strip():
                raise ValueError("INTEGRATION_ENCRYPTION_KEY is required in production.")
            if any(origin.strip() == "*" for origin in self.cors_allowed_origins):
                raise ValueError("Wildcard CORS origins are not allowed in production.")
        if self.storage_backend == "s3" and not self.s3_bucket_name:
            raise ValueError("S3_BUCKET_NAME is required when storage_backend=s3.")
        if self.storage_backend == "supabase" and (not self.supabase_url or not self.supabase_bucket_name):
            raise ValueError("SUPABASE_URL and SUPABASE_BUCKET_NAME are required when storage_backend=supabase.")
        return self

    model_config = SettingsConfigDict(
        env_file=["backend/.env", ".env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    version_file = Path(__file__).resolve().parents[3] / "VERSION"
    version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "0.3.0"
    return Settings(app_version=version)
