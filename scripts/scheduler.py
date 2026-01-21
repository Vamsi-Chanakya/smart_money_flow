#!/usr/bin/env python3
"""Automated scheduler for Smart Money Flow data collection.

Run as a background service to automatically collect data and send alerts.

Usage:
    python scripts/scheduler.py              # Run scheduler
    python scripts/scheduler.py --once       # Run once and exit
    python scripts/scheduler.py --test       # Test all collectors
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.collectors.congressional import CongressionalCollector
from src.collectors.sec_edgar import SecEdgarCollector
from src.collectors.options_flow import OptionsFlowCollector
from src.collectors.crypto_whales import BitcoinWhaleCollector
from src.analyzers.signal_engine import SignalEngine
from src.output.alerts import TelegramAlert, AlertMessage
from src.storage.repository import Repository
from src.storage.models import CongressionalTrade as CongressionalTradeModel
from src.utils.config import settings, get_project_root
from src.utils.logger import get_logger

logger = get_logger(__name__)


from src.collectors.market_sentiment import MarketSentimentCollector
from src.collectors.unusual_whales import UnusualWhalesCollector

# ... imports ...

class SmartMoneyScheduler:
    """Scheduler for automated data collection and alerting."""

    def __init__(self):
        # Initialize database
        db_path = get_project_root() / "data" / "smartmoney.db"
        self.repo = Repository(f"sqlite:///{db_path}")

        # Initialize collectors
        self.congressional_collector = CongressionalCollector()
        self.sec_collector = SecEdgarCollector()
        self.options_collector = OptionsFlowCollector()
        self.btc_collector = BitcoinWhaleCollector()
        self.sentiment_collector = MarketSentimentCollector()
        self.unusual_whales_collector = UnusualWhalesCollector()  # NEW

        # Initialize alert system
        self.telegram = TelegramAlert()
        self.signal_engine = SignalEngine()

        # Track stats
        self.stats = {
            "last_run": None,
            "congressional_trades": 0,
            "signals_generated": 0,
            "alerts_sent": 0,
            "sentiment_checks": 0,
        }

    def collect_congressional(self):
        """Collect congressional trading data."""
        logger.info("Collecting congressional trades...")

        try:
            trades = self.congressional_collector.get_all_house_trades()
            logger.info(f"Fetched {len(trades)} trades")

            # Store in database
            session = self.repo.get_session()
            added = 0

            for trade in trades:
                model = CongressionalTradeModel(
                    disclosure_id=trade.disclosure_id,
                    representative=trade.representative,
                    chamber=trade.chamber,
                    party=trade.party,
                    state=trade.state,
                    district=trade.district,
                    ticker=trade.ticker,
                    asset_description=trade.asset_description,
                    asset_type=trade.asset_type,
                    transaction_type=trade.transaction_type,
                    trade_date=trade.trade_date,
                    disclosure_date=trade.disclosure_date,
                    amount_min=trade.amount_min,
                    amount_max=trade.amount_max,
                    amount_text=trade.amount_text,
                    owner=trade.owner,
                )
                self.repo.add_congressional_trade(session, model)
                added += 1

            session.commit()
            session.close()

            self.stats["congressional_trades"] = added
            logger.info(f"Stored {added} congressional trades")

            return trades

        except Exception as e:
            logger.error(f"Error collecting congressional data: {e}")
            return []

    def collect_sec_data(self):
        """Collect SEC EDGAR data."""
        logger.info("Collecting SEC data...")

        try:
            # Get holdings from notable filers
            for cik, name in list(self.sec_collector.NOTABLE_FILERS.items())[:3]:
                logger.info(f"Checking {name}...")
                try:
                    submissions = self.sec_collector.get_company_submissions(cik)
                    logger.info(f"  Latest filing: {submissions.get('filings', {}).get('recent', {}).get('filingDate', ['N/A'])[0]}")
                except Exception as e:
                    logger.error(f"  Error: {e}")

        except Exception as e:
            logger.error(f"Error collecting SEC data: {e}")

    def collect_sentiment(self):
        """Collect market sentiment data."""
        logger.info("Collecting market sentiment...")
        try:
            # 1. Crypto Fear & Greed (General Market Risk Proxy)
            fng = self.sentiment_collector.get_crypto_fear_greed()
            if fng:
                logger.info(f"Crypto Fear & Greed: {fng['value']} ({fng['classification']})")
                self.stats["sentiment_checks"] += 1
            
            # 2. Stock Sentiment (for major indices/tickers)
            # This consumes API quota, so we limit it.
            # Maybe check SPY or major tech.
            spy_sentiment = self.sentiment_collector.get_stock_sentiment("SPY")
            if spy_sentiment:
                logger.info(f"SPY Sentiment: {spy_sentiment['sentiment_label']} ({spy_sentiment['sentiment_score']})")

            return fng
        except Exception as e:
            logger.error(f"Error collecting sentiment: {e}")
            return None

    def collect_unusual_whales(self):
        """Collect data from Unusual Whales."""
        # Only run if key is configured to avoid log noise
        if not self.unusual_whales_collector.api_key:
            return

        logger.info("Collecting Unusual Whales data...")
        try:
            trades = self.unusual_whales_collector.get_latest_option_trades(limit=10)
            if trades:
                logger.info(f"Unusual Whales: Found {len(trades)} significant option trades")
                # Here we would normally process/store them or convert to signals
                # For now just logging availability
        except Exception as e:
            logger.error(f"Error collecting Unusual Whales: {e}")

    def analyze_and_generate_signals(self, trades):
        """Analyze collected data and generate signals."""
        logger.info("Generating signals...")

        from collections import defaultdict
        from datetime import timedelta

        ticker_stats = defaultdict(lambda: {"buys": 0, "sells": 0, "traders": []})
        cutoff = datetime.now() - timedelta(days=30)

        for trade in trades:
            if not trade.ticker or trade.trade_date < cutoff:
                continue

            ticker = trade.ticker.upper()
            if "purchase" in trade.transaction_type.lower():
                ticker_stats[ticker]["buys"] += 1
            elif "sale" in trade.transaction_type.lower():
                ticker_stats[ticker]["sells"] += 1
            ticker_stats[ticker]["traders"].append(trade.representative)

        signals = []
        for ticker, stats in ticker_stats.items():
            if stats["buys"] + stats["sells"] < 2:
                continue

            component = self.signal_engine.generate_congressional_signal(
                ticker=ticker,
                trade_count=stats["buys"] + stats["sells"],
                buy_count=stats["buys"],
                sell_count=stats["sells"],
                notable_traders=list(set(stats["traders"]))[:3],
            )

            if component:
                signal = self.signal_engine.aggregate_signals(ticker, [component])
                if signal and signal.confidence >= 0.5:
                    signals.append(signal)

        signals.sort(key=lambda x: x.confidence, reverse=True)
        self.stats["signals_generated"] = len(signals)

        logger.info(f"Generated {len(signals)} signals")
        return signals[:10]  # Top 10

    def send_alerts(self, signals):
        """Send alerts for high-confidence signals."""
        if not self.telegram.enabled:
            logger.warning("Telegram not configured - skipping alerts")
            return

        alerts_sent = 0

        for signal in signals:
            if signal.confidence >= 0.7:  # High confidence threshold
                try:
                    if self.telegram.send_signal(signal):
                        alerts_sent += 1
                        logger.info(f"Sent alert for {signal.ticker}")
                except Exception as e:
                    logger.error(f"Error sending alert: {e}")

        self.stats["alerts_sent"] = alerts_sent
        logger.info(f"Sent {alerts_sent} alerts")

    def send_daily_summary(self, signals):
        """Send daily summary via Telegram."""
        if not self.telegram.enabled:
            return

        try:
            self.telegram.send_daily_summary(signals, self.stats)
            logger.info("Sent daily summary")
        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")

    def run_full_collection(self):
        """Run full data collection cycle."""
        logger.info("=" * 50)
        logger.info(f"Starting collection cycle at {datetime.now()}")
        logger.info("=" * 50)

        self.stats["last_run"] = datetime.now()

        # 1. Collect data
        trades = self.collect_congressional()
        self.collect_sec_data()
        self.collect_sentiment()
        self.collect_unusual_whales()

        # 2. Generate signals
        if trades:
            signals = self.analyze_and_generate_signals(trades)

            # 3. Send alerts for high-confidence signals
            # 3. Send alerts for high-confidence signals
            self.send_alerts(signals)
            
            # 4. Always send a summary so user knows it ran
            self.send_daily_summary(signals)

        logger.info("Collection cycle complete")
        logger.info(f"Stats: {self.stats}")

    def run_morning_job(self):
        """Morning job: Collect data and send summary."""
        logger.info("Running morning job...")
        self.run_full_collection()

    def run_evening_job(self):
        """Evening job: Generate signals and send alerts."""
        logger.info("Running evening job...")

        trades = self.collect_congressional()
        if trades:
            signals = self.analyze_and_generate_signals(trades)
            self.send_alerts(signals)
            self.send_daily_summary(signals)


def main():
    parser = argparse.ArgumentParser(description="Smart Money Flow Scheduler")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--test", action="store_true", help="Test all collectors")
    args = parser.parse_args()

    scheduler_instance = SmartMoneyScheduler()

    if args.test:
        logger.info("Testing collectors...")

        # Test congressional
        logger.info("\n--- Testing Congressional Collector ---")
        try:
            trades = scheduler_instance.congressional_collector.get_all_house_trades()
            logger.info(f"SUCCESS: Got {len(trades)} trades")
        except Exception as e:
            logger.error(f"FAILED: {e}")

        # Test SEC
        logger.info("\n--- Testing SEC Collector ---")
        try:
            submissions = scheduler_instance.sec_collector.get_company_submissions("1067983")
            logger.info(f"SUCCESS: Berkshire Hathaway - {submissions.get('name')}")
        except Exception as e:
            logger.error(f"FAILED: {e}")

        # Test Options
        logger.info("\n--- Testing Options Collector ---")
        try:
            pc_ratio = scheduler_instance.options_collector.calculate_put_call_ratio("AAPL")
            logger.info(f"SUCCESS: AAPL P/C Ratio = {pc_ratio}")
        except Exception as e:
            logger.error(f"FAILED: {e}")

        # Test Sentiment
        logger.info("\n--- Testing Sentiment Collector ---")
        try:
            fng = scheduler_instance.sentiment_collector.get_crypto_fear_greed()
            logger.info(f"SUCCESS: Crypto Fear & Greed = {fng}")
            
            # Only test stock sentiment if key is present to avoid error log spam
            if scheduler_instance.sentiment_collector.av_api_key:
                stock_sent = scheduler_instance.sentiment_collector.get_stock_sentiment("SPY")
                logger.info(f"SUCCESS: SPY Sentiment = {stock_sent}")
            else:
                logger.info("SKIPPED: Alpha Vantage Key not set")
        except Exception as e:
            logger.error(f"FAILED: {e}")

        # Test Unusual Whales
        logger.info("\n--- Testing Unusual Whales ---")
        if scheduler_instance.unusual_whales_collector.api_key:
            try:
                trades = scheduler_instance.unusual_whales_collector.get_latest_option_trades(limit=1)
                logger.info(f"SUCCESS: Fetched {len(trades)} trades")
            except Exception as e:
                logger.error(f"FAILED: {e}")
        else:
            logger.info("SKIPPED: API Key not set")

        # Test Telegram
        logger.info("\n--- Testing Telegram ---")
        if scheduler_instance.telegram.enabled:
            if scheduler_instance.telegram.test_connection():
                logger.info("SUCCESS: Telegram connected")
            else:
                logger.error("FAILED: Telegram connection failed")
        else:
            logger.warning("SKIPPED: Telegram not configured")

        return

    if args.once:
        scheduler_instance.run_full_collection()
        return

    # Set up scheduled jobs
    scheduler = BlockingScheduler()

    # Morning collection at 8:30 AM (before work)
    scheduler.add_job(
        scheduler_instance.run_morning_job,
        CronTrigger(hour=8, minute=30),
        id="morning_collection",
        name="Morning data collection",
    )

    # Midday check at 12:00 PM (lunch break)
    scheduler.add_job(
        scheduler_instance.run_full_collection,
        CronTrigger(hour=12, minute=0),
        id="midday_check",
        name="Midday data check",
    )

    # Evening summary at 5:30 PM (after work)
    scheduler.add_job(
        scheduler_instance.run_evening_job,
        CronTrigger(hour=17, minute=30),
        id="evening_analysis",
        name="Evening signal analysis",
    )

    logger.info("Scheduler started. Jobs:")
    logger.info("  - Morning collection: 8:30 AM")
    logger.info("  - Midday check: 12:00 PM")
    logger.info("  - Evening summary: 5:30 PM")
    logger.info("\nPress Ctrl+C to exit")

    try:
        # Run initial collection
        scheduler_instance.run_full_collection()

        # Start scheduler
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")


if __name__ == "__main__":
    main()
