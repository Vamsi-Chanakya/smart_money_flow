"""Smart Money Flow Tracker - Enhanced Streamlit Dashboard

Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter
import plotly.express as px
import plotly.graph_objects as go

# Page config
st.set_page_config(
    page_title="Smart Money Flow Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-top: 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
    }
    .bullish {
        color: #00cc00;
        font-weight: bold;
    }
    .bearish {
        color: #ff4444;
        font-weight: bold;
    }
    .signal-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'congressional_trades' not in st.session_state:
        st.session_state.congressional_trades = None
    if 'insider_trades' not in st.session_state:
        st.session_state.insider_trades = []
    if 'institutional_holdings' not in st.session_state:
        st.session_state.institutional_holdings = {}
    if 'options_flow' not in st.session_state:
        st.session_state.options_flow = []
    if 'signals' not in st.session_state:
        st.session_state.signals = []
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None


def main():
    init_session_state()

    # Sidebar
    st.sidebar.title("💰 Smart Money Flow")
    st.sidebar.markdown("Track institutional & insider movements")

    page = st.sidebar.radio(
        "Navigate",
        [
            "🏠 Dashboard",
            "🏛️ Congressional Trades",
            "🏦 Institutional Holdings",
            "👔 Insider Trades",
            "📊 Options Flow",
            "🐋 Crypto Whales",
            "⚡ Signals",
            "📈 Backtesting",
            "⚙️ Settings",
        ]
    )

    # Route to pages
    if page == "🏠 Dashboard":
        show_dashboard()
    elif page == "🏛️ Congressional Trades":
        show_congressional()
    elif page == "🏦 Institutional Holdings":
        show_institutional()
    elif page == "👔 Insider Trades":
        show_insider()
    elif page == "📊 Options Flow":
        show_options_flow()
    elif page == "🐋 Crypto Whales":
        show_crypto_whales()
    elif page == "⚡ Signals":
        show_signals()
    elif page == "📈 Backtesting":
        show_backtesting()
    elif page == "⚙️ Settings":
        show_settings()


def show_dashboard():
    """Main dashboard view."""
    st.markdown('<p class="main-header">Smart Money Flow Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Real-time tracking of institutional & insider money movements</p>', unsafe_allow_html=True)
    st.markdown("---")

    # Quick action buttons
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🔄 Refresh All Data", use_container_width=True):
            refresh_all_data()

    with col2:
        if st.button("⚡ Generate Signals", use_container_width=True):
            generate_signals()

    with col3:
        if st.button("📤 Test Telegram", use_container_width=True):
            test_telegram()

    with col4:
        if st.button("📊 Run Backtest", use_container_width=True):
            st.info("Navigate to Backtesting page")

    st.markdown("---")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        signal_count = len(st.session_state.signals)
        st.metric(label="🎯 Active Signals", value=signal_count)

    with col2:
        if st.session_state.congressional_trades:
            recent = len([t for t in st.session_state.congressional_trades
                         if t.trade_date > datetime.now() - timedelta(days=30)])
            st.metric(label="🏛️ Congress Trades (30d)", value=recent)
        else:
            st.metric(label="🏛️ Congress Trades (30d)", value="--")

    with col3:
        if st.session_state.options_flow:
            bullish = len([o for o in st.session_state.options_flow if o.sentiment == 'BULLISH'])
            bearish = len([o for o in st.session_state.options_flow if o.sentiment == 'BEARISH'])
            st.metric(label="📈 Options Alerts", value=f"{len(st.session_state.options_flow)}", delta=f"{bullish} Bull / {bearish} Bear")
        else:
            st.metric(label="📈 Options Alerts", value="--")

    with col4:
        if st.session_state.last_update:
            st.metric(label="🕐 Last Update", value=st.session_state.last_update.strftime("%H:%M"))
        else:
            st.metric(label="🕐 Last Update", value="Never")

    st.markdown("---")

    # Two column layout for main content
    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("📊 Recent Activity")
        
        tab1, tab2 = st.tabs(["🏛️ Congress", "👔 Insider"])
        
        with tab1:
            if st.session_state.congressional_trades:
                trades = st.session_state.congressional_trades
                recent = sorted(trades, key=lambda x: x.trade_date, reverse=True)[:10]

                data = [{
                    'Date': t.trade_date.strftime('%Y-%m-%d'),
                    'Representative': t.representative[:20],
                    'Party': t.party or 'N/A',
                    'Ticker': t.ticker or 'N/A',
                    'Type': '🟢 Buy' if 'purchase' in t.transaction_type.lower() else '🔴 Sell',
                    'Amount': t.amount_text or 'N/A',
                } for t in recent if t.ticker]

                if data:
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Click 'Refresh All Data' to load recent trades")

        with tab2:
            if st.session_state.insider_trades:
                trades = st.session_state.insider_trades
                recent = sorted(trades, key=lambda x: x.trade_date, reverse=True)[:10]

                data = [{
                    'Date': t.trade_date.strftime('%Y-%m-%d'),
                    'Insider': t.insider_name[:20],
                    'Title': t.insider_title[:15],
                    'Ticker': t.ticker or 'N/A',
                    'Type': '🟢 Buy' if t.transaction_type == 'P' else '🔴 Sell',
                    'Value': f"${int(t.shares * t.price_per_share):,}",
                } for t in recent]

                if data:
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No recent insider trades found or data not loaded")

    with right_col:
        st.subheader("🎯 Top Signals")

        if st.session_state.signals:
            for sig in st.session_state.signals[:5]:
                direction = "🟢" if sig.direction.value == "buy" else "🔴"
                st.markdown(f"""
                **{direction} {sig.ticker}** ({sig.confidence:.0%})
                - Type: {sig.signal_type.value}
                - Strength: {sig.strength.value}
                """)
        else:
            st.info("No signals generated yet")

        st.markdown("---")

        st.subheader("📈 Most Traded by Congress")

        if st.session_state.congressional_trades:
            trades = st.session_state.congressional_trades
            tickers = [t.ticker for t in trades if t.ticker and t.trade_date > datetime.now() - timedelta(days=30)]
            top_tickers = Counter(tickers).most_common(5)

            for ticker, count in top_tickers:
                st.markdown(f"**${ticker}**: {count} trades")
        else:
            st.info("Load data to see stats")


def refresh_all_data():
    """Refresh data from all sources."""
    status_text = st.empty()
    
    # 1. Congressional Data
    status_text.text("Fetching congressional trades...")
    try:
        from src.collectors.congressional import CongressionalCollector
        collector = CongressionalCollector()
        trades = collector.get_all_house_trades()
        st.session_state.congressional_trades = trades
    except Exception as e:
        st.error(f"Error loading congressional data: {e}")
        
    # 2. Insider Data
    status_text.text("Fetching insider trading (Form 4)...")
    try:
        from src.collectors.sec_edgar import SecEdgarCollector
        sec_collector = SecEdgarCollector()
        insider = sec_collector.get_recent_form4_filings(days_back=7)
        st.session_state.insider_trades = insider
    except Exception as e:
        print(f"Error loading insider data: {e}") # Log to console, don't break UI
        st.session_state.insider_trades = []

    # 3. Institutional Data
    status_text.text("Fetching institutional holdings (13F)...")
    try:
        # Note: Full 13F fetch is slow, so we fetch only notable filers here
        # Ideally this would be cached or run in background
        if not st.session_state.institutional_holdings: # Only fetch if empty to save time
             institutional = sec_collector.get_notable_filer_holdings()
             st.session_state.institutional_holdings = institutional
    except Exception as e:
        print(f"Error loading institutional data: {e}")
        st.session_state.institutional_holdings = {}

    # 4. Options Flow (Market Scan)
    status_text.text("Scanning options market (Top 20 active tickers)...")
    progress_bar = st.progress(0)
    
    # Curated list of high-interest tickers to scan
    SCAN_TICKERS = [
        "SPY", "QQQ", "IWM", "AAPL", "NVDA", "TSLA", "AMD", "MSFT", "GOOGL", "AMZN", 
        "META", "NFLX", "COIN", "MARA", "PLTR", "SOFI", "GME", "AMC", "HOOD", "RIVN",
        "EQPT", "BTGO"
    ]
    
    all_options = []
    try:
        from src.collectors.options_flow import OptionsFlowCollector
        opt_collector = OptionsFlowCollector()
        
        # 1. Fetch from Barchart (if working)
        barchart_opts = opt_collector.get_unusual_activity_barchart()
        all_options.extend(barchart_opts)
        
        # 2. explicit scan of top tickers via yfinance
        for i, ticker in enumerate(SCAN_TICKERS):
            try:
                # Update progress
                progress = (i + 1) / len(SCAN_TICKERS)
                progress_bar.progress(progress)
                status_text.text(f"Scanning options: {ticker}...")
                
                # Fetch options
                opts = opt_collector.get_options_chain_yahoo(ticker)
                if opts:
                    all_options.extend(opts)
                    
            except Exception as e:
                print(f"Error scanning {ticker}: {e}")
                
        st.session_state.options_flow = all_options
        
    except Exception as e:
        print(f"Error loading options data: {e}")
        st.session_state.options_flow = []
        
    progress_bar.empty()

    st.session_state.last_update = datetime.now()
    status_text.empty()
    
    # Summary toast
    msg = f"Loaded data: {len(st.session_state.congressional_trades or [])} Congress, " \
          f"{len(st.session_state.insider_trades)} Insider, " \
          f"{len(st.session_state.options_flow)} Options"
    st.success(msg)


def generate_signals():
    """Generate trading signals from collected data."""
    if not st.session_state.congressional_trades and not st.session_state.insider_trades:
        st.warning("Please refresh data first")
        return

    with st.spinner("Generating signals..."):
        try:
            from src.analyzers.signal_engine import SignalEngine, SignalComponent, SignalType, SignalDirection
            from collections import defaultdict

            engine = SignalEngine()
            
            # Helper to normalize tickers
            def analyze_ticker(ticker):
                if not ticker: return None
                
                # 1. Congressional Signal
                cong_signal = None
                if st.session_state.congressional_trades:
                    c_trades = [t for t in st.session_state.congressional_trades 
                               if t.ticker == ticker and t.trade_date > datetime.now() - timedelta(days=90)]
                    if c_trades:
                        buys = len([t for t in c_trades if "purchase" in t.transaction_type.lower()])
                        sells = len([t for t in c_trades if "sale" in t.transaction_type.lower()])
                        traders = list(set(t.representative for t in c_trades))
                        cong_signal = engine.generate_congressional_signal(ticker, len(c_trades), buys, sells, traders)

                # 2. Insider Signal
                insider_signal = None
                if st.session_state.insider_trades:
                    i_trades = [t for t in st.session_state.insider_trades if t.ticker == ticker]
                    if i_trades:
                        # Simple aggregation for signal gen
                        unique_insiders = len(set(t.insider_name for t in i_trades))
                        total_val = sum(t.shares * t.price_per_share for t in i_trades if t.transaction_type == 'P')
                        is_cluster = unique_insiders >= 2
                        insider_signal = engine.generate_insider_signal(
                            ticker, unique_insiders, total_val, is_cluster, 
                            executive_buys=len([t for t in i_trades if t.is_officer and t.transaction_type == 'P'])
                        )

                # 3. Institutional Signal
                inst_signal = None
                # (Simplified - check if held by notable filers)
                # In real app, would need more sophisticated diffing of quarterly changes
                
                # 4. Options Signal
                opt_signal = None
                if st.session_state.options_flow:
                     opts = [o for o in st.session_state.options_flow if o.ticker == ticker]
                     if opts:
                         # Calculate aggregate metrics
                         call_vol = sum(o.volume for o in opts if o.option_type == 'CALL')
                         put_vol = sum(o.volume for o in opts if o.option_type == 'PUT')
                         p_c_ratio = put_vol / call_vol if call_vol > 0 else 1.0
                         opt_signal = engine.generate_options_signal(ticker, call_vol, put_vol, p_c_ratio, [o.__dict__ for o in opts])

                # Combine
                components = []
                if cong_signal: components.append(cong_signal)
                if insider_signal: components.append(insider_signal)
                if inst_signal: components.append(inst_signal)
                if opt_signal: components.append(opt_signal)
                
                return engine.aggregate_signals(ticker, components)

            # Collect all unique tickers from all sources to analyze
            all_tickers = set()
            if st.session_state.congressional_trades:
                all_tickers.update(t.ticker for t in st.session_state.congressional_trades if t.ticker)
            if st.session_state.insider_trades:
                all_tickers.update(t.ticker for t in st.session_state.insider_trades if t.ticker)
            if st.session_state.options_flow:
                all_tickers.update(o.ticker for o in st.session_state.options_flow if o.ticker)

            signals = []
            for ticker in all_tickers:
                sig = analyze_ticker(ticker)
                if sig:
                    signals.append(sig)

            # Sort by confidence
            signals.sort(key=lambda x: x.confidence, reverse=True)
            st.session_state.signals = signals[:50]

            st.success(f"Generated {len(signals)} signals from {len(all_tickers)} tickers analyzed!")

        except Exception as e:
            st.error(f"Error generating signals: {e}")
            import traceback
            traceback.print_exc()


def test_telegram():
    """Test Telegram connection."""
    try:
        from src.output.alerts import TelegramAlert
        alert = TelegramAlert()

        if alert.test_connection():
            st.success("Telegram connected successfully! Check your chat.")
        else:
            st.error("Failed to send test message. Check your settings.")
    except Exception as e:
        st.error(f"Error: {e}")


def show_congressional():
    """Congressional trading view."""
    st.header("🏛️ Congressional Stock Trades")
    st.markdown("Trades by members of Congress (STOCK Act disclosures)")

    col1, col2 = st.columns([3, 1])

    with col2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            refresh_all_data()

    if not st.session_state.congressional_trades:
        st.warning("Click 'Refresh Data' to fetch congressional trades")
        return

    trades = st.session_state.congressional_trades

    # Filters
    st.subheader("Filters")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        days_back = st.slider("Days back", 7, 365, 30)

    with col2:
        trade_type = st.selectbox("Trade Type", ["All", "Purchase", "Sale"])

    with col3:
        parties = ["All"] + list(set(t.party for t in trades if t.party))
        party_filter = st.selectbox("Party", parties)

    with col4:
        ticker_filter = st.text_input("Ticker").upper()

    # Filter trades
    cutoff = datetime.now() - timedelta(days=days_back)
    filtered = [t for t in trades if t.trade_date >= cutoff]

    if trade_type == "Purchase":
        filtered = [t for t in filtered if "purchase" in t.transaction_type.lower()]
    elif trade_type == "Sale":
        filtered = [t for t in filtered if "sale" in t.transaction_type.lower()]

    if party_filter != "All":
        filtered = [t for t in filtered if t.party == party_filter]

    if ticker_filter:
        filtered = [t for t in filtered if t.ticker and t.ticker.upper() == ticker_filter]

    st.markdown(f"**Showing {len(filtered)} trades**")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Most Traded Tickers")
        ticker_counts = Counter(t.ticker for t in filtered if t.ticker)
        top_tickers = ticker_counts.most_common(15)

        if top_tickers:
            fig = px.bar(
                x=[t[0] for t in top_tickers],
                y=[t[1] for t in top_tickers],
                labels={'x': 'Ticker', 'y': 'Trade Count'},
                color=[t[1] for t in top_tickers],
                color_continuous_scale='Blues',
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Buy vs Sell Activity")
        buys = len([t for t in filtered if "purchase" in t.transaction_type.lower()])
        sells = len([t for t in filtered if "sale" in t.transaction_type.lower()])

        fig = px.pie(
            values=[buys, sells],
            names=['Purchases', 'Sales'],
            color_discrete_sequence=['#00cc00', '#ff4444'],
        )
        st.plotly_chart(fig, use_container_width=True)

    # Data table
    st.subheader("Trade Details")

    data = [{
        'Date': t.trade_date.strftime('%Y-%m-%d'),
        'Disclosed': t.disclosure_date.strftime('%Y-%m-%d'),
        'Representative': t.representative,
        'Party': t.party or 'N/A',
        'State': t.state or 'N/A',
        'Ticker': t.ticker or 'N/A',
        'Type': t.transaction_type,
        'Amount': t.amount_text or 'N/A',
    } for t in sorted(filtered, key=lambda x: x.trade_date, reverse=True)]

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Download
    csv = df.to_csv(index=False)
    st.download_button("📥 Download CSV", csv, "congressional_trades.csv", "text/csv")


def show_institutional():
    """Institutional holdings view."""
    st.header("🏦 Institutional Holdings (13F Filings)")

    st.info("""
    **Notable Investors Tracked:**
    - Berkshire Hathaway (Warren Buffett) - CIK: 1067983
    - Bridgewater Associates (Ray Dalio) - CIK: 1336528
    - Scion Asset Management (Michael Burry) - CIK: 1697748
    - Pershing Square (Bill Ackman) - CIK: 1591086

    Note: Q4 2025 filings due February 17, 2026
    """)

    # CIK lookup
    st.subheader("Lookup Institution")

    col1, col2 = st.columns([3, 1])
    with col1:
        cik = st.text_input("Enter CIK number", placeholder="e.g., 1067983 for Berkshire")

    with col2:
        st.write("")
        st.write("")
        fetch_btn = st.button("🔍 Fetch", use_container_width=True)

    if fetch_btn and cik:
        with st.spinner("Fetching from SEC EDGAR..."):
            try:
                from src.collectors.sec_edgar import SecEdgarCollector
                collector = SecEdgarCollector()
                submissions = collector.get_company_submissions(cik)

                st.success(f"**{submissions.get('name', 'Unknown')}**")

                filings = submissions.get("filings", {}).get("recent", {})
                forms = filings.get("form", [])[:20]
                dates = filings.get("filingDate", [])[:20]

                st.write("**Recent Filings:**")
                filing_data = [{"Form": f, "Date": d} for f, d in zip(forms, dates)]
                st.dataframe(pd.DataFrame(filing_data), hide_index=True)

            except Exception as e:
                st.error(f"Error: {e}")


def show_insider():
    """Insider trading view."""
    st.header("👔 Insider Trading (Form 4)")

    st.markdown("""
    **What to look for:**
    - **Cluster Buys**: Multiple insiders buying within 30 days
    - **Open Market Purchases**: More significant than option exercises
    - **Executive Buys**: CEO/CFO purchases signal confidence
    """)

    st.subheader("External Resources")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Free Data Sources:**
        - [OpenInsider - Cluster Buys](http://openinsider.com/latest-cluster-buys)
        - [OpenInsider - Latest Purchases](http://openinsider.com/insider-purchases)
        - [SEC EDGAR Form 4](https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4)
        """)

    with col2:
        st.markdown("""
        **Key Metrics:**
        - Multiple insiders buying = Strong signal
        - Purchases > $100K = High conviction
        - Open market (not options) = More meaningful
        """)

    st.markdown("---")
    
    if st.session_state.insider_trades:
        st.subheader("📝 Recent Insider Filings")
        
        data = [{
            'Date': t.trade_date.strftime('%Y-%m-%d'),
            'Ticker': t.ticker,
            'Insider': t.insider_name,
            'Title': t.insider_title,
            'Type': 'Buy' if t.transaction_type == 'P' else 'Sell',
            'Shares': f"{t.shares:,}",
            'Price': f"${t.price_per_share:.2f}",
            'Value': f"${int(t.shares * t.price_per_share):,}",
            'Owned': f"{t.shares_owned_after:,}",
        } for t in st.session_state.insider_trades]
        
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("No recent insider data loaded. Click 'Refresh All Data' on Dashboard.")


def show_options_flow():
    """Options flow view."""
    st.header("📊 Options Flow Analysis")

    col1, col2 = st.columns([3, 1])

    with col1:
        ticker = st.text_input("Enter ticker to analyze", placeholder="e.g., AAPL, TSLA")

    with col2:
        st.write("")
        st.write("")
        analyze_btn = st.button("🔍 Analyze", use_container_width=True)

    if analyze_btn and ticker:
        with st.spinner(f"Analyzing options for {ticker.upper()}..."):
            try:
                from src.collectors.options_flow import OptionsFlowCollector
                collector = OptionsFlowCollector()

                # Get put/call ratio
                pc_data = collector.calculate_put_call_ratio(ticker.upper())

                if pc_data:
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("Call Volume", f"{pc_data['call_volume']:,}")
                    with col2:
                        st.metric("Put Volume", f"{pc_data['put_volume']:,}")
                    with col3:
                        sentiment_color = "🟢" if pc_data['sentiment'] == "BULLISH" else "🔴" if pc_data['sentiment'] == "BEARISH" else "⚪"
                        st.metric("P/C Ratio", f"{pc_data['put_call_ratio']:.2f} {sentiment_color}")

                    st.markdown(f"**Sentiment:** {pc_data['sentiment']}")

                    # Get unusual options
                    options = collector.get_options_chain_yahoo(ticker.upper())

                    if options:
                        st.subheader("Unusual Options Activity")

                        data = [{
                            'Type': o.option_type,
                            'Strike': f"${o.strike_price:.2f}",
                            'Expiry': o.expiration_date.strftime('%Y-%m-%d'),
                            'Volume': o.volume,
                            'OI': o.open_interest,
                            'Vol/OI': f"{o.volume_oi_ratio:.1f}x",
                            'Sentiment': o.sentiment,
                        } for o in options[:10]]

                        st.dataframe(pd.DataFrame(data), hide_index=True)
                else:
                    st.warning("Could not fetch options data")

            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")

    if st.session_state.options_flow:
        st.subheader("🔥 Top Unusual Activity (Market Wide)")
        
        data = [{
            'Ticker': o.ticker,
            'Type': o.option_type,
            'Vol/OI': f"{o.volume_oi_ratio:.1f}x",
            'Volume': f"{o.volume:,}",
            'OI': f"{o.open_interest:,}",
            'Sentiment': o.sentiment,
        } for o in st.session_state.options_flow[:20]]
        
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("Refresh data to see market-wide unusual activity")

    st.markdown("---")
    st.markdown("""
    **Interpretation Guide:**
    - P/C Ratio < 0.7 = Bullish (more calls)
    - P/C Ratio > 1.0 = Bearish (more puts)
    - Vol/OI > 5x = Unusual activity
    """)


def show_crypto_whales():
    """Crypto whale tracking view."""
    st.header("🐋 Crypto Whale Tracker")

    st.info("""
    Track large cryptocurrency movements on Ethereum and Bitcoin.
    Requires Etherscan API key for full functionality.
    """)

    tab1, tab2 = st.tabs(["Ethereum", "Bitcoin"])

    with tab1:
        st.subheader("Ethereum Whale Movements")

        if st.button("🔍 Fetch ETH Whales"):
            with st.spinner("Fetching whale transactions..."):
                try:
                    from src.collectors.crypto_whales import CryptoWhaleCollector
                    collector = CryptoWhaleCollector()

                    # This will show limited data without API key
                    st.warning("Configure Etherscan API key in settings for full data")

                except Exception as e:
                    st.error(f"Error: {e}")

    with tab2:
        st.subheader("Bitcoin Large Transactions")

        if st.button("🔍 Fetch BTC Whales"):
            with st.spinner("Fetching large BTC transactions..."):
                try:
                    from src.collectors.crypto_whales import BitcoinWhaleCollector
                    collector = BitcoinWhaleCollector()
                    txs = collector.get_large_transactions(min_btc=100)

                    if txs:
                        data = [{
                            'Hash': tx['hash'][:16] + '...',
                            'Value (BTC)': f"{tx['value_btc']:,.2f}",
                            'Time': tx['time'].strftime('%Y-%m-%d %H:%M'),
                            'Inputs': tx['inputs'],
                            'Outputs': tx['outputs'],
                        } for tx in txs[:15]]

                        st.dataframe(pd.DataFrame(data), hide_index=True)
                    else:
                        st.info("No large transactions found")

                except Exception as e:
                    st.error(f"Error: {e}")


def show_signals():
    """Trading signals view."""
    st.header("⚡ Smart Money Signals")

    col1, col2 = st.columns([3, 1])

    with col2:
        if st.button("🔄 Generate Signals", use_container_width=True):
            generate_signals()

    if not st.session_state.signals:
        st.info("Click 'Generate Signals' to analyze data and create signals")
        return

    signals = st.session_state.signals

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    buy_signals = [s for s in signals if s.direction.value == "buy"]
    sell_signals = [s for s in signals if s.direction.value == "sell"]

    with col1:
        st.metric("Total Signals", len(signals))
    with col2:
        st.metric("Buy Signals", len(buy_signals))
    with col3:
        st.metric("Sell Signals", len(sell_signals))
    with col4:
        avg_conf = sum(s.confidence for s in signals) / len(signals) if signals else 0
        st.metric("Avg Confidence", f"{avg_conf:.0%}")

    st.markdown("---")

    # Signal cards
    for signal in signals:
        direction_emoji = "🟢" if signal.direction.value == "buy" else "🔴"
        strength_emoji = "🔥🔥🔥" if signal.strength.value == "strong" else "🔥🔥" if signal.strength.value == "moderate" else "🔥"

        with st.container():
            col1, col2, col3 = st.columns([1, 2, 1])

            with col1:
                st.markdown(f"### {direction_emoji} ${signal.ticker}")
                st.markdown(f"**{signal.direction.value.upper()}** {strength_emoji}")

            with col2:
                st.markdown(f"**Confidence:** {signal.confidence:.0%}")
                st.markdown(f"**Type:** {signal.signal_type.value}")
                st.markdown(f"_{signal.notes}_")

            with col3:
                st.markdown(f"**Generated:** {signal.generated_at.strftime('%Y-%m-%d')}")

                if st.button(f"📤 Alert", key=f"alert_{signal.ticker}"):
                    try:
                        from src.output.alerts import TelegramAlert
                        alert = TelegramAlert()
                        if alert.send_signal(signal):
                            st.success("Sent!")
                        else:
                            st.error("Failed")
                    except Exception as e:
                        st.error(str(e))

            st.markdown("---")


def show_backtesting():
    """Backtesting view."""
    st.header("📈 Signal Backtesting")

    st.markdown("""
    Test historical signal performance against actual price movements.
    """)

    if not st.session_state.signals:
        st.warning("Generate signals first to run backtests")
        return

    signals = st.session_state.signals

    st.markdown(f"**{len(signals)} signals available for backtesting**")

    if st.button("🚀 Run Backtest"):
        with st.spinner("Running backtest..."):
            try:
                from src.analyzers.backtester import Backtester

                backtester = Backtester()
                results = backtester.backtest_signals(signals[:10])  # Limit for speed

                if results:
                    summary = backtester.generate_summary(results)

                    # Display summary
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Win Rate", f"{summary.win_rate:.1%}")
                    with col2:
                        st.metric("Avg 30d Return", f"{summary.avg_return_30d:+.1%}")
                    with col3:
                        st.metric("Best Return", f"{summary.best_return:+.1%}")
                    with col4:
                        st.metric("Worst Return", f"{summary.worst_return:+.1%}")

                    # Results table
                    st.subheader("Individual Results")

                    data = [{
                        'Ticker': r.ticker,
                        'Direction': r.signal_direction.value,
                        'Confidence': f"{r.signal_confidence:.0%}",
                        '7d Return': f"{r.return_7d:+.1%}" if r.return_7d else "N/A",
                        '30d Return': f"{r.return_30d:+.1%}" if r.return_30d else "N/A",
                        'Winner': "✅" if r.is_winner else "❌" if r.is_winner is False else "?",
                    } for r in results]

                    st.dataframe(pd.DataFrame(data), hide_index=True)

                else:
                    st.warning("No results - signals may be too recent")

            except Exception as e:
                st.error(f"Error running backtest: {e}")


def show_settings():
    """Settings view."""
    st.header("⚙️ Settings")

    st.subheader("Telegram Alerts")

    bot_token = st.text_input("Bot Token", type="password", help="Get from @BotFather on Telegram")
    chat_id = st.text_input("Chat ID", help="Your Telegram chat ID")

    if st.button("💾 Save & Test Telegram"):
        if bot_token and chat_id:
            try:
                from src.output.alerts import TelegramAlert
                alert = TelegramAlert(bot_token=bot_token, chat_id=chat_id)

                if alert.test_connection():
                    st.success("Connected! Check your Telegram.")

                    # Save to config (in production, use proper config management)
                    st.info("Add these to config/settings.yaml to persist")
                else:
                    st.error("Failed to connect")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.warning("Enter both bot token and chat ID")

    st.markdown("---")

    st.subheader("API Keys")

    etherscan_key = st.text_input("Etherscan API Key", type="password", help="For crypto whale tracking")
    finnhub_key = st.text_input("Finnhub API Key", type="password", help="For additional market data")

    st.markdown("---")

    st.subheader("Signal Settings")

    col1, col2 = st.columns(2)

    with col1:
        st.slider("Min Confidence for Alerts", 0.0, 1.0, 0.7)
        st.slider("Institutional Weight", 0.0, 1.0, 0.9)
        st.slider("Insider Weight", 0.0, 1.0, 0.85)

    with col2:
        st.slider("Congressional Weight", 0.0, 1.0, 0.6)
        st.slider("Options Flow Weight", 0.0, 1.0, 0.5)
        st.slider("Cross-Signal Bonus", 1.0, 2.0, 1.5)


if __name__ == "__main__":
    main()
