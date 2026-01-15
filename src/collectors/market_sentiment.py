"""Market Sentiment Collector.

Collects sentiment data from:
1. Alternative.me (Crypto Fear & Greed Index) - Free
2. Alpha Vantage (News Sentiment) - Free Tier
"""

import requests
from typing import Optional, Dict, Any
from datetime import datetime
from ..utils.logger import get_logger
from ..utils.config import settings

logger = get_logger(__name__)

class MarketSentimentCollector:
    """Collector for market sentiment data."""

    CRYPTO_FNG_URL = "https://api.alternative.me/fng/"
    ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"

    def __init__(self):
        self.session = requests.Session()
        self.av_api_key = settings.apis.alpha_vantage.api_key

    def get_crypto_fear_greed(self) -> Optional[Dict[str, Any]]:
        """Get Crypto Fear & Greed Index from Alternative.me."""
        try:
            response = self.session.get(self.CRYPTO_FNG_URL)
            response.raise_for_status()
            data = response.json()
            
            # Format: {'data': [{'value': '72', 'value_classification': 'Greed', ...}]}
            if 'data' in data and len(data['data']) > 0:
                item = data['data'][0]
                return {
                    "value": int(item['value']),
                    "classification": item['value_classification'],
                    "timestamp": datetime.fromtimestamp(int(item['timestamp']))
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching Crypto Fear & Greed: {e}")
            return None

    def get_stock_sentiment(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get News Sentiment for a stock from Alpha Vantage."""
        if not self.av_api_key:
            logger.warning("Alpha Vantage API key not set - skipping sentiment")
            return None

        # Rate limit check (simple check, strictly enforced by API anyway)
        # Free tier: 25 requests/day. Use sparingly.
        
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "apikey": self.av_api_key,
            "limit": settings.market_sentiment.news_limit
        }

        try:
            response = self.session.get(self.ALPHA_VANTAGE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if "feed" not in data:
                return None

            # Calculate average sentiment score
            sentiment_scores = []
            for item in data.get("feed", []):
                for ticker_sentiment in item.get("ticker_sentiment", []):
                    if ticker_sentiment.get("ticker") == ticker:
                        score = float(ticker_sentiment.get("ticker_sentiment_score", 0))
                        sentiment_scores.append(score)

            if not sentiment_scores:
                return None

            avg_score = sum(sentiment_scores) / len(sentiment_scores)
            
            # Label
            if avg_score >= settings.market_sentiment.sentiment_threshold_bullish:
                label = "Bullish"
            elif avg_score <= settings.market_sentiment.sentiment_threshold_bearish:
                label = "Bearish"
            else:
                label = "Neutral"

            return {
                "ticker": ticker,
                "sentiment_score": round(avg_score, 2),
                "sentiment_label": label,
                "article_count": len(sentiment_scores)
            }

        except Exception as e:
            logger.error(f"Error fetching stock sentiment for {ticker}: {e}")
            return None
