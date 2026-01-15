"""Configuration management for Smart Money Flow Tracker."""

import os
from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///data/smartmoney.db"


class SecEdgarConfig(BaseModel):
    base_url: str = "https://data.sec.gov"
    user_agent: str = "SmartMoneyFlow research@example.com"
    rate_limit: int = 10


class HouseStockWatcherConfig(BaseModel):
    base_url: str = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data"


class FinnhubConfig(BaseModel):
    base_url: str = "https://finnhub.io/api/v1"
    api_key: str = ""


class AlphaVantageConfig(BaseModel):
    base_url: str = "https://www.alphavantage.co/query"
    api_key: str = ""


class ApisConfig(BaseModel):
    sec_edgar: SecEdgarConfig = SecEdgarConfig()
    house_stock_watcher: HouseStockWatcherConfig = HouseStockWatcherConfig()
    finnhub: FinnhubConfig = FinnhubConfig()
    alpha_vantage: AlphaVantageConfig = AlphaVantageConfig()


class SignalsConfig(BaseModel):
    institutional_accumulation: float = 0.9
    insider_cluster_buy: float = 0.85
    congressional_trade: float = 0.6
    options_flow: float = 0.5
    cross_signal_bonus: float = 1.5


class AlertsConfig(BaseModel):
    min_confidence_score: float = 0.7
    insider_cluster_min_count: int = 3
    institutional_min_filers: int = 2
    options_volume_multiplier: int = 5


class TelegramConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


class DiscordConfig(BaseModel):
    enabled: bool = False
    webhook_url: str = ""


class NotificationsConfig(BaseModel):
    telegram: TelegramConfig = TelegramConfig()
    discord: DiscordConfig = DiscordConfig()


class Settings(BaseSettings):
    database: DatabaseConfig = DatabaseConfig()
    apis: ApisConfig = ApisConfig()
    signals: SignalsConfig = SignalsConfig()
    alerts: AlertsConfig = AlertsConfig()
    notifications: NotificationsConfig = NotificationsConfig()

    class Config:
        env_prefix = "SMF_"
        extra = "ignore"

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Settings":
        """Load settings from YAML file."""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls(**data) if data else cls()


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def load_settings() -> Settings:
    """Load settings from config file."""
    config_path = get_project_root() / "config" / "settings.yaml"
    return Settings.from_yaml(config_path)


# Global settings instance
settings = load_settings()
