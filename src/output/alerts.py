"""Alert system for Smart Money Flow Tracker.

Supports:
- Telegram notifications
- Discord webhooks
- Email (future)
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

from ..analyzers.signal_engine import TradingSignal, SignalDirection, SignalStrength
from ..utils.config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AlertMessage:
    """Structured alert message."""

    title: str
    body: str
    ticker: Optional[str] = None
    signal_type: Optional[str] = None
    priority: str = "normal"  # low, normal, high
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AlertChannel(ABC):
    """Abstract base class for alert channels."""

    @abstractmethod
    def send(self, message: AlertMessage) -> bool:
        """Send an alert message.

        Args:
            message: Alert message to send

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    def send_signal(self, signal: TradingSignal) -> bool:
        """Send a trading signal alert.

        Args:
            signal: Trading signal to send

        Returns:
            True if sent successfully
        """
        pass


class TelegramAlert(AlertChannel):
    """Telegram bot alert channel.

    Setup:
    1. Create a bot via @BotFather on Telegram
    2. Get your bot token
    3. Get your chat ID (message your bot, then check:
       https://api.telegram.org/bot<TOKEN>/getUpdates)
    4. Add to config/settings.yaml
    """

    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or settings.notifications.telegram.bot_token
        self.chat_id = chat_id or settings.notifications.telegram.chat_id
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            logger.warning("Telegram alerts not configured - missing bot_token or chat_id")

    def send(self, message: AlertMessage) -> bool:
        """Send a text message via Telegram."""
        if not self.enabled:
            logger.warning("Telegram not configured")
            return False

        text = self._format_message(message)
        return self._send_message(text)

    def send_signal(self, signal: TradingSignal) -> bool:
        """Send a trading signal via Telegram."""
        if not self.enabled:
            logger.warning("Telegram not configured")
            return False

        text = self._format_signal(signal)
        return self._send_message(text, parse_mode="Markdown")

    def _send_message(self, text: str, parse_mode: str = None) -> bool:
        """Send message to Telegram."""
        url = f"{self.BASE_URL}{self.bot_token}/sendMessage"

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }

        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                logger.info("Telegram message sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {result}")
                return False

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    def _format_message(self, message: AlertMessage) -> str:
        """Format AlertMessage for Telegram."""
        priority_emoji = {
            "high": "🚨",
            "normal": "📢",
            "low": "ℹ️",
        }

        emoji = priority_emoji.get(message.priority, "📢")

        text = f"{emoji} *{message.title}*\n\n{message.body}"

        if message.ticker:
            text += f"\n\n📊 Ticker: ${message.ticker}"

        text += f"\n\n⏰ {message.timestamp.strftime('%Y-%m-%d %H:%M')}"

        return text

    def _format_signal(self, signal: TradingSignal) -> str:
        """Format TradingSignal for Telegram."""
        # Direction emoji
        if signal.direction == SignalDirection.BUY:
            dir_emoji = "🟢"
            action = "BUY"
        else:
            dir_emoji = "🔴"
            action = "SELL"

        # Strength emoji
        strength_emoji = {
            SignalStrength.STRONG: "🔥🔥🔥",
            SignalStrength.MODERATE: "🔥🔥",
            SignalStrength.WEAK: "🔥",
        }
        str_emoji = strength_emoji.get(signal.strength, "")

        # Source emojis
        source_emoji = {
            "institutional": "🏦",
            "insider": "👔",
            "congressional": "🏛️",
            "options_flow": "📊",
            "crypto_whale": "🐋",
            "composite": "⭐",
        }

        text = f"""
{dir_emoji} *{action} SIGNAL: ${signal.ticker}* {str_emoji}

*Confidence:* {signal.confidence:.0%}
*Strength:* {signal.strength.value.title()}
*Type:* {signal.signal_type.value.replace("_", " ").title()}

*Contributing Signals:*
"""

        for comp in signal.components:
            emoji = source_emoji.get(comp.source.value, "•")
            text += f"  {emoji} {comp.details}\n"

        if signal.price_at_signal:
            text += f"\n💵 *Price:* ${signal.price_at_signal:.2f}"

        text += f"\n⏰ {signal.generated_at.strftime('%Y-%m-%d %H:%M')}"

        return text.strip()

    def send_daily_summary(self, signals: list[TradingSignal], stats: dict, trades: list = None) -> bool:
        """Send daily summary message.

        Only sends if there's meaningful data to report (signals, news, or data points).
        """
        if not self.enabled:
            return False

        # Extract counts - support both old and new stat key names
        active_signals = len(signals)
        new_today = stats.get('new_signals', stats.get('signals_generated', 0))
        data_points = stats.get('data_points', stats.get('congressional_trades', 0))

        # Skip if nothing meaningful to report
        if active_signals == 0 and new_today == 0 and data_points == 0:
            logger.info("No meaningful data to report - skipping daily summary")
            return False

        text = f"""
📊 *DAILY SMART MONEY SUMMARY*
{datetime.now().strftime('%Y-%m-%d')}

*Active Signals:* {active_signals}
*New Today:* {new_today}
*Data Points Collected:* {data_points}

"""

        if signals:
            text += "*Top Signals:*\n"
            for sig in signals[:5]:
                emoji = "🟢" if sig.direction == SignalDirection.BUY else "🔴"
                text += f"  {emoji} ${sig.ticker} ({sig.confidence:.0%})\n"

        # Add trade summaries if provided
        if trades:
            text += "\n*Recent Trades:*\n"
            for trade in trades[:10]:  # Limit to 10 to keep message short
                ticker = trade.ticker or "N/A"
                name = trade.representative.split()[-1] if trade.representative else "Unknown"  # Last name only
                tx_type = "Buy" if "purchase" in trade.transaction_type.lower() else "Sell"
                amount = trade.amount_text or ""
                text += f"  • ${ticker} - {name} - {tx_type} - {amount}\n"
        elif not signals:
            text += "_No active signals today_"

        text += "\n_Generated by Smart Money Flow Tracker_"

        return self._send_message(text, parse_mode="Markdown")

    def test_connection(self) -> bool:
        """Test Telegram connection by sending a test message."""
        if not self.enabled:
            logger.error("Telegram not configured")
            return False

        test_msg = AlertMessage(
            title="Connection Test",
            body="Smart Money Flow Tracker is connected! 🎉",
            priority="low",
        )

        return self.send(test_msg)


class DiscordAlert(AlertChannel):
    """Discord webhook alert channel."""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or settings.notifications.discord.webhook_url
        self.enabled = bool(self.webhook_url)

        if not self.enabled:
            logger.warning("Discord alerts not configured - missing webhook_url")

    def send(self, message: AlertMessage) -> bool:
        """Send a message via Discord webhook."""
        if not self.enabled:
            return False

        embed = {
            "title": message.title,
            "description": message.body,
            "timestamp": message.timestamp.isoformat(),
            "color": self._get_color(message.priority),
        }

        if message.ticker:
            embed["fields"] = [{"name": "Ticker", "value": f"${message.ticker}", "inline": True}]

        payload = {"embeds": [embed]}

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=30)
            response.raise_for_status()
            logger.info("Discord message sent successfully")
            return True
        except Exception as e:
            logger.error(f"Error sending Discord message: {e}")
            return False

    def send_signal(self, signal: TradingSignal) -> bool:
        """Send trading signal via Discord."""
        if not self.enabled:
            return False

        # Direction color
        color = 0x00FF00 if signal.direction == SignalDirection.BUY else 0xFF0000

        # Build fields
        fields = [
            {"name": "Direction", "value": signal.direction.value.upper(), "inline": True},
            {"name": "Confidence", "value": f"{signal.confidence:.0%}", "inline": True},
            {"name": "Strength", "value": signal.strength.value.title(), "inline": True},
        ]

        if signal.price_at_signal:
            fields.append({"name": "Price", "value": f"${signal.price_at_signal:.2f}", "inline": True})

        # Add signal sources
        sources_text = "\n".join(f"• {c.details}" for c in signal.components)
        fields.append({"name": "Sources", "value": sources_text, "inline": False})

        embed = {
            "title": f"{'🟢' if signal.direction == SignalDirection.BUY else '🔴'} Signal: ${signal.ticker}",
            "color": color,
            "fields": fields,
            "timestamp": signal.generated_at.isoformat(),
            "footer": {"text": "Smart Money Flow Tracker"},
        }

        payload = {"embeds": [embed]}

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=30)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error sending Discord signal: {e}")
            return False

    def _get_color(self, priority: str) -> int:
        """Get Discord embed color for priority."""
        colors = {
            "high": 0xFF0000,  # Red
            "normal": 0x0099FF,  # Blue
            "low": 0x808080,  # Gray
        }
        return colors.get(priority, 0x0099FF)


class AlertManager:
    """Manages all alert channels."""

    def __init__(self):
        self.channels: list[AlertChannel] = []

        # Initialize enabled channels
        if settings.notifications.telegram.enabled:
            self.channels.append(TelegramAlert())

        if settings.notifications.discord.enabled:
            self.channels.append(DiscordAlert())

    def add_channel(self, channel: AlertChannel):
        """Add an alert channel."""
        self.channels.append(channel)

    def broadcast(self, message: AlertMessage) -> dict[str, bool]:
        """Send message to all channels.

        Returns:
            Dict mapping channel name to success status
        """
        results = {}
        for channel in self.channels:
            channel_name = channel.__class__.__name__
            results[channel_name] = channel.send(message)
        return results

    def broadcast_signal(self, signal: TradingSignal) -> dict[str, bool]:
        """Send signal to all channels."""
        results = {}
        for channel in self.channels:
            channel_name = channel.__class__.__name__
            results[channel_name] = channel.send_signal(signal)
        return results

    def send_alert_if_strong(self, signal: TradingSignal, min_confidence: float = 0.7) -> bool:
        """Only send alert if signal meets threshold.

        Args:
            signal: Trading signal
            min_confidence: Minimum confidence to alert

        Returns:
            True if alert was sent
        """
        if signal.confidence < min_confidence:
            logger.debug(f"Signal for {signal.ticker} below threshold ({signal.confidence:.0%})")
            return False

        results = self.broadcast_signal(signal)
        return any(results.values())
