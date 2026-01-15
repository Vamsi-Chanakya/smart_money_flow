"""Signal Generation Engine - Aggregate data into actionable signals.

Combines data from multiple sources to generate trading signals
with confidence scores.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from ..utils.config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SignalType(Enum):
    """Types of trading signals."""

    INSTITUTIONAL = "institutional"
    INSIDER = "insider"
    CONGRESSIONAL = "congressional"
    OPTIONS_FLOW = "options_flow"
    CRYPTO_WHALE = "crypto_whale"
    COMPOSITE = "composite"  # Multiple signals combined


class SignalDirection(Enum):
    """Signal direction."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class SignalStrength(Enum):
    """Signal strength classification."""

    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


@dataclass
class SignalComponent:
    """Individual component contributing to a signal."""

    source: SignalType
    direction: SignalDirection
    strength: float  # 0.0 to 1.0
    details: str
    timestamp: datetime
    raw_data: dict = field(default_factory=dict)


@dataclass
class TradingSignal:
    """Aggregated trading signal."""

    ticker: str
    direction: SignalDirection
    confidence: float  # 0.0 to 1.0
    strength: SignalStrength
    signal_type: SignalType
    components: list[SignalComponent]
    generated_at: datetime
    expires_at: Optional[datetime]
    notes: str
    price_at_signal: Optional[float] = None


class SignalEngine:
    """Engine for generating and aggregating trading signals.

    Weights (configurable):
    - Institutional accumulation: 0.9
    - Insider cluster buy: 0.85
    - Congressional trade: 0.6
    - Options flow: 0.5
    - Cross-signal bonus: 1.5x
    """

    def __init__(self):
        self.weights = {
            SignalType.INSTITUTIONAL: settings.signals.institutional_accumulation,
            SignalType.INSIDER: settings.signals.insider_cluster_buy,
            SignalType.CONGRESSIONAL: settings.signals.congressional_trade,
            SignalType.OPTIONS_FLOW: settings.signals.options_flow,
            SignalType.CRYPTO_WHALE: 0.5,
        }
        self.cross_signal_bonus = settings.signals.cross_signal_bonus

    def generate_institutional_signal(
        self,
        ticker: str,
        filer_count: int,
        total_shares_added: int,
        notable_filers: list[str],
    ) -> Optional[SignalComponent]:
        """Generate signal from institutional accumulation.

        Args:
            ticker: Stock ticker
            filer_count: Number of institutions adding position
            total_shares_added: Total shares accumulated
            notable_filers: List of notable fund names

        Returns:
            Signal component if criteria met
        """
        min_filers = settings.alerts.institutional_min_filers

        if filer_count < min_filers:
            return None

        # Calculate strength based on filer count
        # 2 filers = 0.4, 5 filers = 0.7, 10+ filers = 1.0
        strength = min(1.0, 0.2 + (filer_count * 0.1))

        # Boost for notable filers
        notable_boost = min(0.2, len(notable_filers) * 0.05)
        strength = min(1.0, strength + notable_boost)

        details = f"{filer_count} institutions accumulated {total_shares_added:,} shares"
        if notable_filers:
            details += f" (including {', '.join(notable_filers[:3])})"

        return SignalComponent(
            source=SignalType.INSTITUTIONAL,
            direction=SignalDirection.BUY,
            strength=strength,
            details=details,
            timestamp=datetime.now(),
            raw_data={
                "filer_count": filer_count,
                "total_shares": total_shares_added,
                "notable_filers": notable_filers,
            },
        )

    def generate_insider_signal(
        self,
        ticker: str,
        insider_count: int,
        total_value: float,
        is_cluster_buy: bool,
        executive_buys: int = 0,
    ) -> Optional[SignalComponent]:
        """Generate signal from insider trading.

        Args:
            ticker: Stock ticker
            insider_count: Number of unique insiders
            total_value: Total dollar value of purchases
            is_cluster_buy: Whether this is a cluster buy (multiple in 30 days)
            executive_buys: Number of CEO/CFO purchases

        Returns:
            Signal component if criteria met
        """
        min_insiders = settings.alerts.insider_cluster_min_count

        if not is_cluster_buy or insider_count < min_insiders:
            return None

        # Base strength from insider count
        strength = min(1.0, 0.3 + (insider_count * 0.15))

        # Boost for large values
        if total_value > 1_000_000:
            strength = min(1.0, strength + 0.2)
        elif total_value > 500_000:
            strength = min(1.0, strength + 0.1)

        # Boost for executive buys
        strength = min(1.0, strength + (executive_buys * 0.1))

        details = f"Cluster buy: {insider_count} insiders purchased ${total_value:,.0f}"
        if executive_buys:
            details += f" ({executive_buys} executives)"

        return SignalComponent(
            source=SignalType.INSIDER,
            direction=SignalDirection.BUY,
            strength=strength,
            details=details,
            timestamp=datetime.now(),
            raw_data={
                "insider_count": insider_count,
                "total_value": total_value,
                "executive_buys": executive_buys,
            },
        )

    def generate_congressional_signal(
        self,
        ticker: str,
        trade_count: int,
        buy_count: int,
        sell_count: int,
        notable_traders: list[str],
    ) -> Optional[SignalComponent]:
        """Generate signal from congressional trades.

        Args:
            ticker: Stock ticker
            trade_count: Total trades
            buy_count: Number of purchases
            sell_count: Number of sales
            notable_traders: Names of notable traders

        Returns:
            Signal component if criteria met
        """
        if trade_count < 2:
            return None

        net = buy_count - sell_count

        if net == 0:
            return None

        direction = SignalDirection.BUY if net > 0 else SignalDirection.SELL

        # Strength based on net trades
        strength = min(1.0, abs(net) * 0.2)

        # Boost for notable traders
        if notable_traders:
            strength = min(1.0, strength + 0.15)

        action = "bought" if direction == SignalDirection.BUY else "sold"
        details = f"Congress {action} {abs(net)} net ({buy_count} buys, {sell_count} sells)"
        if notable_traders:
            details += f" by {', '.join(notable_traders[:2])}"

        return SignalComponent(
            source=SignalType.CONGRESSIONAL,
            direction=direction,
            strength=strength,
            details=details,
            timestamp=datetime.now(),
            raw_data={
                "buy_count": buy_count,
                "sell_count": sell_count,
                "traders": notable_traders,
            },
        )

    def generate_options_signal(
        self,
        ticker: str,
        call_volume: int,
        put_volume: int,
        put_call_ratio: float,
        unusual_activity: list[dict],
    ) -> Optional[SignalComponent]:
        """Generate signal from options flow.

        Args:
            ticker: Stock ticker
            call_volume: Total call volume
            put_volume: Total put volume
            put_call_ratio: P/C ratio
            unusual_activity: List of unusual options

        Returns:
            Signal component if criteria met
        """
        if not unusual_activity:
            return None

        # Determine direction from P/C ratio
        if put_call_ratio < 0.5:
            direction = SignalDirection.BUY
            strength = min(1.0, (0.7 - put_call_ratio) * 2)
        elif put_call_ratio > 1.2:
            direction = SignalDirection.SELL
            strength = min(1.0, (put_call_ratio - 1.0) * 0.5)
        else:
            return None  # No clear signal

        # Boost for high unusual activity
        unusual_count = len(unusual_activity)
        strength = min(1.0, strength + (unusual_count * 0.05))

        sentiment = "bullish" if direction == SignalDirection.BUY else "bearish"
        details = f"Options flow {sentiment}: P/C ratio {put_call_ratio:.2f}, {unusual_count} unusual contracts"

        return SignalComponent(
            source=SignalType.OPTIONS_FLOW,
            direction=direction,
            strength=strength,
            details=details,
            timestamp=datetime.now(),
            raw_data={
                "call_volume": call_volume,
                "put_volume": put_volume,
                "put_call_ratio": put_call_ratio,
                "unusual_count": unusual_count,
            },
        )

    def aggregate_signals(
        self,
        ticker: str,
        components: list[SignalComponent],
        current_price: Optional[float] = None,
    ) -> Optional[TradingSignal]:
        """Aggregate multiple signal components into a trading signal.

        Args:
            ticker: Stock ticker
            components: List of signal components
            current_price: Current stock price

        Returns:
            Aggregated trading signal or None
        """
        if not components:
            return None

        # Separate by direction
        buy_signals = [c for c in components if c.direction == SignalDirection.BUY]
        sell_signals = [c for c in components if c.direction == SignalDirection.SELL]

        # Calculate weighted scores
        buy_score = sum(c.strength * self.weights.get(c.source, 0.5) for c in buy_signals)
        sell_score = sum(c.strength * self.weights.get(c.source, 0.5) for c in sell_signals)

        # Apply cross-signal bonus
        if len(buy_signals) >= 2:
            buy_score *= self.cross_signal_bonus
        if len(sell_signals) >= 2:
            sell_score *= self.cross_signal_bonus

        # Determine direction
        if buy_score > sell_score and buy_score >= 0.5:
            direction = SignalDirection.BUY
            confidence = min(1.0, buy_score / (buy_score + sell_score + 0.1))
            active_components = buy_signals
        elif sell_score > buy_score and sell_score >= 0.5:
            direction = SignalDirection.SELL
            confidence = min(1.0, sell_score / (buy_score + sell_score + 0.1))
            active_components = sell_signals
        else:
            return None  # No clear signal

        # Determine strength
        if confidence >= 0.8:
            strength = SignalStrength.STRONG
        elif confidence >= 0.6:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        # Determine signal type
        if len(active_components) > 1:
            signal_type = SignalType.COMPOSITE
        else:
            signal_type = active_components[0].source

        # Generate notes
        notes = " | ".join(c.details for c in active_components)

        return TradingSignal(
            ticker=ticker,
            direction=direction,
            confidence=confidence,
            strength=strength,
            signal_type=signal_type,
            components=active_components,
            generated_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=30),
            notes=notes,
            price_at_signal=current_price,
        )

    def score_signal(self, signal: TradingSignal) -> float:
        """Calculate a composite score for ranking signals.

        Args:
            signal: Trading signal

        Returns:
            Score from 0.0 to 100.0
        """
        # Base score from confidence
        score = signal.confidence * 60

        # Bonus for multiple sources
        unique_sources = len(set(c.source for c in signal.components))
        score += unique_sources * 10

        # Bonus for strength
        if signal.strength == SignalStrength.STRONG:
            score += 20
        elif signal.strength == SignalStrength.MODERATE:
            score += 10

        return min(100.0, score)

    def format_signal_for_alert(self, signal: TradingSignal) -> str:
        """Format signal for Telegram/Discord alert.

        Args:
            signal: Trading signal

        Returns:
            Formatted alert message
        """
        emoji = "🟢" if signal.direction == SignalDirection.BUY else "🔴"
        strength_emoji = {"strong": "🔥", "moderate": "⚡", "weak": "💡"}

        msg = f"""
{emoji} **{signal.direction.value.upper()} SIGNAL: ${signal.ticker}**

📊 **Confidence:** {signal.confidence:.0%}
💪 **Strength:** {signal.strength.value.title()} {strength_emoji.get(signal.strength.value, "")}
📈 **Type:** {signal.signal_type.value.replace("_", " ").title()}

**Sources:**
"""
        for comp in signal.components:
            source_emoji = {
                "institutional": "🏦",
                "insider": "👔",
                "congressional": "🏛️",
                "options_flow": "📊",
                "crypto_whale": "🐋",
            }
            msg += f"  {source_emoji.get(comp.source.value, '•')} {comp.details}\n"

        if signal.price_at_signal:
            msg += f"\n💵 **Price at Signal:** ${signal.price_at_signal:.2f}"

        msg += f"\n⏰ **Generated:** {signal.generated_at.strftime('%Y-%m-%d %H:%M')}"

        return msg.strip()
