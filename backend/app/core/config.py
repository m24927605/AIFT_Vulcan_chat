from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    primary_llm: str = "openai"       # openai | anthropic
    fallback_llm: str = "anthropic"   # openai | anthropic | "" (disabled)
    tavily_api_key: str = ""
    fugle_api_key: str = ""  # Fugle MarketData API key (optional, for TW stock data)
    finnhub_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    telegram_bot_token: str = ""
    telegram_admin_ids: list[int] = []
    mode: str = "web"
    api_secret_key: str = ""  # Protects admin endpoints (notify, broadcast)
    data_dir: str = "."  # Directory for SQLite databases

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
