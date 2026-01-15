# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Smart Money Flow Tracker - A comprehensive system to track institutional investor movements, insider trading, congressional trades, options flow, and crypto whale activity using free, publicly available data sources to generate investment signals.

## Commands

### Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Dashboard
```bash
streamlit run app.py
```

### Data Collection
```bash
# Collect all data sources
python scripts/collect_data.py

# Collect specific source
python scripts/collect_data.py --source congressional
python scripts/collect_data.py --source sec
```

### Scheduler (Automated Collection)
```bash
# Run scheduler (continuous)
python scripts/scheduler.py

# Run once and exit
python scripts/scheduler.py --once

# Test all collectors
python scripts/scheduler.py --test
```

### Running Tests
```bash
pytest tests/
pytest tests/test_collectors.py -v
```

## Architecture

```
src/
├── collectors/              # Data fetchers
│   ├── sec_edgar.py        # SEC 13F & Form 4 (FREE - data.sec.gov)
│   ├── congressional.py    # Congress trades (FREE - housestockwatcher.com)
│   ├── options_flow.py     # Options data (Yahoo Finance, Barchart)
│   └── crypto_whales.py    # ETH/BTC whale tracking
├── analyzers/               # Signal generation
│   ├── signal_engine.py    # Multi-source signal aggregation
│   └── backtester.py       # Historical performance testing
├── storage/
│   ├── models.py           # SQLAlchemy ORM (6 tables)
│   └── repository.py       # Database operations
├── output/
│   └── alerts.py           # Telegram & Discord notifications
└── utils/
    ├── config.py           # Pydantic settings
    ├── logger.py           # Logging
    └── rate_limiter.py     # API rate limiting
```

## Key Data Sources (All Free)

| Source | API | Rate Limit | Data |
|--------|-----|------------|------|
| SEC EDGAR | data.sec.gov | 10 req/sec | 13F holdings, Form 4 insider trades |
| House Stock Watcher | S3 JSON | ~5 req/sec | Congressional trades |
| Yahoo Finance | yfinance | Unlimited | Options chains, stock prices |
| Blockchain.com | REST API | ~3 req/sec | Bitcoin large transactions |
| Etherscan | API | 5 req/sec | Ethereum whale transactions (needs free API key) |

## Database

SQLite by default (`data/smartmoney.db`). Models:
- `Institution` - Hedge funds, mutual funds
- `InstitutionalHolding` - 13F positions
- `InsiderTrade` - Form 4 filings
- `CongressionalTrade` - STOCK Act disclosures
- `OptionsFlow` - Unusual options activity
- `Signal` - Generated trading signals

## Signal Types & Weights

| Signal | Weight | Description |
|--------|--------|-------------|
| Institutional Accumulation | 0.9 | Multiple 13F filers adding same position |
| Insider Cluster Buy | 0.85 | 3+ insiders buying within 30 days |
| Congressional Trade | 0.6 | Trades by members of Congress |
| Options Flow | 0.5 | Unusual volume relative to open interest |
| Cross-Signal Bonus | 1.5x | Multiple signals converging on same ticker |

## Telegram Setup

1. Create bot via @BotFather on Telegram
2. Get your bot token
3. Message your bot, then get chat ID from: `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Add to `config/settings.yaml`:
```yaml
notifications:
  telegram:
    enabled: true
    bot_token: "your-bot-token"
    chat_id: "your-chat-id"
```

## Configuration

Edit `config/settings.yaml` for:
- Database URL
- API keys (Etherscan, Finnhub)
- Signal weights
- Alert thresholds
- Notification settings

## Dashboard Pages

- **Dashboard** - Overview with quick actions
- **Congressional Trades** - Filter and analyze Congress member trades
- **Institutional Holdings** - 13F lookup by CIK
- **Insider Trades** - Form 4 resources
- **Options Flow** - Put/call ratio analysis
- **Crypto Whales** - BTC/ETH large transaction tracking
- **Signals** - Generated trading signals with alert buttons
- **Backtesting** - Historical signal performance
- **Settings** - Configure Telegram, API keys, weights
