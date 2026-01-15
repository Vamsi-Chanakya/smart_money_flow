"""Unusual Whales Data Collector.

Collects options flow and unusual activity from Unusual Whales API.
Requires API Key (Paid Tier usually required).
"""

import requests
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from ..utils.logger import get_logger
from ..utils.config import settings
from ..utils.rate_limiter import RateLimiter

logger = get_logger(__name__)

class UnusualWhalesCollector:
    """Collector for Unusual Whales API."""

    def __init__(self):
        self.base_url = settings.apis.unusual_whales.base_url
        self.api_key = settings.apis.unusual_whales.api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "SmartMoneyFlow/1.0",
            "Accept": "application/json"
        })
        self.rate_limiter = RateLimiter(5)  # Conservative limit

    def get_latest_option_trades(self, ticker: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get latest significant option trades.
        
        Args:
            ticker: Optional ticker symbol to filter by
            limit: Number of trades to return
        """
        if not self.api_key:
            logger.debug("Unusual Whales API key not set - skipping")
            return []

        self.rate_limiter.wait()
        
        endpoint = f"{self.base_url}/option_trades"
        params = {
            "limit": limit,
            "min_premium": 10000  # Only show significant trades
        }
        
        if ticker:
            params["ticker"] = ticker

        try:
            response = self.session.get(endpoint, params=params, timeout=10)
            
            if response.status_code == 401:
                logger.warning("Unusual Whales API Unauthorized - Check API Key")
                return []
            
            if response.status_code == 403:
                logger.warning("Unusual Whales API Forbidden - Subscription level too low?")
                return []

            response.raise_for_status()
            data = response.json()
            
            # API response structure varies, assume 'data' list or direct list
            results = data.get("data", []) if isinstance(data, dict) else data
            
            logger.info(f"Fetched {len(results)} option trades from Unusual Whales")
            return results

        except Exception as e:
            logger.error(f"Error fetching Unusual Whales data: {e}")
            return []

    def get_market_tide(self) -> Optional[Dict[str, Any]]:
        """Get overall market tide/sentiment if available."""
        if not self.api_key:
            return None
            
        self.rate_limiter.wait()
        try:
            # Hypothetical endpoint based on public docs names
            response = self.session.get(f"{self.base_url}/market_tide", timeout=10)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
