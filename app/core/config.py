from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/app"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "app"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # S3 / MinIO
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "app-bucket"
    S3_REGION: str = "us-east-1"

    # Clerk
    # CLERK_JWKS_URL: found in Clerk dashboard → API Keys → Advanced
    # Format: https://<your-clerk-frontend-api>/.well-known/jwks.json
    CLERK_JWKS_URL: str = ""
    # CLERK_ISSUER: your Clerk frontend API URL (e.g. https://clerk.your-app.com)
    # Leave empty to skip issuer validation during local development
    CLERK_ISSUER: str = ""


settings = Settings()
