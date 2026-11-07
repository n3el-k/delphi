from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    frontend_origin: str = "http://localhost:5173"
    # GitHub login of the single seeded learner. Neel's webhook matches PR authors to this.
    demo_learner_github_login: str = "param-m1"


settings = Settings()
