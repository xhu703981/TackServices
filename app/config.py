from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the project root, shared with docker-compose.
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str
    jwt_secret_key: str
    jwt_access_expire: int = 3600  # seconds (1 hour)
    jwt_refresh_expire: int = 604800  # seconds (7 days)
    google_client_id: str  # Google ID tokens must be issued for this client, or they're rejected
    github_webhook_secret: str  # the GitHub App's webhook secret: proves a delivery really came from GitHub
    github_app_id: int  # shown on the GitHub App's settings page
    github_private_key_path: Path  # the app's .pem (gitignored); relative paths start at the project root


settings = Settings()
