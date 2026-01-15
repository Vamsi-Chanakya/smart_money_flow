from unittest.mock import patch, MagicMock
from src.collectors.congressional import CongressionalCollector

def test_congressional_fallback_to_demo():
    """Test that collector falls back to demo data on API failure."""
    collector = CongressionalCollector()
    
    # Mock requests.get to raise an exception
    with patch('requests.Session.get', side_effect=Exception("API Down")):
        trades = collector.get_all_house_trades()
        
        # Should return demo data (which has 10 items)
        assert len(trades) == 10
        assert trades[0].representative == "Nancy Pelosi"

def test_congressional_demo_data_structure():
    """Test proper parsing of demo data."""
    collector = CongressionalCollector()
    trades = collector._get_demo_trades()
    
    assert len(trades) == 10
    trade = trades[0]
    assert trade.ticker is not None
    assert trade.amount_min > 0
    assert trade.transaction_type in ["purchase", "sale"]
