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

    # Database connection pool
    DB_POOL_SIZE: int = 10          # persistent connections per process
    DB_MAX_OVERFLOW: int = 20       # extra connections allowed under burst
    DB_POOL_TIMEOUT: int = 30       # seconds to wait for a connection
    DB_POOL_RECYCLE: int = 1800     # recycle connections after 30 min (avoids stale TCP)

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # S3 / MinIO
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "app-bucket"
    S3_REGION: str = "us-east-1"

    # Stytch — https://stytch.com/dashboard/api-keys
    # Use "project-test-..." / "secret-test-..." for local/dev
    # Use "project-live-..." / "secret-live-..." for production
    STYTCH_PROJECT_ID: str = ""
    STYTCH_SECRET: str = ""


settings = Settings()
