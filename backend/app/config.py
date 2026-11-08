from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    frontend_origin: str = "http://localhost:5173"
    # GitHub login of the single seeded learner. (The webhook matches PRs by repo, not by author.)
    demo_learner_github_login: str = "param-m1"

    # GitHub App (Neel's webhook and bot). The webhook secret signs every delivery, so it's
    # a SecretStr: it stays out of reprs and logs. The private key stays in its own file.
    github_app_id: str | None = None
    github_installation_id: str | None = None
    github_private_key_path: Path | None = None
    github_webhook_secret: SecretStr | None = None


settings = Settings()
