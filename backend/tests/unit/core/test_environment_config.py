from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_development_environment_uses_local_defaults():
    settings = Settings(
        _env_file=None,
        app_env="development",
        postgres_user="rag_admin",
        postgres_password="rag_password",
        postgres_port=5432,
        postgres_db="rag_chatbot",
    )
    assert settings.app_env == "development"
    assert settings.resolved_database_url.endswith("/rag_chatbot")
    assert settings.frontend_url == "http://localhost:3000"
    assert settings.resolved_integration_encryption_secret() == settings.jwt_secret_key


def test_staging_environment_parses_cors_and_database_url():
    settings = Settings(
        _env_file=None,
        app_env="staging",
        database_url="postgresql://staging:secret@db.example.com:5433/rag_stage",
        cors_allowed_origins="https://stage.example.com,https://preview.example.com",
    )
    assert settings.app_env == "staging"
    assert settings.resolved_database_url == "postgresql+psycopg://staging:secret@db.example.com:5433/rag_stage"
    assert settings.cors_allowed_origins == ["https://stage.example.com", "https://preview.example.com"]


def test_production_like_environment_keeps_https_controls_enabled():
    settings = Settings(
        _env_file=None,
        app_env="production",
        frontend_url="https://app.example.com",
        enforce_https_in_production=True,
        secure_cookie_samesite="lax",
        jwt_secret_key="prod-jwt-secret",
        integration_encryption_key="prod-integration-secret",
    )
    assert settings.app_env == "production"
    assert settings.enforce_https_in_production is True
    assert settings.frontend_url.startswith("https://")


def test_production_environment_rejects_default_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY must be set to a non-default value in production."):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="change-this-in-production",
            integration_encryption_key="prod-integration-secret",
        )


def test_production_environment_requires_integration_encryption_key():
    with pytest.raises(ValidationError, match="INTEGRATION_ENCRYPTION_KEY is required in production."):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="prod-jwt-secret",
            integration_encryption_key="",
        )
