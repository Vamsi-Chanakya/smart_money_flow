#!/usr/bin/env python3
"""Stateless watchlist scanner for GitHub Actions.

Scans configured tickers for binary events and sends Telegram alerts.
No database required - fetches fresh data each run.

Usage:
    python scripts/scan_watchlist.py              # Scan all and alert
    python scripts/scan_watchlist.py --dry-run    # Scan without sending alerts
    python scripts/scan_watchlist.py --ticker SMCI # Scan single ticker
"""

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import settings, watchlist
from src.utils.logger import get_logger
from src.output.alerts import TelegramAlert, AlertMessage

logger = get_logger(__name__)


@dataclass
class ScanResult:
    """Result of scanning a single asset."""
    symbol: str
    asset_type: str  # stock or crypto
    events_found: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_events(self) -> bool:
        return len(self.events_found) > 0


class WatchlistScanner:
    """Stateless scanner for watchlist binary events."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.telegram = TelegramAlert()
        self.results: list[ScanResult] = []

        # Lazy load collectors
        self._congressional = None
        self._options = None
        self._sec = None
        self._crypto = None

    @property
    def congressional_collector(self):
        if self._congressional is None:
            from src.collectors.congressional import CongressionalCollector
            self._congressional = CongressionalCollector()
        return self._congressional

    @property
    def options_collector(self):
        if self._options is None:
            from src.collectors.options_flow import OptionsFlowCollector
            self._options = OptionsFlowCollector()
        return self._options

    @property
    def sec_collector(self):
        if self._sec is None:
            from src.collectors.sec_edgar import SecEdgarCollector
            self._sec = SecEdgarCollector()
        return self._sec

    @property
    def crypto_collector(self):
        if self._crypto is None:
            from src.collectors.crypto_whales import BitcoinWhaleCollector
            self._crypto = BitcoinWhaleCollector()
        return self._crypto

    def scan_all(self) -> list[ScanResult]:
        """Scan all assets in watchlist."""
        logger.info(f"Starting watchlist scan at {datetime.now()}")
        logger.info(f"Stocks: {watchlist.stock_symbols}")
        logger.info(f"Crypto: {watchlist.crypto_symbols}")

        # Scan stocks
        for stock in watchlist.stocks:
            result = self.scan_stock(stock.symbol, stock.events)
            self.results.append(result)

        # Scan crypto
        for crypto in watchlist.crypto:
            result = self.scan_crypto(crypto.symbol, crypto.events)
            self.results.append(result)

        return self.results

    def scan_stock(self, symbol: str, events: list[str]) -> ScanResult:
        """Scan a single stock for configured events."""
        logger.info(f"Scanning {symbol} for events: {events}")
        result = ScanResult(symbol=symbol, asset_type="stock")

        if "congressional_trades" in events:
            self._scan_congressional(symbol, result)

        if "insider_trades" in events:
            self._scan_insider(symbol, result)

        if "options_flow" in events:
            self._scan_options(symbol, result)

        if "earnings" in events:
            self._scan_earnings(symbol, result)

        return result

    def scan_crypto(self, symbol: str, events: list[str]) -> ScanResult:
        """Scan a single crypto for configured events."""
        logger.info(f"Scanning {symbol} for events: {events}")
        result = ScanResult(symbol=symbol, asset_type="crypto")

        if "whale_transactions" in events or "large_transfers" in events:
            self._scan_crypto_whales(symbol, result)

        return result

    def _scan_congressional(self, symbol: str, result: ScanResult):
        """Scan for congressional trades."""
        try:
            config = watchlist.events.congressional_trades
            trades = self.congressional_collector.get_house_trades_by_ticker(symbol)

            # Filter by lookback period and amount
            cutoff = datetime.now() - timedelta(days=config.lookback_days)
            recent_trades = [
                t for t in trades
                if t.trade_date >= cutoff
                and (t.amount_min is None or t.amount_min >= config.min_amount)
            ]

            if recent_trades:
                buys = [t for t in recent_trades if "purchase" in t.transaction_type.lower()]
                sells = [t for t in recent_trades if "sale" in t.transaction_type.lower()]

                traders = list(set(t.representative for t in recent_trades))

                result.events_found.append({
                    "type": "congressional_trade",
                    "ticker": symbol,
                    "total_trades": len(recent_trades),
                    "buys": len(buys),
                    "sells": len(sells),
                    "traders": traders[:5],
                    "latest_date": max(t.trade_date for t in recent_trades),
                })
                logger.info(f"  Found {len(recent_trades)} congressional trades for {symbol}")

        except Exception as e:
            result.errors.append(f"Congressional scan error: {e}")
            logger.error(f"  Error scanning congressional for {symbol}: {e}")

    def _scan_insider(self, symbol: str, result: ScanResult):
        """Scan for insider trades via SEC Form 4."""
        try:
            config = watchlist.events.insider_trades

            # Get recent Form 4 filings for the ticker
            filings = self.sec_collector.get_recent_form4_filings(symbol, days_back=config.lookback_days)

            if filings:
                # Filter filings for this ticker and by date
                cutoff = datetime.now() - timedelta(days=config.lookback_days)
                relevant_filings = [
                    f for f in filings
                    if f.ticker.upper() == symbol.upper()
                    and f.trade_date >= cutoff
                    and f.transaction_type in config.transaction_types
                ]

                if relevant_filings:
                    buys = [f for f in relevant_filings if f.transaction_type == "P"]
                    sells = [f for f in relevant_filings if f.transaction_type == "S"]

                    result.events_found.append({
                        "type": "insider_trade",
                        "ticker": symbol,
                        "total_filings": len(relevant_filings),
                        "buys": len(buys),
                        "sells": len(sells),
                        "insiders": list(set(f.insider_name for f in relevant_filings))[:5],
                    })
                    logger.info(f"  Found {len(relevant_filings)} insider trades for {symbol}")

        except Exception as e:
            result.errors.append(f"Insider scan error: {e}")
            logger.error(f"  Error scanning insider for {symbol}: {e}")

    def _scan_options(self, symbol: str, result: ScanResult):
        """Scan for unusual options flow."""
        try:
            config = watchlist.events.options_flow

            # Get options chain and look for unusual activity
            activities = self.options_collector.get_options_chain_yahoo(symbol)

            # Filter by config thresholds
            unusual = [
                a for a in activities
                if a.volume_oi_ratio >= config.min_volume_oi_ratio
            ]

            if unusual:
                calls = [a for a in unusual if a.option_type == "CALL"]
                puts = [a for a in unusual if a.option_type == "PUT"]

                # Calculate estimated premium
                total_premium = sum(
                    (a.last_price or 0) * a.volume * 100
                    for a in unusual
                    if a.last_price
                )

                if total_premium >= config.min_premium or len(unusual) >= 3:
                    # Determine overall sentiment
                    call_volume = sum(a.volume for a in calls)
                    put_volume = sum(a.volume for a in puts)

                    if call_volume > put_volume * 1.5:
                        sentiment = "BULLISH"
                    elif put_volume > call_volume * 1.5:
                        sentiment = "BEARISH"
                    else:
                        sentiment = "MIXED"

                    result.events_found.append({
                        "type": "options_flow",
                        "ticker": symbol,
                        "unusual_contracts": len(unusual),
                        "calls": len(calls),
                        "puts": len(puts),
                        "estimated_premium": total_premium,
                        "sentiment": sentiment,
                        "top_strikes": [
                            {"strike": a.strike_price, "type": a.option_type, "vol_oi": round(a.volume_oi_ratio, 1)}
                            for a in sorted(unusual, key=lambda x: x.volume_oi_ratio, reverse=True)[:3]
                        ],
                    })
                    logger.info(f"  Found {len(unusual)} unusual options for {symbol} ({sentiment})")

        except Exception as e:
            result.errors.append(f"Options scan error: {e}")
            logger.error(f"  Error scanning options for {symbol}: {e}")

    def _scan_earnings(self, symbol: str, result: ScanResult):
        """Scan for upcoming earnings."""
        try:
            import yfinance as yf

            config = watchlist.events.earnings
            ticker = yf.Ticker(symbol)

            # Get earnings dates
            calendar = ticker.calendar

            if calendar is not None and not calendar.empty:
                # calendar can be a DataFrame with earnings date
                earnings_date = None

                if hasattr(calendar, 'iloc'):
                    # It's a DataFrame
                    if 'Earnings Date' in calendar.index:
                        earnings_date = calendar.loc['Earnings Date'].iloc[0]
                    elif len(calendar) > 0:
                        # Try first column
                        earnings_date = calendar.iloc[0, 0] if calendar.shape[1] > 0 else None

                if earnings_date:
                    # Convert to datetime if needed
                    if hasattr(earnings_date, 'to_pydatetime'):
                        earnings_date = earnings_date.to_pydatetime()
                    elif isinstance(earnings_date, str):
                        from dateutil import parser
                        earnings_date = parser.parse(earnings_date)

                    # Check if within alert window
                    if isinstance(earnings_date, datetime):
                        days_until = (earnings_date - datetime.now()).days

                        if 0 <= days_until <= config.days_before_alert:
                            result.events_found.append({
                                "type": "earnings",
                                "ticker": symbol,
                                "earnings_date": earnings_date.strftime("%Y-%m-%d"),
                                "days_until": days_until,
                            })
                            logger.info(f"  Earnings in {days_until} days for {symbol}")

        except Exception as e:
            # Earnings data often unavailable - don't treat as error
            logger.debug(f"  Could not get earnings for {symbol}: {e}")

    def _scan_crypto_whales(self, symbol: str, result: ScanResult):
        """Scan for crypto whale transactions."""
        try:
            config = watchlist.events.whale_transactions

            # Currently only supports BTC via blockchain.com
            if symbol.upper() in ["BTC", "BITCOIN"]:
                transactions = self.crypto_collector.get_recent_large_transactions(
                    min_value_btc=config.min_value_usd / 50000  # Rough BTC price estimate
                )

                if transactions:
                    result.events_found.append({
                        "type": "whale_transaction",
                        "symbol": symbol,
                        "transaction_count": len(transactions),
                        "total_value_btc": sum(t.get("value_btc", 0) for t in transactions),
                    })
                    logger.info(f"  Found {len(transactions)} whale transactions for {symbol}")

            elif symbol.upper() in ["LINK", "CHAINLINK"]:
                # LINK is an ERC-20 token - would need Etherscan API
                logger.info(f"  LINK whale tracking requires Etherscan API key")

            else:
                logger.info(f"  Crypto whale tracking not implemented for {symbol}")

        except Exception as e:
            result.errors.append(f"Crypto whale scan error: {e}")
            logger.error(f"  Error scanning crypto whales for {symbol}: {e}")

    def send_alerts(self) -> int:
        """Send Telegram alerts for all events found."""
        if not self.telegram.enabled:
            logger.warning("Telegram not configured - skipping alerts")
            return 0

        alerts_sent = 0
        events_with_data = [r for r in self.results if r.has_events]

        if not events_with_data:
            logger.info("No events found - no alerts to send")
            return 0

        for result in events_with_data:
            for event in result.events_found:
                message = self._format_event_alert(result.symbol, event)

                if self.dry_run:
                    logger.info(f"[DRY RUN] Would send: {message.title}")
                    print(f"\n{'='*50}")
                    print(f"ALERT: {message.title}")
                    print(f"{'='*50}")
                    print(message.body)
                else:
                    if self.telegram.send(message):
                        alerts_sent += 1
                        logger.info(f"Sent alert for {result.symbol}: {event['type']}")

        return alerts_sent

    def _format_event_alert(self, symbol: str, event: dict) -> AlertMessage:
        """Format an event as an alert message."""
        event_type = event.get("type", "unknown")

        if event_type == "congressional_trade":
            title = f"Congressional Trade: ${symbol}"
            body = self._format_congressional_alert(event)
            priority = "high" if event["buys"] > 2 or event["sells"] > 2 else "normal"

        elif event_type == "insider_trade":
            title = f"Insider Activity: ${symbol}"
            body = self._format_insider_alert(event)
            priority = "high" if event["buys"] > 0 else "normal"

        elif event_type == "options_flow":
            title = f"Options Flow: ${symbol}"
            body = self._format_options_alert(event)
            priority = "high" if event["sentiment"] in ["BULLISH", "BEARISH"] else "normal"

        elif event_type == "earnings":
            title = f"Earnings Alert: ${symbol}"
            body = self._format_earnings_alert(event)
            priority = "high" if event["days_until"] <= 3 else "normal"

        elif event_type == "whale_transaction":
            title = f"Whale Activity: {symbol}"
            body = self._format_whale_alert(event)
            priority = "normal"

        else:
            title = f"Event: ${symbol}"
            body = str(event)
            priority = "normal"

        return AlertMessage(
            title=title,
            body=body,
            ticker=symbol,
            signal_type=event_type,
            priority=priority,
        )

    def _format_congressional_alert(self, event: dict) -> str:
        """Format congressional trade event."""
        lines = [
            f"Total Trades: {event['total_trades']}",
            f"Buys: {event['buys']} | Sells: {event['sells']}",
            f"Traders: {', '.join(event['traders'][:3])}",
            f"Latest: {event['latest_date'].strftime('%Y-%m-%d')}",
        ]
        return "\n".join(lines)

    def _format_insider_alert(self, event: dict) -> str:
        """Format insider trade event."""
        lines = [
            f"Total Filings: {event['total_filings']}",
            f"Buys: {event['buys']} | Sells: {event['sells']}",
            f"Insiders: {', '.join(event['insiders'][:3])}",
        ]
        return "\n".join(lines)

    def _format_options_alert(self, event: dict) -> str:
        """Format options flow event."""
        lines = [
            f"Sentiment: {event['sentiment']}",
            f"Unusual Contracts: {event['unusual_contracts']}",
            f"Calls: {event['calls']} | Puts: {event['puts']}",
            f"Est. Premium: ${event['estimated_premium']:,.0f}",
            "",
            "Top Strikes:",
        ]
        for strike in event.get("top_strikes", []):
            lines.append(f"  ${strike['strike']} {strike['type']} (Vol/OI: {strike['vol_oi']}x)")
        return "\n".join(lines)

    def _format_earnings_alert(self, event: dict) -> str:
        """Format earnings event."""
        return f"Earnings Date: {event['earnings_date']}\nDays Until: {event['days_until']}"

    def _format_whale_alert(self, event: dict) -> str:
        """Format whale transaction event."""
        return f"Transactions: {event['transaction_count']}\nTotal Value: {event.get('total_value_btc', 0):.2f} BTC"

    def print_summary(self):
        """Print scan summary to console."""
        print("\n" + "=" * 60)
        print("WATCHLIST SCAN SUMMARY")
        print("=" * 60)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Stocks scanned: {len(watchlist.stocks)}")
        print(f"Crypto scanned: {len(watchlist.crypto)}")
        print()

        total_events = 0
        for result in self.results:
            status = "OK" if not result.errors else "ERROR"
            event_count = len(result.events_found)
            total_events += event_count

            print(f"[{status}] {result.symbol} ({result.asset_type}): {event_count} events")

            for event in result.events_found:
                event_type = event.get("type", "unknown")
                if event_type == "congressional_trade":
                    print(f"      Congressional: {event['buys']}B/{event['sells']}S by {len(event['traders'])} traders")
                elif event_type == "options_flow":
                    print(f"      Options: {event['sentiment']} - {event['unusual_contracts']} unusual")
                elif event_type == "earnings":
                    print(f"      Earnings: in {event['days_until']} days")
                elif event_type == "insider_trade":
                    print(f"      Insider: {event['buys']}B/{event['sells']}S")
                else:
                    print(f"      {event_type}")

            for error in result.errors:
                print(f"      Error: {error}")

        print()
        print(f"Total events found: {total_events}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Scan watchlist for binary events")
    parser.add_argument("--dry-run", action="store_true", help="Scan without sending alerts")
    parser.add_argument("--ticker", type=str, help="Scan single ticker only")
    args = parser.parse_args()

    scanner = WatchlistScanner(dry_run=args.dry_run)

    if args.ticker:
        # Scan single ticker
        symbol = args.ticker.upper()
        stock_config = watchlist.get_stock(symbol)
        crypto_config = watchlist.get_crypto(symbol)

        if stock_config:
            result = scanner.scan_stock(symbol, stock_config.events)
            scanner.results.append(result)
        elif crypto_config:
            result = scanner.scan_crypto(symbol, crypto_config.events)
            scanner.results.append(result)
        else:
            logger.error(f"Ticker {symbol} not found in watchlist")
            sys.exit(1)
    else:
        # Scan all
        scanner.scan_all()

    # Print summary
    scanner.print_summary()

    # Send alerts
    alerts_sent = scanner.send_alerts()
    logger.info(f"Alerts sent: {alerts_sent}")

    # Exit with error if any scan errors occurred
    errors = sum(len(r.errors) for r in scanner.results)
    if errors > 0:
        logger.warning(f"Scan completed with {errors} errors")


if __name__ == "__main__":
    main()
