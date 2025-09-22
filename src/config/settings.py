from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    # Database
    database_url: str = Field(default="postgresql://pbsg:pbsg_password@localhost:5432/pbsg")

    # Kraken
    kraken_ws_url: str = Field(default="wss://ws.kraken.com")
    kraken_symbols: list[str] = Field(default=["BTC/USD", "ETH/USD"])
    kraken_timeframes: list[str] = Field(default=["15", "60", "240", "360"])

    # Signal Configuration
    signal_min_volume: float = Field(default=100000)
    signal_cooldown_minutes: int = Field(default=60)

    # Signal Sinks
    telegram_bot_token: Optional[str] = Field(default=None)
    telegram_chat_id: Optional[str] = Field(default=None)
    webhook_url: Optional[str] = Field(default=None)

    # Environment
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()