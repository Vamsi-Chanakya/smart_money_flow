"""Configuration management for Smart Money Flow Tracker."""

import os
from pathlib import Path
from typing import Any, Optional, Union

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


class UnusualWhalesConfig(BaseModel):
    base_url: str = "https://api.unusualwhales.com/api"
    api_key: str = ""
    min_premium: int = 10000 


class MarketSentimentConfig(BaseModel):
    sentiment_threshold_bullish: float = 0.35
    sentiment_threshold_bearish: float = -0.35
    news_limit: int = 10


class ApisConfig(BaseModel):
    sec_edgar: SecEdgarConfig = SecEdgarConfig()
    house_stock_watcher: HouseStockWatcherConfig = HouseStockWatcherConfig()
    finnhub: FinnhubConfig = FinnhubConfig()
    alpha_vantage: AlphaVantageConfig = AlphaVantageConfig()
    unusual_whales: UnusualWhalesConfig = UnusualWhalesConfig()


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
    market_sentiment: MarketSentimentConfig = MarketSentimentConfig()
    alerts: AlertsConfig = AlertsConfig()
    notifications: NotificationsConfig = NotificationsConfig()

    class Config:
        env_prefix = "SMF_"
        env_file = ".env"
        env_file_encoding = "utf-8"
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


# ==================== Watchlist Configuration ====================

class EarningsEventConfig(BaseModel):
    days_before_alert: int = 7


class CongressionalEventConfig(BaseModel):
    lookback_days: int = 30
    min_amount: int = 15000


class InsiderEventConfig(BaseModel):
    lookback_days: int = 30
    min_insiders: int = 1
    transaction_types: list[str] = ["P", "S"]


class OptionsFlowEventConfig(BaseModel):
    min_volume_oi_ratio: float = 2.0
    min_premium: int = 50000


class WhaleEventConfig(BaseModel):
    min_value_usd: int = 100000


class EventsConfig(BaseModel):
    earnings: EarningsEventConfig = EarningsEventConfig()
    congressional_trades: CongressionalEventConfig = CongressionalEventConfig()
    insider_trades: InsiderEventConfig = InsiderEventConfig()
    options_flow: OptionsFlowEventConfig = OptionsFlowEventConfig()
    whale_transactions: WhaleEventConfig = WhaleEventConfig()


class StockWatchItem(BaseModel):
    symbol: str
    name: Optional[str] = None
    events: list[str] = ["earnings", "congressional_trades", "insider_trades", "options_flow"]


class CryptoWatchItem(BaseModel):
    symbol: str
    name: Optional[str] = None
    events: list[str] = ["whale_transactions", "large_transfers"]


class Watchlist(BaseModel):
    stocks: list[StockWatchItem] = []
    crypto: list[CryptoWatchItem] = []
    events: EventsConfig = EventsConfig()

    @property
    def stock_symbols(self) -> list[str]:
        """Get list of stock symbols."""
        return [s.symbol for s in self.stocks]

    @property
    def crypto_symbols(self) -> list[str]:
        """Get list of crypto symbols."""
        return [c.symbol for c in self.crypto]

    def get_stock(self, symbol: str) -> Optional[StockWatchItem]:
        """Get stock config by symbol."""
        for stock in self.stocks:
            if stock.symbol.upper() == symbol.upper():
                return stock
        return None

    def get_crypto(self, symbol: str) -> Optional[CryptoWatchItem]:
        """Get crypto config by symbol."""
        for crypto in self.crypto:
            if crypto.symbol.upper() == symbol.upper():
                return crypto
        return None


def load_watchlist() -> Watchlist:
    """Load watchlist from config file."""
    watchlist_path = get_project_root() / "config" / "watchlist.yaml"

    if not watchlist_path.exists():
        return Watchlist()

    with open(watchlist_path) as f:
        data = yaml.safe_load(f)

    return Watchlist(**data) if data else Watchlist()


# Global watchlist instance
watchlist = load_watchlist()
