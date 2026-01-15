from src.analyzers.signal_engine import SignalEngine, SignalDirection

def test_congressional_signal_generation():
    """Test generating signals from trade counts."""
    engine = SignalEngine()
    
    # Case: Strong Buy (Many buys, no sells, notable trader)
    signal = engine.generate_congressional_signal(
        ticker="AAPL",
        trade_count=5,
        buy_count=5,
        sell_count=0,
        notable_traders=["Nancy Pelosi"]
    )
    
    assert signal is not None
    assert signal.direction == SignalDirection.BUY
    assert signal.strength >= 0.1  # strength is calculated as abs(net) * 0.2 + (0.15 for notable) = 1.15 -> capped at 1.0

def test_congressional_signal_neutral():
    """Test that balanced buying/selling yields minimal or neutral signal."""
    engine = SignalEngine()
    
    # Case: Balanced (2 buys, 2 sells)
    signal = engine.generate_congressional_signal(
        ticker="GOOG",
        trade_count=4,
        buy_count=2,
        sell_count=2,
        notable_traders=[]
    )
    
    # Depending on implementation, might return None or a low-confidence signal
    if signal:
        assert signal.strength < 0.6  # Should be low confidence

def test_signal_aggregation():
    """Test aggregating components into a trading signal."""
    engine = SignalEngine()
    
    # Create a dummy component
    component = engine.generate_congressional_signal(
        ticker="AAPL",
        trade_count=5,
        buy_count=5,
        sell_count=0,
        notable_traders=["Nancy Pelosi"]
    )
    
    # Aggregate
    trading_signal = engine.aggregate_signals("AAPL", [component])
    
    assert trading_signal is not None
    assert trading_signal.confidence > 0.5
    assert trading_signal.direction == SignalDirection.BUY
