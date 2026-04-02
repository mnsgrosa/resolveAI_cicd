from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "sqlite+aiosqlite:///./resolveai.db"

    # Anthropic
    anthropic_api_key: str

    # Review model config
    planner_model: str = "claude-sonnet-4-6"  # swap to claude-opus-4-6 later
    executor_model: str = "claude-sonnet-4-6"

    # App
    app_title: str = "ResolveAI CICD"
    debug: bool = False


settings = Settings()
