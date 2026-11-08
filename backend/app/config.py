from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    frontend_origin: str = "http://localhost:5173"
    # GitHub login of the single seeded learner. Neel's webhook matches PR authors to this.
    demo_learner_github_login: str = "param-m1"
    # Claude API key. Settings reads .env but doesn't export it to the environment,
    # so the reviewer passes this to the SDK itself. SecretStr keeps it out of reprs and logs.
    anthropic_api_key: SecretStr | None = None


settings = Settings()
