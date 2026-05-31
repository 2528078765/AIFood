from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # Qwen (DashScope)
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Tavily
    tavily_api_key: str = ""

    # Database (SQLite for lightweight deployment)
    database_url: str = "sqlite+aiosqlite:///./aifood.db"

    # WeChat
    wechat_appid: str = ""
    wechat_secret: str = ""

    # Encryption
    encryption_key: str = ""

    # JWT
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # App
    debug: bool = True
    api_prefix: str = "/api"


settings = Settings()
