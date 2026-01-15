# Smart Money Flow Tracker

Track where institutional investors, insiders, and congress members are putting their money — using only **free, publicly available data sources**.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Features

- **Congressional Trading** — Track stock trades by members of Congress (STOCK Act disclosures)
- **Institutional Holdings** — Monitor 13F filings from hedge funds and mutual funds
- **Insider Trading** — Track Form 4 filings for insider buys/sells
- **Options Flow** — Detect unusual options activity and put/call ratios
- **Crypto Whales** — Monitor large Bitcoin and Ethereum transactions
- **Signal Generation** — AI-powered signal aggregation with confidence scoring
- **Telegram Alerts** — Real-time notifications for high-confidence signals
- **Backtesting** — Test historical signal performance

## Screenshots

The dashboard includes 9 pages:
- Dashboard (overview)
- Congressional Trades
- Institutional Holdings
- Insider Trades
- Options Flow
- Crypto Whales
- Signals
- Backtesting
- Settings

## Data Sources (All Free)

| Source | Data | Rate Limit |
|--------|------|------------|
| [SEC EDGAR](https://www.sec.gov/edgar) | 13F holdings, Form 4 insider trades | 10 req/sec |
| [House Stock Watcher](https://housestockwatcher.com) | Congressional trades | Unlimited |
| [Yahoo Finance](https://finance.yahoo.com) | Options chains, stock prices | Unlimited |
| [Blockchain.com](https://blockchain.com) | Bitcoin transactions | 3 req/sec |
| [Etherscan](https://etherscan.io) | Ethereum transactions | 5 req/sec (free API key) |

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/Vamsi-Chanakya/smart_money_flow.git
cd smart_money_flow

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure

```bash
# Copy example config
cp config/settings.yaml.example config/settings.yaml

# Edit with your settings (optional: add Telegram bot token)
```

### 3. Run Dashboard

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Telegram Alerts Setup

1. Message [@BotFather](https://t.me/botfather) on Telegram → `/newbot` → Get your bot token
2. Message your new bot, then visit: `https://api.telegram.org/bot<TOKEN>/getUpdates` to get your chat ID
3. Add to `config/settings.yaml`:

```yaml
notifications:
  telegram:
    enabled: true
    bot_token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"
```

## Automated Data Collection

Run the scheduler for automatic data collection and alerts:

```bash
# Run continuously (7 AM, 6 PM, every 4 hours)
python scripts/scheduler.py

# Run once and exit
python scripts/scheduler.py --once

# Test all collectors
python scripts/scheduler.py --test
```

## Project Structure

```
smart_money_flow/
├── app.py                    # Streamlit dashboard
├── config/
│   └── settings.yaml         # Configuration (git-ignored)
├── scripts/
│   ├── collect_data.py       # Manual data collection
│   └── scheduler.py          # Automated scheduler
├── src/
│   ├── collectors/           # Data fetchers
│   │   ├── sec_edgar.py      # SEC 13F & Form 4
│   │   ├── congressional.py  # Congress trades
│   │   ├── options_flow.py   # Options data
│   │   └── crypto_whales.py  # ETH/BTC whales
│   ├── analyzers/
│   │   ├── signal_engine.py  # Signal generation
│   │   └── backtester.py     # Historical testing
│   ├── storage/
│   │   ├── models.py         # Database models
│   │   └── repository.py     # DB operations
│   └── output/
│       └── alerts.py         # Telegram/Discord
└── data/                     # Local database
```

## Signal Types & Weights

| Signal | Weight | Description |
|--------|--------|-------------|
| Institutional Accumulation | 0.90 | Multiple hedge funds buying same stock |
| Insider Cluster Buy | 0.85 | 3+ insiders buying within 30 days |
| Congressional Trade | 0.60 | Trades by members of Congress |
| Options Flow | 0.50 | Unusual volume vs open interest |
| **Cross-Signal Bonus** | **1.5x** | Multiple signals on same ticker |

## API Reference

### Collectors

```python
from src.collectors import CongressionalCollector, SecEdgarCollector

# Get congressional trades
collector = CongressionalCollector()
trades = collector.get_all_house_trades()

# Get SEC filings
sec = SecEdgarCollector()
holdings = sec.get_13f_holdings("1067983")  # Berkshire CIK
```

### Signal Engine

```python
from src.analyzers import SignalEngine

engine = SignalEngine()
signal = engine.generate_congressional_signal(
    ticker="AAPL",
    trade_count=5,
    buy_count=4,
    sell_count=1,
    notable_traders=["Nancy Pelosi"]
)
```

### Alerts

```python
from src.output import TelegramAlert

alert = TelegramAlert(bot_token="...", chat_id="...")
alert.send_signal(signal)
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This project is for **educational and research purposes only**. It is not financial advice. Always do your own research before making investment decisions. Past performance does not guarantee future results.

## License

MIT License - see [LICENSE](LICENSE) for details.

---

Built with Claude Code
