from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    LANGFUSE_PUBLIC_KEY: str = "pk-lf-test"
    LANGFUSE_SECRET_KEY: str = "sk-lf-test"
    LANGFUSE_HOST: str = "http://localhost:3000"
    
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    
    DEFAULT_MAX_STEPS: int = 10
    DEFAULT_TOKEN_LIMIT: int = 10000
    DEFAULT_BUDGET_USD: float = 0.50
    USD_TO_VND_RATE: float = 25400.0  # Tỷ giá quy đổi USD -> VND
    SIMULATION_MODE: bool = True  # Chế độ mô phỏng / Mock sandbox vs Live Mode
    
    ALERT_WEBHOOK_URL: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

