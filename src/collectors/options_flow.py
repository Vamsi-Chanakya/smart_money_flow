"""Options Flow collector - Track unusual options activity.

Sources:
- Barchart (free, web scraping)
- Yahoo Finance options chain (free)
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from ..utils.logger import get_logger
from ..utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


@dataclass
class OptionsActivity:
    """Represents unusual options activity."""

    ticker: str
    observed_date: datetime
    expiration_date: datetime
    strike_price: float
    option_type: str  # CALL or PUT
    volume: int
    open_interest: int
    volume_oi_ratio: float
    implied_volatility: Optional[float]
    last_price: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    underlying_price: Optional[float]
    sentiment: str  # BULLISH, BEARISH, NEUTRAL
    source: str


class OptionsFlowCollector:
    """Collector for unusual options activity.

    Primary method: Scrape Barchart's free unusual activity page.
    Backup: Yahoo Finance options chains.
    """

    BARCHART_URL = "https://www.barchart.com/options/unusual-activity/stocks"
    YAHOO_OPTIONS_URL = "https://query1.finance.yahoo.com/v7/finance/options"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.rate_limiter = RateLimiter(2)  # Be gentle with scraping

    def get_unusual_activity_barchart(self) -> list[OptionsActivity]:
        """Scrape unusual options activity from Barchart.

        Returns:
            List of unusual options activity
        """
        logger.info("Fetching unusual options from Barchart...")

        self.rate_limiter.wait()

        try:
            response = self.session.get(self.BARCHART_URL, timeout=30)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Error fetching Barchart: {e}")
            return []

        return self._parse_barchart_html(response.text)

    def _parse_barchart_html(self, html: str) -> list[OptionsActivity]:
        """Parse Barchart unusual activity HTML."""
        activities = []
        soup = BeautifulSoup(html, "lxml")

        # Find the data table
        table = soup.find("table", class_="bc-table-scrollable-inner")
        if not table:
            # Try alternative selector
            table = soup.find("table")

        if not table:
            logger.warning("Could not find options table on Barchart")
            return []

        rows = table.find_all("tr")[1:]  # Skip header

        for row in rows:
            try:
                cells = row.find_all("td")
                if len(cells) < 8:
                    continue

                # Extract data from cells
                symbol_cell = cells[0].get_text(strip=True)

                # Parse symbol (format: AAPL 250117C00200000 or similar)
                ticker = self._extract_ticker(symbol_cell)
                if not ticker:
                    continue

                # Parse option details
                option_type = "CALL" if "C" in symbol_cell.upper() else "PUT"

                # Get numeric values
                volume = self._parse_number(cells[2].get_text(strip=True))
                open_interest = self._parse_number(cells[3].get_text(strip=True))

                if volume and open_interest and open_interest > 0:
                    vol_oi = volume / open_interest
                else:
                    vol_oi = 0

                # Determine sentiment
                sentiment = "BULLISH" if option_type == "CALL" and vol_oi > 2 else \
                           "BEARISH" if option_type == "PUT" and vol_oi > 2 else "NEUTRAL"

                activity = OptionsActivity(
                    ticker=ticker,
                    observed_date=datetime.now(),
                    expiration_date=datetime.now(),  # Would parse from symbol
                    strike_price=0.0,  # Would parse from symbol
                    option_type=option_type,
                    volume=volume or 0,
                    open_interest=open_interest or 0,
                    volume_oi_ratio=vol_oi,
                    implied_volatility=None,
                    last_price=None,
                    bid=None,
                    ask=None,
                    underlying_price=None,
                    sentiment=sentiment,
                    source="barchart",
                )
                activities.append(activity)

            except Exception as e:
                logger.warning(f"Error parsing row: {e}")
                continue

        logger.info(f"Parsed {len(activities)} unusual options from Barchart")
        return activities

    def _extract_ticker(self, symbol: str) -> Optional[str]:
        """Extract ticker from option symbol."""
        # Option symbols: AAPL250117C00200000
        # Or just ticker: AAPL
        match = re.match(r"([A-Z]{1,5})", symbol)
        return match.group(1) if match else None

    def _parse_number(self, text: str) -> Optional[int]:
        """Parse number from text, handling K/M suffixes."""
        if not text:
            return None

        text = text.replace(",", "").strip()

        multiplier = 1
        if text.endswith("K"):
            multiplier = 1000
            text = text[:-1]
        elif text.endswith("M"):
            multiplier = 1000000
            text = text[:-1]

        try:
            return int(float(text) * multiplier)
        except ValueError:
            return None

    def get_options_chain_yahoo(self, ticker: str) -> list[OptionsActivity]:
        """Get options chain from Yahoo Finance using yfinance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of options with high volume/OI ratio
        """
        import yfinance as yf
        
        logger.info(f"Fetching options chain for {ticker} from Yahoo (yfinance)...")
        activities = []

        try:
            tk = yf.Ticker(ticker)
            expirations = tk.options
            
            if not expirations:
                return []
                
            # Check only the nearest expiration for speed
            nearest_exp = expirations[0]
            chain = tk.option_chain(nearest_exp)
            exp_date = datetime.strptime(nearest_exp, "%Y-%m-%d")
            
            # Helper to process chain dataframe
            def process_df(df, option_type):
                for _, row in df.iterrows():
                    volume = row.get('volume', 0)
                    oi = row.get('openInterest', 0)
                    
                    if not volume or not oi or oi == 0:
                        continue
                        
                    # Filter for significant activity
                    if volume < 500: # Minimum volume filter
                        continue
                        
                    vol_oi = volume / oi
                    if vol_oi < 2.0: # Minimum Vol/OI ratio
                        continue
                        
                    sentiment = "BULLISH" if option_type == "CALL" else "BEARISH"
                    
                    activities.append(OptionsActivity(
                        ticker=ticker,
                        observed_date=datetime.now(),
                        expiration_date=exp_date,
                        strike_price=row.get('strike'),
                        option_type=option_type,
                        volume=int(volume),
                        open_interest=int(oi),
                        volume_oi_ratio=vol_oi,
                        implied_volatility=row.get('impliedVolatility'),
                        last_price=row.get('lastPrice'),
                        bid=row.get('bid'),
                        ask=row.get('ask'),
                        underlying_price=0.0, # yfinance opt chain doesn't give underlying directly in row
                        sentiment=sentiment,
                        source="yahoo_yfinance",
                    ))

            if chain.calls is not None:
                process_df(chain.calls, "CALL")
            if chain.puts is not None:
                process_df(chain.puts, "PUT")

        except Exception as e:
            logger.error(f"Error fetching Yahoo options for {ticker}: {e}")
            return []
            
        # Sort by volume/OI
        activities.sort(key=lambda x: x.volume_oi_ratio, reverse=True)
        return activities[:20]

    def _parse_yahoo_options(self, ticker: str, data: dict) -> list[OptionsActivity]:
        # Deprecated
        return []

    def _parse_yahoo_option(self, *args, **kwargs):
        # Deprecated
        return None

    def get_unusual_for_tickers(self, tickers: list[str]) -> dict[str, list[OptionsActivity]]:
        """Get unusual options for multiple tickers.

        Args:
            tickers: List of stock tickers

        Returns:
            Dict mapping ticker to unusual options
        """
        results = {}

        for ticker in tickers:
            try:
                activities = self.get_options_chain_yahoo(ticker)
                if activities:
                    results[ticker] = activities
            except Exception as e:
                logger.error(f"Error getting options for {ticker}: {e}")

        return results

    def calculate_put_call_ratio(self, ticker: str) -> Optional[dict]:
        """Calculate put/call ratio for a ticker.

        Returns:
            Dict with put_volume, call_volume, ratio, sentiment
        """
        activities = self.get_options_chain_yahoo(ticker)

        if not activities:
            return None

        call_volume = sum(a.volume for a in activities if a.option_type == "CALL")
        put_volume = sum(a.volume for a in activities if a.option_type == "PUT")

        if call_volume == 0:
            ratio = float("inf")
        else:
            ratio = put_volume / call_volume

        # P/C ratio < 0.7 = bullish, > 1.0 = bearish
        if ratio < 0.7:
            sentiment = "BULLISH"
        elif ratio > 1.0:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"

        return {
            "ticker": ticker,
            "call_volume": call_volume,
            "put_volume": put_volume,
            "put_call_ratio": round(ratio, 2),
            "sentiment": sentiment,
        }
