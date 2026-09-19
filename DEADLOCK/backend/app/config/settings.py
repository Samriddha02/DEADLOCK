from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # GitHub
    github_token: str = ""
    github_api_url: str = "https://api.github.com"
    github_owner: str = ""
    github_repo: str = ""

    # Integration configuration. All are optional in deterministic demo mode.
    deadlock_mode: str = "demo"
    llm_provider: str = ""
    llm_api_key: str = ""
    beeceptor_base_url: str = ""
    beeceptor_api_key: str = ""
    n8n_webhook_secret: str = ""
    frontend_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # AI / Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # Database
    database_url: str = "sqlite:///./deadlock.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global settings object
settings = Settings()
