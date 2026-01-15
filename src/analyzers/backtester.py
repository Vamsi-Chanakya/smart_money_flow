"""Backtesting framework for Smart Money signals.

Test historical signal performance against actual price movements.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf
import pandas as pd
import numpy as np

from .signal_engine import TradingSignal, SignalDirection, SignalStrength
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BacktestResult:
    """Result of backtesting a single signal."""

    ticker: str
    signal_date: datetime
    signal_direction: SignalDirection
    signal_confidence: float
    price_at_signal: float

    # Returns
    return_1d: Optional[float] = None
    return_7d: Optional[float] = None
    return_30d: Optional[float] = None

    # Prices
    price_after_1d: Optional[float] = None
    price_after_7d: Optional[float] = None
    price_after_30d: Optional[float] = None

    # Analysis
    is_winner: Optional[bool] = None  # Based on 30d return
    max_gain: Optional[float] = None
    max_drawdown: Optional[float] = None


@dataclass
class BacktestSummary:
    """Summary of backtest results."""

    total_signals: int
    winners: int
    losers: int
    win_rate: float

    avg_return_1d: float
    avg_return_7d: float
    avg_return_30d: float

    best_return: float
    worst_return: float

    avg_winner_return: float
    avg_loser_return: float

    sharpe_ratio: Optional[float]
    profit_factor: Optional[float]

    by_signal_type: dict = field(default_factory=dict)
    by_direction: dict = field(default_factory=dict)


class Backtester:
    """Backtester for Smart Money signals.

    Uses yfinance for historical price data.
    """

    def __init__(self):
        self.results: list[BacktestResult] = []
        self.price_cache: dict[str, pd.DataFrame] = {}

    def get_price_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime = None,
    ) -> Optional[pd.DataFrame]:
        """Get historical price data for a ticker.

        Args:
            ticker: Stock ticker
            start_date: Start date for data
            end_date: End date (defaults to today)

        Returns:
            DataFrame with OHLCV data
        """
        if end_date is None:
            end_date = datetime.now()

        cache_key = f"{ticker}_{start_date.date()}_{end_date.date()}"

        if cache_key in self.price_cache:
            return self.price_cache[cache_key]

        try:
            logger.info(f"Fetching price data for {ticker}")
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)

            if df.empty:
                logger.warning(f"No price data for {ticker}")
                return None

            self.price_cache[cache_key] = df
            return df

        except Exception as e:
            logger.error(f"Error fetching price data for {ticker}: {e}")
            return None

    def backtest_signal(
        self,
        signal: TradingSignal,
        holding_days: list[int] = [1, 7, 30],
    ) -> Optional[BacktestResult]:
        """Backtest a single signal.

        Args:
            signal: Trading signal to test
            holding_days: List of holding periods to evaluate

        Returns:
            Backtest result or None if data unavailable
        """
        # Get price data from signal date to now
        end_date = datetime.now()
        start_date = signal.generated_at - timedelta(days=1)

        df = self.get_price_data(signal.ticker, start_date, end_date)

        if df is None or df.empty:
            return None

        # Find signal date in data
        signal_date = signal.generated_at.date()

        try:
            # Get closest trading day to signal date
            df_dates = df.index.date
            signal_idx = None

            for i, d in enumerate(df_dates):
                if d >= signal_date:
                    signal_idx = i
                    break

            if signal_idx is None:
                return None

            price_at_signal = df.iloc[signal_idx]["Close"]

            result = BacktestResult(
                ticker=signal.ticker,
                signal_date=signal.generated_at,
                signal_direction=signal.direction,
                signal_confidence=signal.confidence,
                price_at_signal=price_at_signal,
            )

            # Calculate returns for each holding period
            for days in holding_days:
                future_idx = signal_idx + days

                if future_idx < len(df):
                    future_price = df.iloc[future_idx]["Close"]
                    raw_return = (future_price - price_at_signal) / price_at_signal

                    # Adjust for signal direction (SELL signals profit from decline)
                    if signal.direction == SignalDirection.SELL:
                        raw_return = -raw_return

                    if days == 1:
                        result.return_1d = raw_return
                        result.price_after_1d = future_price
                    elif days == 7:
                        result.return_7d = raw_return
                        result.price_after_7d = future_price
                    elif days == 30:
                        result.return_30d = raw_return
                        result.price_after_30d = future_price

            # Determine winner/loser based on 30d return
            if result.return_30d is not None:
                result.is_winner = result.return_30d > 0

            # Calculate max gain/drawdown
            if signal_idx + 30 <= len(df):
                period_data = df.iloc[signal_idx:signal_idx + 30]["Close"]
                period_returns = (period_data - price_at_signal) / price_at_signal

                if signal.direction == SignalDirection.SELL:
                    period_returns = -period_returns

                result.max_gain = period_returns.max()
                result.max_drawdown = period_returns.min()

            return result

        except Exception as e:
            logger.error(f"Error backtesting {signal.ticker}: {e}")
            return None

    def backtest_signals(self, signals: list[TradingSignal]) -> list[BacktestResult]:
        """Backtest multiple signals.

        Args:
            signals: List of signals to backtest

        Returns:
            List of backtest results
        """
        results = []

        for signal in signals:
            result = self.backtest_signal(signal)
            if result:
                results.append(result)
                logger.info(
                    f"Backtested {signal.ticker}: "
                    f"30d return = {result.return_30d:.1%}" if result.return_30d else "N/A"
                )

        self.results.extend(results)
        return results

    def generate_summary(self, results: list[BacktestResult] = None) -> BacktestSummary:
        """Generate summary statistics from backtest results.

        Args:
            results: Results to summarize (uses stored results if None)

        Returns:
            Summary statistics
        """
        if results is None:
            results = self.results

        if not results:
            return BacktestSummary(
                total_signals=0,
                winners=0,
                losers=0,
                win_rate=0.0,
                avg_return_1d=0.0,
                avg_return_7d=0.0,
                avg_return_30d=0.0,
                best_return=0.0,
                worst_return=0.0,
                avg_winner_return=0.0,
                avg_loser_return=0.0,
                sharpe_ratio=None,
                profit_factor=None,
            )

        # Filter results with 30d returns
        valid_results = [r for r in results if r.return_30d is not None]

        if not valid_results:
            return BacktestSummary(
                total_signals=len(results),
                winners=0,
                losers=0,
                win_rate=0.0,
                avg_return_1d=0.0,
                avg_return_7d=0.0,
                avg_return_30d=0.0,
                best_return=0.0,
                worst_return=0.0,
                avg_winner_return=0.0,
                avg_loser_return=0.0,
                sharpe_ratio=None,
                profit_factor=None,
            )

        # Calculate stats
        winners = [r for r in valid_results if r.is_winner]
        losers = [r for r in valid_results if not r.is_winner]

        returns_1d = [r.return_1d for r in valid_results if r.return_1d is not None]
        returns_7d = [r.return_7d for r in valid_results if r.return_7d is not None]
        returns_30d = [r.return_30d for r in valid_results]

        winner_returns = [r.return_30d for r in winners]
        loser_returns = [r.return_30d for r in losers]

        # Sharpe ratio (annualized, assuming 30d holding)
        if len(returns_30d) > 1:
            returns_array = np.array(returns_30d)
            sharpe = (returns_array.mean() / returns_array.std()) * np.sqrt(12)  # Annualized
        else:
            sharpe = None

        # Profit factor
        total_gains = sum(r for r in returns_30d if r > 0)
        total_losses = abs(sum(r for r in returns_30d if r < 0))
        profit_factor = total_gains / total_losses if total_losses > 0 else None

        return BacktestSummary(
            total_signals=len(results),
            winners=len(winners),
            losers=len(losers),
            win_rate=len(winners) / len(valid_results) if valid_results else 0,
            avg_return_1d=np.mean(returns_1d) if returns_1d else 0,
            avg_return_7d=np.mean(returns_7d) if returns_7d else 0,
            avg_return_30d=np.mean(returns_30d) if returns_30d else 0,
            best_return=max(returns_30d) if returns_30d else 0,
            worst_return=min(returns_30d) if returns_30d else 0,
            avg_winner_return=np.mean(winner_returns) if winner_returns else 0,
            avg_loser_return=np.mean(loser_returns) if loser_returns else 0,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
        )

    def format_summary(self, summary: BacktestSummary) -> str:
        """Format summary for display.

        Args:
            summary: Backtest summary

        Returns:
            Formatted string
        """
        return f"""
╔════════════════════════════════════════════════════════════╗
║              BACKTEST SUMMARY                              ║
╠════════════════════════════════════════════════════════════╣
║  Total Signals:     {summary.total_signals:>10}                          ║
║  Winners:           {summary.winners:>10}                          ║
║  Losers:            {summary.losers:>10}                          ║
║  Win Rate:          {summary.win_rate:>10.1%}                          ║
╠════════════════════════════════════════════════════════════╣
║  RETURNS                                                   ║
║  ─────────────────────────────────────────────────────────║
║  Avg 1-Day:         {summary.avg_return_1d:>+10.2%}                          ║
║  Avg 7-Day:         {summary.avg_return_7d:>+10.2%}                          ║
║  Avg 30-Day:        {summary.avg_return_30d:>+10.2%}                          ║
║                                                            ║
║  Best Return:       {summary.best_return:>+10.2%}                          ║
║  Worst Return:      {summary.worst_return:>+10.2%}                          ║
║                                                            ║
║  Avg Winner:        {summary.avg_winner_return:>+10.2%}                          ║
║  Avg Loser:         {summary.avg_loser_return:>+10.2%}                          ║
╠════════════════════════════════════════════════════════════╣
║  RISK METRICS                                              ║
║  ─────────────────────────────────────────────────────────║
║  Sharpe Ratio:      {str(f"{summary.sharpe_ratio:.2f}" if summary.sharpe_ratio else "N/A"):>10}                          ║
║  Profit Factor:     {str(f"{summary.profit_factor:.2f}" if summary.profit_factor else "N/A"):>10}                          ║
╚════════════════════════════════════════════════════════════╝
"""

    def export_results(self, filepath: str, results: list[BacktestResult] = None) -> bool:
        """Export results to CSV.

        Args:
            filepath: Output file path
            results: Results to export (uses stored if None)

        Returns:
            True if successful
        """
        if results is None:
            results = self.results

        if not results:
            logger.warning("No results to export")
            return False

        try:
            data = []
            for r in results:
                data.append({
                    "ticker": r.ticker,
                    "signal_date": r.signal_date,
                    "direction": r.signal_direction.value,
                    "confidence": r.signal_confidence,
                    "price_at_signal": r.price_at_signal,
                    "return_1d": r.return_1d,
                    "return_7d": r.return_7d,
                    "return_30d": r.return_30d,
                    "is_winner": r.is_winner,
                    "max_gain": r.max_gain,
                    "max_drawdown": r.max_drawdown,
                })

            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False)
            logger.info(f"Exported {len(results)} results to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error exporting results: {e}")
            return False
