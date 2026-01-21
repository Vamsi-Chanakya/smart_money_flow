# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Smart Money Flow Tracker - A system to track institutional investor movements, insider trading, congressional trades, options flow, and crypto whale activity using free, publicly available data sources to generate investment signals.

## Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Dashboard
streamlit run app.py

# Data Collection
python scripts/collect_data.py                    # All sources
python scripts/collect_data.py --source congressional

# Watchlist Scanner (stateless, for GitHub Actions)
python scripts/scan_watchlist.py              # Scan all tickers and send alerts
python scripts/scan_watchlist.py --dry-run    # Scan without sending alerts
python scripts/scan_watchlist.py --ticker SMCI # Scan single ticker

# Scheduler
python scripts/scheduler.py          # Continuous (8:30 AM, 12 PM, 5:30 PM)
python scripts/scheduler.py --once   # Run once
python scripts/scheduler.py --test   # Test all collectors

# Tests
pytest tests/                        # All tests
pytest tests/test_collectors.py -v   # Single file
pytest tests/test_collectors.py::test_function -v  # Single test
```

## Architecture

**Data Flow**: Collectors → Repository (SQLite) → SignalEngine → Alerts (Telegram/Discord)

```
src/
├── collectors/           # Data fetchers (each with rate limiting via tenacity)
│   ├── congressional.py  # House Stock Watcher → Unusual Whales fallback → demo data
│   ├── sec_edgar.py      # SEC 13F & Form 4 (data.sec.gov)
│   ├── options_flow.py   # Yahoo Finance (yfinance)
│   ├── crypto_whales.py  # Blockchain.com & Etherscan
│   ├── unusual_whales.py # Premium API (optional)
│   └── market_sentiment.py
├── analyzers/
│   ├── signal_engine.py  # Aggregates signals, applies weights, generates TradingSignal
│   └── backtester.py
├── storage/
│   ├── models.py         # SQLAlchemy ORM: Institution, InstitutionalHolding,
│   │                     #   InsiderTrade, CongressionalTrade, OptionsFlow, Signal
│   └── repository.py     # CRUD operations
├── output/alerts.py      # TelegramAlert, DiscordAlert, AlertMessage
└── utils/
    ├── config.py         # Pydantic Settings with YAML + env var loading
    ├── logger.py
    └── rate_limiter.py
```

## Configuration

**Primary**: `config/settings.yaml` (copy from `settings.yaml.example`)

**Watchlist**: `config/watchlist.yaml` - Tickers to scan with per-ticker event configuration

**Environment Variables** (override YAML, prefix `SMF_`):
```bash
SMF_APIS__FINNHUB__API_KEY=your_key
SMF_APIS__UNUSUAL_WHALES__API_KEY=your_key
SMF_NOTIFICATIONS__TELEGRAM__BOT_TOKEN=your_token
SMF_NOTIFICATIONS__TELEGRAM__CHAT_ID=your_chat_id
```

Nested keys use double underscore: `SMF_APIS__FINNHUB__API_KEY` maps to `apis.finnhub.api_key`

## Testing

Tests use in-memory SQLite (`sqlite:///:memory:`). Key fixtures in `tests/conftest.py`:
- `repository` - In-memory Repository instance
- `db_session` - Database session with automatic cleanup
- `mock_settings` - Settings with test values

## Key Patterns

- **Collectors** return dataclasses (e.g., `CongressTrade`), converted to SQLAlchemy models for storage
- **SignalEngine** generates `SignalComponent`s from each source, then `aggregate_signals()` combines them into a `TradingSignal` with confidence scoring
- **Rate limiting**: Use `RateLimiter` from utils + `tenacity` decorators for retries
- **Config access**: Import `settings` and `watchlist` from `src.utils.config` (global singletons loaded from YAML)
- **Scripts path setup**: Scripts add `sys.path.insert(0, str(Path(__file__).parent.parent))` to import from `src/`

## GitHub Actions

Two workflows in `.github/workflows/`:
- `alerts.yml` - Scheduled alerts (Mon-Fri 8:30 AM, 12 PM, 5:30 PM CST) via `scheduler.py --once`
- `scan-watchlist.yml` - Market open/close scans (9:30 AM, 4 PM ET) via `scan_watchlist.py`

Both use `workflow_dispatch` for manual triggers. Required secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
