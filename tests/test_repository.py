from datetime import datetime
from src.storage.models import CongressionalTrade, Institution

def test_create_institution(repository, db_session):
    """Test creating and retrieving an institution."""
    inst = repository.get_or_create_institution(db_session, "12345", "Test Fund")
    assert inst.cik == "12345"
    assert inst.name == "Test Fund"
    
    # Test idempotency (should return existing)
    inst2 = repository.get_or_create_institution(db_session, "12345", "Test Fund")
    assert inst2.id == inst.id

def test_add_congressional_trade(repository, db_session):
    """Test adding and retrieving congressional trades."""
    trade = CongressionalTrade(
        disclosure_id="DOC123",
        representative="Nancy Pelosi",
        chamber="House",
        party="D",
        state="CA",
        district="12",
        ticker="AAPL",
        asset_description="Apple Inc",
        asset_type="Stock",
        transaction_type="purchase",
        trade_date=datetime.now(),
        disclosure_date=datetime.now(),
        amount_min=1000,
        amount_max=15000,
        amount_text="$1,001 - $15,000",
        owner="Self"
    )
    
    repository.add_congressional_trade(db_session, trade)
    db_session.commit()
    
    # Retrieve
    trades = repository.get_congressional_trades_by_ticker(db_session, "AAPL")
    assert len(trades) == 1
    assert trades[0].representative == "Nancy Pelosi"

def test_get_recent_trades(repository, db_session):
    """Test retrieving recent trades."""
    trade1 = CongressionalTrade(
        disclosure_id="DOC1", representative="Rep A", chamber="House", party="D", state="CA", district="1",
        ticker="MSFT", asset_description="Microsoft", asset_type="Stock", transaction_type="purchase",
        trade_date=datetime.now(), disclosure_date=datetime.now(), amount_min=1000, amount_max=15000, amount_text="", owner="Self"
    )
    repository.add_congressional_trade(db_session, trade1)
    db_session.commit()
    
    trades = repository.get_recent_congressional_trades(db_session, days_back=7)
    assert len(trades) == 1
    assert trades[0].ticker == "MSFT"
