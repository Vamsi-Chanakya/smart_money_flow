#!/usr/bin/env python3
"""Script to collect data from all sources.

Run manually or schedule with cron.
Usage: python scripts/collect_data.py [--source SOURCE]
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.sec_edgar import SecEdgarCollector
from src.collectors.congressional import CongressionalCollector
from src.storage.repository import Repository
from src.storage.models import CongressionalTrade as CongressionalTradeModel
from src.utils.config import settings, get_project_root
from src.utils.logger import get_logger

logger = get_logger(__name__)


def collect_congressional(repo: Repository):
    """Collect congressional trading data."""
    logger.info("Collecting congressional trades...")

    collector = CongressionalCollector()
    trades = collector.get_all_house_trades()

    logger.info(f"Fetched {len(trades)} trades from House Stock Watcher")

    # Store in database
    session = repo.get_session()
    added = 0

    try:
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
            repo.add_congressional_trade(session, model)
            added += 1

        session.commit()
        logger.info(f"Added {added} congressional trades to database")

    except Exception as e:
        session.rollback()
        logger.error(f"Error storing congressional trades: {e}")
    finally:
        session.close()


def collect_sec_13f(repo: Repository):
    """Collect 13F institutional holdings."""
    logger.info("Collecting 13F filings...")

    collector = SecEdgarCollector()

    # Get holdings from notable filers
    for cik, name in collector.NOTABLE_FILERS.items():
        logger.info(f"Fetching {name}...")
        try:
            holdings = collector.get_13f_holdings(cik)
            logger.info(f"  Found {len(holdings)} holdings")
            # TODO: Store in database
        except Exception as e:
            logger.error(f"  Error: {e}")


def collect_insider_trades(repo: Repository):
    """Collect Form 4 insider trades."""
    logger.info("Collecting Form 4 filings...")
    # TODO: Implement
    pass


def main():
    parser = argparse.ArgumentParser(description="Collect smart money data")
    parser.add_argument(
        "--source",
        choices=["all", "congressional", "sec", "insider"],
        default="all",
        help="Data source to collect",
    )
    args = parser.parse_args()

    # Initialize database
    db_path = get_project_root() / "data" / "smartmoney.db"
    db_url = f"sqlite:///{db_path}"
    repo = Repository(db_url)

    if args.source in ("all", "congressional"):
        collect_congressional(repo)

    if args.source in ("all", "sec"):
        collect_sec_13f(repo)

    if args.source in ("all", "insider"):
        collect_insider_trades(repo)

    logger.info("Data collection complete!")


if __name__ == "__main__":
    main()
