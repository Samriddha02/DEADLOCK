from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # GitHub
    github_token: str = ""
    github_api_url: str = "https://api.github.com"

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