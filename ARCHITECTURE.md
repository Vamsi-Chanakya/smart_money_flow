# Smart Money Flow Tracker - Architecture & Implementation Plan

## Executive Summary

A system to track institutional investor movements, insider trading, congressional trades, and whale activity using **only free, publicly available data sources** to generate investment signals.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SMART MONEY FLOW TRACKER                               │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA COLLECTION LAYER                               │
├─────────────────────┬─────────────────────┬─────────────────────────────────────┤
│                     │                     │                                     │
│  ┌───────────────┐  │  ┌───────────────┐  │  ┌───────────────┐                  │
│  │  SEC EDGAR    │  │  │ CONGRESSIONAL │  │  │    CRYPTO     │                  │
│  │  (FREE API)   │  │  │   TRADING     │  │  │  ON-CHAIN     │                  │
│  ├───────────────┤  │  ├───────────────┤  │  ├───────────────┤                  │
│  │ • 13F Filings │  │  │ • House Stock │  │  │ • Whale Alert │                  │
│  │   (Hedge Fund │  │  │   Watcher API │  │  │ • Arkham Intel│                  │
│  │   Holdings)   │  │  │   (FREE)      │  │  │ • Etherscan   │                  │
│  │ • Form 4      │  │  │ • Senate      │  │  │ • Blockchain  │                  │
│  │   (Insider    │  │  │   Disclosures │  │  │   Explorers   │                  │
│  │   Trading)    │  │  │               │  │  │   (FREE)      │                  │
│  │ • 13D/13G     │  │  │               │  │  │               │                  │
│  │   (Activist)  │  │  │               │  │  │               │                  │
│  └───────┬───────┘  │  └───────┬───────┘  │  └───────┬───────┘                  │
│          │          │          │          │          │                          │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────────────────────────┤
│          │          │          │          │          │                          │
│  ┌───────────────┐  │  ┌───────────────┐  │  ┌───────────────┐                  │
│  │   OPTIONS     │  │  │   ECONOMIC    │  │  │   MARKET      │                  │
│  │   FLOW        │  │  │   DATA        │  │  │   DATA        │                  │
│  ├───────────────┤  │  ├───────────────┤  │  ├───────────────┤                  │
│  │ • Barchart    │  │  │ • FRED API    │  │  │ • Yahoo Fin   │                  │
│  │   (FREE)      │  │  │   (FREE)      │  │  │   (FREE)      │                  │
│  │ • OptionStrat │  │  │ • Fed Reserve │  │  │ • Finnhub     │                  │
│  │   (15m delay) │  │  │   Data        │  │  │   (FREE tier) │                  │
│  │               │  │  │ • Treasury    │  │  │ • Alpha       │                  │
│  │               │  │  │   Data        │  │  │   Vantage     │                  │
│  └───────┬───────┘  │  └───────┬───────┘  │  └───────┬───────┘                  │
│          │          │          │          │          │                          │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA PROCESSING LAYER                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         ETL PIPELINE (Python)                            │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │    │
│  │  │   Extract   │─▶│  Transform  │─▶│   Validate  │─▶│    Load     │     │    │
│  │  │  (Scrapers/ │  │  (Normalize │  │  (Quality   │  │  (Database) │     │    │
│  │  │   APIs)     │  │   & Clean)  │  │   Checks)   │  │             │     │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                      DATA ENRICHMENT                                     │    │
│  │  • Ticker symbol resolution      • Sector/Industry mapping               │    │
│  │  • Company name normalization    • Historical price attachment           │    │
│  │  • Entity deduplication          • Time-series alignment                 │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STORAGE LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐      │
│  │    PostgreSQL       │  │      SQLite         │  │    File Storage     │      │
│  │   (Production)      │  │   (Development)     │  │   (Raw Data Cache)  │      │
│  ├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤      │
│  │ • Institutional     │  │ • Local dev/test    │  │ • JSON responses    │      │
│  │   holdings          │  │ • Single file DB    │  │ • CSV exports       │      │
│  │ • Insider trades    │  │                     │  │ • Parquet files     │      │
│  │ • Congressional     │  │                     │  │                     │      │
│  │   trades            │  │                     │  │                     │      │
│  │ • Whale movements   │  │                     │  │                     │      │
│  │ • Options flow      │  │                     │  │                     │      │
│  │ • Historical prices │  │                     │  │                     │      │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ANALYSIS LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                     SIGNAL GENERATION ENGINE                            │     │
│  │                                                                         │     │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │     │
│  │  │  Institutional   │  │    Insider       │  │  Congressional   │      │     │
│  │  │  Accumulation    │  │    Clustering    │  │  Following       │      │     │
│  │  │  Detection       │  │    Analysis      │  │  Strategy        │      │     │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘      │     │
│  │                                                                         │     │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │     │
│  │  │  Options Flow    │  │   Whale Alert    │  │   Cross-Signal   │      │     │
│  │  │  Sentiment       │  │   Tracker        │  │   Correlation    │      │     │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘      │     │
│  │                                                                         │     │
│  └────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                     SCORING & RANKING                                   │     │
│  │  • Confidence score calculation   • Risk assessment                     │     │
│  │  • Multi-factor ranking           • Position sizing suggestions         │     │
│  │  • Historical accuracy tracking   • Sector exposure analysis            │     │
│  └────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT LAYER                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐      │
│  │    Dashboard        │  │      Reports        │  │      Alerts         │      │
│  │   (Streamlit)       │  │  (PDF/HTML/Email)   │  │  (Discord/Telegram) │      │
│  ├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤      │
│  │ • Live data views   │  │ • Daily summaries   │  │ • Real-time notifs  │      │
│  │ • Interactive       │  │ • Weekly reports    │  │ • Threshold alerts  │      │
│  │   charts            │  │ • Custom exports    │  │ • Pattern triggers  │      │
│  │ • Filtering &       │  │                     │  │                     │      │
│  │   drill-down        │  │                     │  │                     │      │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                          SCHEDULER & ORCHESTRATION                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • Cron jobs / APScheduler for data collection                                   │
│  • Rate limiting handlers for API calls                                          │
│  • Retry logic with exponential backoff                                          │
│  • Health monitoring and logging                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Free Data Sources Summary

### Tier 1: Completely Free (No API Key Required)

| Source | Data Type | Update Frequency | Rate Limit |
|--------|-----------|------------------|------------|
| [SEC EDGAR API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | 13F, Form 4, 13D/13G filings | Real-time | 10 req/sec |
| [FRED API](https://fred.stlouisfed.org/docs/api/fred/) | Economic indicators | Daily | 120 req/min |
| [House Stock Watcher](https://housestockwatcher.com/api) | Congressional trades | Daily | Reasonable use |

### Tier 2: Free Tier with API Key

| Source | Data Type | Free Tier Limits |
|--------|-----------|------------------|
| [Finnhub](https://finnhub.io/docs/api) | Insider trades, company data | 60 calls/min |
| [Alpha Vantage](https://www.alphavantage.co/) | Stock prices, fundamentals | 25 calls/day |
| [Polygon.io](https://polygon.io/) | Market data | 5 calls/min |
| [Etherscan](https://etherscan.io/apis) | Ethereum on-chain data | 5 calls/sec |

### Tier 3: Free with Limitations

| Source | Data Type | Limitations |
|--------|-----------|-------------|
| [Barchart](https://www.barchart.com/options/unusual-activity) | Unusual options activity | Email newsletter, web scraping |
| [OptionStrat](https://optionstrat.com/flow) | Options flow | 15-min delay, 10% of data |
| [Arkham Intelligence](https://platform.arkhamintelligence.com/) | Crypto whale tracking | Web interface, limited API |
| [Yahoo Finance](https://finance.yahoo.com/) | Stock prices, fundamentals | Scraping with `yfinance` |

---

## Implementation Plan

### Phase 1: Foundation (Core Infrastructure)

#### 1.1 Project Setup
```
smartMoneyFlow/
├── src/
│   ├── collectors/          # Data collection modules
│   │   ├── sec_edgar.py
│   │   ├── congressional.py
│   │   ├── options_flow.py
│   │   ├── crypto_whales.py
│   │   └── market_data.py
│   ├── processors/          # Data transformation
│   │   ├── normalizer.py
│   │   ├── enricher.py
│   │   └── validator.py
│   ├── analyzers/           # Signal generation
│   │   ├── institutional.py
│   │   ├── insider.py
│   │   ├── congressional.py
│   │   └── aggregator.py
│   ├── storage/             # Database operations
│   │   ├── models.py
│   │   └── repository.py
│   ├── output/              # Reporting & alerts
│   │   ├── dashboard.py
│   │   ├── reports.py
│   │   └── alerts.py
│   └── utils/               # Shared utilities
│       ├── rate_limiter.py
│       ├── logger.py
│       └── config.py
├── data/                    # Local data storage
│   ├── raw/
│   ├── processed/
│   └── cache/
├── tests/
├── config/
│   └── settings.yaml
├── scripts/
│   └── scheduler.py
├── requirements.txt
├── docker-compose.yml
└── README.md
```

#### 1.2 Core Dependencies
```
# Data Collection
requests
aiohttp
beautifulsoup4
selenium (for JS-heavy sites)

# Data Processing
pandas
numpy
python-dateutil

# Database
sqlalchemy
psycopg2-binary (PostgreSQL)
alembic (migrations)

# Analysis
scikit-learn
ta (technical analysis)

# Output
streamlit
plotly
python-telegram-bot

# Utilities
pydantic
pyyaml
schedule
tenacity (retries)
```

### Phase 2: Data Collectors

#### 2.1 SEC EDGAR Collector
**Purpose:** Track institutional holdings and insider trading

**Key Filings:**
- **13F** - Quarterly institutional holdings (hedge funds, mutual funds managing >$100M)
- **Form 4** - Insider transactions within 2 business days
- **13D/13G** - >5% beneficial ownership (activist investors)
- **Schedule 13F-HR** - Confidential holdings (delayed disclosure)

**Implementation:**
1. Poll SEC EDGAR API daily for new filings
2. Parse XML/HTML filings into structured data
3. Track position changes quarter-over-quarter
4. Flag unusual accumulation patterns

#### 2.2 Congressional Trading Collector
**Purpose:** Track trades by members of Congress

**Data Points:**
- Representative/Senator name
- Transaction date vs. disclosure date (look for patterns)
- Stock ticker, transaction type, amount range
- Committee assignments (for sector correlations)

**Implementation:**
1. Use House Stock Watcher API for House trades
2. Scrape Senate disclosures from efdsearch.senate.gov
3. Cross-reference with committee assignments
4. Calculate historical accuracy per member

#### 2.3 Options Flow Collector
**Purpose:** Detect unusual options activity indicating informed trading

**Signals:**
- High volume relative to open interest
- Large premium bets (>$100K)
- Unusual strike/expiry selection
- Call/put ratio shifts

**Implementation:**
1. Scrape Barchart unusual activity page
2. Use OptionStrat free tier (15-min delayed)
3. Filter for institutional-sized trades
4. Correlate with upcoming events (earnings, FDA, etc.)

#### 2.4 Crypto Whale Tracker
**Purpose:** Monitor large cryptocurrency movements

**Signals:**
- Exchange inflows/outflows
- Whale wallet accumulation
- Stablecoin movements
- Smart money DeFi positions

**Implementation:**
1. Use Etherscan API for Ethereum transactions
2. Integrate Arkham Intelligence web data
3. Monitor known whale addresses
4. Track exchange reserve changes

### Phase 3: Analysis Engine

#### 3.1 Signal Types

| Signal | Description | Weight |
|--------|-------------|--------|
| **Institutional Accumulation** | Multiple 13F filers adding same position | High |
| **Insider Cluster Buying** | Multiple insiders buying within 30 days | High |
| **Congressional Following** | Track high-accuracy congress members | Medium |
| **Options Flow** | Unusual call buying before events | Medium |
| **Whale Accumulation** | Large crypto wallet movements | Medium |
| **Cross-Signal Convergence** | Multiple signals on same ticker | Very High |

#### 3.2 Scoring Algorithm
```
Confidence Score = Σ (signal_weight × signal_strength × recency_factor)

Where:
- signal_weight: Predefined importance (0.1 - 1.0)
- signal_strength: Magnitude of the signal (0.0 - 1.0)
- recency_factor: Decay function based on days since signal
```

#### 3.3 Backtesting Framework
- Replay historical signals against actual price movements
- Calculate win rate, average return, Sharpe ratio
- Optimize signal weights based on historical performance
- Track prediction accuracy over time

### Phase 4: Output & Delivery

#### 4.1 Dashboard (Streamlit)
- **Home:** Today's top signals, recent notable trades
- **Institutional:** 13F changes, top hedge fund positions
- **Insiders:** Recent Form 4 filings, cluster buys
- **Congress:** Member trades, committee correlations
- **Options:** Unusual activity, sentiment indicators
- **Crypto:** Whale movements, exchange flows
- **Backtesting:** Historical signal performance

#### 4.2 Alerts System
- Discord/Telegram webhooks for real-time alerts
- Email digest (daily/weekly summaries)
- Configurable thresholds and filters

### Phase 5: Automation & Monitoring

#### 5.1 Scheduler
```python
# Daily Schedule
06:00 - Collect overnight SEC filings
08:00 - Collect congressional disclosures
09:30 - Market open: Start options flow monitoring
16:00 - Market close: Daily summary generation
18:00 - Collect crypto whale movements
22:00 - Run analysis and generate signals
```

#### 5.2 Monitoring
- API health checks
- Data freshness alerts
- Error tracking (Sentry or similar)
- Rate limit monitoring

---

## Key Signals to Track

### 1. Institutional "Smart Money" Signals
- **13F Clustering:** When 3+ notable funds add same position
- **Conviction Increases:** Existing positions increased by >25%
- **New Positions:** First-time entries by successful managers
- **Activist Involvement:** 13D filings (ownership >5%)

### 2. Insider Trading Signals
- **Cluster Buys:** Multiple insiders buying within 30-day window
- **Open Market Purchases:** Not options exercises or grants
- **Executive Buys:** CEO/CFO purchases (higher signal quality)
- **Unusual Size:** Purchases >$100K or >10% of salary

### 3. Congressional Signals
- **Committee Relevance:** Trades in sectors overseen by member's committee
- **Timing Patterns:** Trades before major legislation or announcements
- **Track Record:** Focus on members with historically high accuracy

### 4. Options Flow Signals
- **Whale Trades:** Single orders >$1M premium
- **Unusual OI:** Volume >5x average open interest
- **Directional Bets:** Heavy call or put activity before events
- **Sweep Orders:** Aggressive buying across multiple exchanges

### 5. Crypto Signals
- **Exchange Withdrawals:** Large amounts leaving exchanges (bullish)
- **Stablecoin Minting:** Fresh USDT/USDC indicating buying power
- **Whale Accumulation:** Known smart money addresses adding positions

---

## Risk Considerations

1. **Data Lag:** Most SEC filings have 45-day+ delays
2. **Survivorship Bias:** Only track current successful investors
3. **Crowded Trades:** Public signals may become less effective
4. **False Positives:** Require confirmation from multiple sources
5. **Market Conditions:** Strategies may not work in all environments

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Signal Win Rate | >55% |
| Average Return per Signal | >5% (30-day) |
| Data Collection Uptime | >99% |
| Alert Latency | <5 minutes |
| False Positive Rate | <30% |

---

## Next Steps

1. **Set up project structure** - Create directories and initial files
2. **Implement SEC EDGAR collector** - Start with 13F and Form 4
3. **Build database schema** - Design tables for all data types
4. **Create basic dashboard** - Streamlit MVP for data visualization
5. **Add congressional data** - House Stock Watcher integration
6. **Implement analysis engine** - Signal generation logic
7. **Set up alerts** - Discord/Telegram notifications
8. **Backtest and refine** - Optimize based on historical data
