from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings come from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), extra="ignore")

    app_env: str = "development"
    database_url: str = "mysql+pymysql://root:password@127.0.0.1:3306/cartium"
    jwt_secret: str = "dev-secret-change-me-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("database_url")
    @classmethod
    def use_pymysql_driver(cls, url: str) -> str:
        # Hosts like Railway hand out "mysql://..." URLs; SQLAlchemy needs the driver named.
        return "mysql+pymysql://" + url.removeprefix("mysql://") if url.startswith("mysql://") else url

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


settings = Settings()
