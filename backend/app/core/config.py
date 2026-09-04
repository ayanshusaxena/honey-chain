"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the API."""

    app_name: str = "Honey Chain API"
    environment: str = "development"
    database_url: str | None = None
    jwt_secret: SecretStr | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)
    demo_password: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_prefix="HONEY_CHAIN_",
        extra="ignore",
    )

    def jwt_secret_value(self) -> str:
        """Return the configured JWT signing secret or fail closed."""
        if self.jwt_secret is None or not self.jwt_secret.get_secret_value():
            raise RuntimeError("HONEY_CHAIN_JWT_SECRET must be configured.")
        return self.jwt_secret.get_secret_value()

    def demo_password_value(self) -> str:
        """Return the configured demo password or fail closed."""
        if self.demo_password is None or not self.demo_password.get_secret_value():
            raise RuntimeError("HONEY_CHAIN_DEMO_PASSWORD must be configured.")
        return self.demo_password.get_secret_value()


settings = Settings()
