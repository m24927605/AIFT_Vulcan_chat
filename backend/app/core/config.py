from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    tavily_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    telegram_bot_token: str = ""
    telegram_admin_ids: list[int] = []
    mode: str = "web"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
