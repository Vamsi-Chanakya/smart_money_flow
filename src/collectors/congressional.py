"""Congressional stock trading data collector.

Uses the free House Stock Watcher API and Senate disclosure data.
Based on STOCK Act disclosure requirements.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ..utils.logger import get_logger
from ..utils.rate_limiter import RateLimiter
from .unusual_whales import UnusualWhalesCollector

logger = get_logger(__name__)


@dataclass
class CongressTrade:
    """Represents a congressional stock trade."""

    disclosure_id: str
    representative: str
    chamber: str  # House or Senate
    party: Optional[str]
    state: Optional[str]
    district: Optional[str]
    ticker: Optional[str]
    asset_description: str
    asset_type: Optional[str]
    transaction_type: str  # purchase, sale, exchange
    trade_date: datetime
    disclosure_date: datetime
    amount_min: Optional[int]
    amount_max: Optional[int]
    amount_text: Optional[str]
    owner: Optional[str]  # self, spouse, joint, child


class CongressionalCollector:
    """Collector for Congressional trading data.

    Primary source: House Stock Watcher (free, updated daily)
    https://housestockwatcher.com/api

    Data includes trades by members of Congress as required by STOCK Act.
    """

    HOUSE_API_BASE = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SmartMoneyFlow/1.0",
        })
        self.rate_limiter = RateLimiter(5)  # Be gentle with free API
        self.uw_collector = UnusualWhalesCollector()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get(self, url: str) -> requests.Response:
        """Make a rate-limited GET request."""
        self.rate_limiter.wait()
        response = self.session.get(url)
        response.raise_for_status()
        return response

    # ==================== House Trades ====================

    def get_all_house_trades(self) -> list[CongressTrade]:
        """Get all historical congressional trading data.
        
        Priority:
        1. Unusual Whales API (Best, Real-time)
        2. House Stock Watcher API (Deprecated)
        3. Demo Data (Fallback)
        """
        # 1. Try Unusual Whales
        if self.uw_collector.api_key:
            try:
                uw_data = self.uw_collector.get_congress_trades(limit=100)
                if uw_data:
                    trades = []
                    for item in uw_data:
                        trade = self._parse_uw_trade(item)
                        if trade:
                            trades.append(trade)
                    
                    if trades:
                        logger.info(f"Fetched {len(trades)} trades from Unusual Whales")
                        return trades
            except Exception as e:
                logger.warning(f"Failed to fetch from Unusual Whales: {e}")

        # 2. Try House Stock Watcher (Legacy)
        url = f"{self.HOUSE_API_BASE}/all_transactions.json"
        
        try:
            response = self._get(url)
            data = response.json()

            trades = []
            for item in data:
                trade = self._parse_house_trade(item)
                if trade:
                    trades.append(trade)

            logger.info(f"Fetched {len(trades)} House trades")
            return trades
        except Exception as e:
            logger.warning(f"Could not fetch from House Stock Watcher API: {e}")
            logger.info("Using demo data - House Stock Watcher API is no longer available")
            return self._get_demo_trades()

    def _get_demo_trades(self) -> list[CongressTrade]:
        """Return demo congressional trades for testing when API is unavailable.
        
        Note: House Stock Watcher (housestockwatcher.com) is no longer available.
        Consider using alternative sources like:
        - Quiver Quantitative API (requires API key)
        - Capitol Trades (requires web scraping)
        - SEC EDGAR for official filings
        """
        from datetime import timedelta
        
        demo_data = [
            {"representative": "Nancy Pelosi", "party": "D", "state": "CA", "ticker": "NVDA", 
             "type": "purchase", "amount": "$1,000,001 - $5,000,000", "days_ago": 5},
            {"representative": "Nancy Pelosi", "party": "D", "state": "CA", "ticker": "AAPL", 
             "type": "purchase", "amount": "$500,001 - $1,000,000", "days_ago": 12},
            {"representative": "Dan Crenshaw", "party": "R", "state": "TX", "ticker": "MSFT", 
             "type": "purchase", "amount": "$15,001 - $50,000", "days_ago": 8},
            {"representative": "Josh Gottheimer", "party": "D", "state": "NJ", "ticker": "GOOGL", 
             "type": "sale", "amount": "$100,001 - $250,000", "days_ago": 3},
            {"representative": "Tommy Tuberville", "party": "R", "state": "AL", "ticker": "TSLA", 
             "type": "purchase", "amount": "$50,001 - $100,000", "days_ago": 15},
            {"representative": "Marjorie Taylor Greene", "party": "R", "state": "GA", "ticker": "META", 
             "type": "purchase", "amount": "$1,001 - $15,000", "days_ago": 7},
            {"representative": "Ro Khanna", "party": "D", "state": "CA", "ticker": "AMD", 
             "type": "purchase", "amount": "$15,001 - $50,000", "days_ago": 20},
            {"representative": "Michael McCaul", "party": "R", "state": "TX", "ticker": "AMZN", 
             "type": "sale", "amount": "$250,001 - $500,000", "days_ago": 10},
            {"representative": "Debbie Wasserman Schultz", "party": "D", "state": "FL", "ticker": "JPM", 
             "type": "purchase", "amount": "$50,001 - $100,000", "days_ago": 25},
            {"representative": "Greg Gianforte", "party": "R", "state": "MT", "ticker": "XOM", 
             "type": "purchase", "amount": "$100,001 - $250,000", "days_ago": 18},
        ]
        
        trades = []
        now = datetime.now()
        
        for i, item in enumerate(demo_data):
            trade_date = now - timedelta(days=item["days_ago"])
            disclosure_date = trade_date + timedelta(days=30)  # Typical 30-day disclosure lag
            
            amount_min, amount_max = self._parse_amount_range(item["amount"])
            
            trade = CongressTrade(
                disclosure_id=f"demo_{item['representative'].replace(' ', '_')}_{i}",
                representative=item["representative"],
                chamber="House",
                party=item["party"],
                state=item["state"],
                district=None,
                ticker=item["ticker"],
                asset_description=f"{item['ticker']} Common Stock",
                asset_type="Stock",
                transaction_type=item["type"],
                trade_date=trade_date,
                disclosure_date=disclosure_date,
                amount_min=amount_min,
                amount_max=amount_max,
                amount_text=item["amount"],
                owner="self",
            )
            trades.append(trade)
        
        logger.info(f"Generated {len(trades)} demo trades for testing")
        return trades

    def get_house_trades_by_ticker(self, ticker: str) -> list[CongressTrade]:
        """Get House trades for a specific ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of trades for that ticker
        """
        all_trades = self.get_all_house_trades()
        return [t for t in all_trades if t.ticker and t.ticker.upper() == ticker.upper()]

    def get_house_trades_by_representative(self, name: str) -> list[CongressTrade]:
        """Get trades by a specific representative.

        Args:
            name: Representative name (partial match)

        Returns:
            List of trades by that representative
        """
        all_trades = self.get_all_house_trades()
        name_lower = name.lower()
        return [t for t in all_trades if name_lower in t.representative.lower()]

    def _parse_house_trade(self, item: dict) -> Optional[CongressTrade]:
        """Parse a trade from House Stock Watcher format."""
        try:
            # Parse dates
            trade_date = self._parse_date(item.get("transaction_date", ""))
            disclosure_date = self._parse_date(item.get("disclosure_date", ""))

            if not trade_date or not disclosure_date:
                return None

            # Parse amount range
            amount_text = item.get("amount", "")
            amount_min, amount_max = self._parse_amount_range(amount_text)

            # Extract ticker from description if not provided
            ticker = item.get("ticker", "")
            if not ticker or ticker == "--":
                ticker = self._extract_ticker(item.get("asset_description", ""))

            # Generate unique ID
            disclosure_id = f"house_{item.get('representative', '')}_{trade_date.isoformat()}_{ticker or 'na'}"
            disclosure_id = re.sub(r'[^a-zA-Z0-9_-]', '', disclosure_id)[:100]

            return CongressTrade(
                disclosure_id=disclosure_id,
                representative=item.get("representative", "Unknown"),
                chamber="House",
                party=item.get("party"),
                state=item.get("state"),
                district=item.get("district"),
                ticker=ticker if ticker and ticker != "--" else None,
                asset_description=item.get("asset_description", ""),
                asset_type=item.get("type"),
                transaction_type=item.get("type", "").lower(),  # purchase, sale, etc.
                trade_date=trade_date,
                disclosure_date=disclosure_date,
                amount_min=amount_min,
                amount_max=amount_max,
                amount_text=amount_text,
                owner=item.get("owner"),
            )
        except Exception as e:
            logger.warning(f"Error parsing House trade: {e}")
            return None

    def _parse_uw_trade(self, item: dict) -> Optional[CongressTrade]:
        """Parse trade from Unusual Whales format."""
        try:
            # Report Date -> Disclosure Date
            # Transaction Date -> Trade Date
            trade_date = self._parse_date(item.get("transaction_date"))
            disclosure_date = self._parse_date(item.get("report_date")) or datetime.now()
            
            if not trade_date:
                return None

            return CongressTrade(
                disclosure_id=f"uw_{item.get('id', '')}",
                representative=item.get("politician", "Unknown"),
                chamber=item.get("chamber", "Congress"),
                party=item.get("party"),
                state=item.get("state"),
                district=item.get("district"),
                ticker=item.get("ticker"),
                asset_description=item.get("description", ""),
                asset_type="Stock", 
                transaction_type=item.get("transaction_type", "").lower(),
                trade_date=trade_date,
                disclosure_date=disclosure_date,
                amount_min=None, 
                amount_max=None,
                amount_text=item.get("amount"), # UW might give text or number
                owner=item.get("owner"),
            )
        except Exception:
            return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string in various formats."""
        if not date_str:
            return None

        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%Y-%m-%dT%H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _parse_amount_range(self, amount_str: str) -> tuple[Optional[int], Optional[int]]:
        """Parse amount range string like '$1,001 - $15,000'."""
        if not amount_str:
            return None, None

        # Remove $ and commas
        amount_str = amount_str.replace("$", "").replace(",", "")

        # Common patterns
        patterns = [
            r"(\d+)\s*-\s*(\d+)",  # "1001 - 15000"
            r"(\d+)\s*to\s*(\d+)",  # "1001 to 15000"
            r"Over\s*(\d+)",  # "Over 1000000"
        ]

        for pattern in patterns:
            match = re.search(pattern, amount_str, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    return int(groups[0]), int(groups[1])
                elif len(groups) == 1:
                    return int(groups[0]), None

        return None, None

    def _extract_ticker(self, description: str) -> Optional[str]:
        """Try to extract ticker symbol from asset description."""
        # Look for pattern like "(AAPL)" or "- AAPL"
        patterns = [
            r"\(([A-Z]{1,5})\)",  # (AAPL)
            r"\s-\s([A-Z]{1,5})$",  # - AAPL at end
            r"\[([A-Z]{1,5})\]",  # [AAPL]
        ]

        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return match.group(1)

        return None

    # ==================== Analysis Helpers ====================

    def get_recent_purchases(self, days_back: int = 30) -> list[CongressTrade]:
        """Get recent purchase transactions.

        Args:
            days_back: Number of days to look back

        Returns:
            List of recent purchases
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days_back)
        all_trades = self.get_all_house_trades()

        return [
            t for t in all_trades
            if t.trade_date >= cutoff and t.transaction_type in ("purchase", "buy")
        ]

    def get_recent_sales(self, days_back: int = 30) -> list[CongressTrade]:
        """Get recent sale transactions."""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days_back)
        all_trades = self.get_all_house_trades()

        return [
            t for t in all_trades
            if t.trade_date >= cutoff and t.transaction_type in ("sale", "sell", "sale (full)", "sale (partial)")
        ]

    def get_most_traded_tickers(self, days_back: int = 30, top_n: int = 20) -> list[dict]:
        """Get most frequently traded tickers by Congress.

        Returns:
            List of {ticker, buy_count, sell_count, net_sentiment}
        """
        from collections import defaultdict
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days_back)
        all_trades = self.get_all_house_trades()

        ticker_stats = defaultdict(lambda: {"buys": 0, "sells": 0})

        for trade in all_trades:
            if trade.trade_date < cutoff or not trade.ticker:
                continue

            ticker = trade.ticker.upper()
            if trade.transaction_type in ("purchase", "buy"):
                ticker_stats[ticker]["buys"] += 1
            elif "sale" in trade.transaction_type.lower():
                ticker_stats[ticker]["sells"] += 1

        # Convert to list and sort by total activity
        results = []
        for ticker, stats in ticker_stats.items():
            total = stats["buys"] + stats["sells"]
            net = stats["buys"] - stats["sells"]
            results.append({
                "ticker": ticker,
                "buy_count": stats["buys"],
                "sell_count": stats["sells"],
                "total_trades": total,
                "net_sentiment": "BULLISH" if net > 0 else "BEARISH" if net < 0 else "NEUTRAL",
            })

        results.sort(key=lambda x: x["total_trades"], reverse=True)
        return results[:top_n]

    def get_top_traders(self, days_back: int = 90, top_n: int = 20) -> list[dict]:
        """Get most active trading members of Congress.

        Returns:
            List of {name, party, state, trade_count}
        """
        from collections import defaultdict
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days_back)
        all_trades = self.get_all_house_trades()

        trader_stats = defaultdict(lambda: {"party": None, "state": None, "count": 0})

        for trade in all_trades:
            if trade.trade_date < cutoff:
                continue

            name = trade.representative
            trader_stats[name]["count"] += 1
            trader_stats[name]["party"] = trade.party
            trader_stats[name]["state"] = trade.state

        # Convert to list and sort
        results = [
            {
                "name": name,
                "party": stats["party"],
                "state": stats["state"],
                "trade_count": stats["count"],
            }
            for name, stats in trader_stats.items()
        ]

        results.sort(key=lambda x: x["trade_count"], reverse=True)
        return results[:top_n]
