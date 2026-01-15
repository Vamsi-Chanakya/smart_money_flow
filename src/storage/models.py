"""SQLAlchemy models for Smart Money Flow Tracker."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Institution(Base):
    """Institutional investment managers (hedge funds, mutual funds, etc.)."""

    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    cik: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500))
    file_number: Mapped[Optional[str]] = mapped_column(String(50))
    manager_type: Mapped[Optional[str]] = mapped_column(String(100))  # Hedge Fund, Mutual Fund, etc.

    # Tracking
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    holdings: Mapped[list["InstitutionalHolding"]] = relationship(back_populates="institution")

    def __repr__(self) -> str:
        return f"<Institution(cik={self.cik}, name={self.name})>"


class InstitutionalHolding(Base):
    """13F holdings from institutional investors."""

    __tablename__ = "institutional_holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    report_date: Mapped[datetime] = mapped_column(DateTime, index=True)  # Quarter end date
    filed_date: Mapped[datetime] = mapped_column(DateTime)

    # Security info
    cusip: Mapped[str] = mapped_column(String(9), index=True)
    ticker: Mapped[Optional[str]] = mapped_column(String(10), index=True)
    company_name: Mapped[str] = mapped_column(String(500))
    security_type: Mapped[Optional[str]] = mapped_column(String(50))  # SH, PUT, CALL

    # Position details
    shares: Mapped[int] = mapped_column(Integer)
    value_usd: Mapped[int] = mapped_column(Integer)  # In thousands USD (as reported)
    shares_change: Mapped[Optional[int]] = mapped_column(Integer)  # Change from prior quarter
    shares_change_pct: Mapped[Optional[float]] = mapped_column(Float)
    is_new_position: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sold_out: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    institution: Mapped["Institution"] = relationship(back_populates="holdings")

    __table_args__ = (
        Index("ix_holdings_ticker_date", "ticker", "report_date"),
        Index("ix_holdings_institution_date", "institution_id", "report_date"),
    )

    def __repr__(self) -> str:
        return f"<InstitutionalHolding(ticker={self.ticker}, shares={self.shares})>"


class InsiderTrade(Base):
    """SEC Form 4 insider trading filings."""

    __tablename__ = "insider_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    accession_number: Mapped[str] = mapped_column(String(30), unique=True)
    filed_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    trade_date: Mapped[datetime] = mapped_column(DateTime, index=True)

    # Company info
    issuer_cik: Mapped[str] = mapped_column(String(20), index=True)
    issuer_name: Mapped[str] = mapped_column(String(500))
    ticker: Mapped[Optional[str]] = mapped_column(String(10), index=True)

    # Insider info
    insider_cik: Mapped[str] = mapped_column(String(20))
    insider_name: Mapped[str] = mapped_column(String(500))
    insider_title: Mapped[Optional[str]] = mapped_column(String(200))
    is_director: Mapped[bool] = mapped_column(Boolean, default=False)
    is_officer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ten_percent_owner: Mapped[bool] = mapped_column(Boolean, default=False)

    # Transaction details
    transaction_type: Mapped[str] = mapped_column(String(10))  # P=Purchase, S=Sale, A=Award, etc.
    shares: Mapped[int] = mapped_column(Integer)
    price_per_share: Mapped[Optional[float]] = mapped_column(Float)
    total_value: Mapped[Optional[float]] = mapped_column(Float)
    shares_owned_after: Mapped[Optional[int]] = mapped_column(Integer)

    # Derived
    is_open_market: Mapped[bool] = mapped_column(Boolean, default=False)  # True = more significant

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_insider_ticker_date", "ticker", "trade_date"),
    )

    def __repr__(self) -> str:
        return f"<InsiderTrade(ticker={self.ticker}, insider={self.insider_name}, type={self.transaction_type})>"


class CongressionalTrade(Base):
    """Stock trades by members of Congress (STOCK Act disclosures)."""

    __tablename__ = "congressional_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    disclosure_id: Mapped[str] = mapped_column(String(100), unique=True)

    # Politician info
    representative: Mapped[str] = mapped_column(String(200), index=True)
    chamber: Mapped[str] = mapped_column(String(10))  # House or Senate
    party: Mapped[Optional[str]] = mapped_column(String(20))
    state: Mapped[Optional[str]] = mapped_column(String(5))
    district: Mapped[Optional[str]] = mapped_column(String(10))

    # Trade info
    ticker: Mapped[Optional[str]] = mapped_column(String(10), index=True)
    asset_description: Mapped[str] = mapped_column(String(500))
    asset_type: Mapped[Optional[str]] = mapped_column(String(100))  # Stock, Option, Bond, etc.
    transaction_type: Mapped[str] = mapped_column(String(20))  # Purchase, Sale, Exchange
    trade_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    disclosure_date: Mapped[datetime] = mapped_column(DateTime)

    # Amount (ranges as reported)
    amount_min: Mapped[Optional[int]] = mapped_column(Integer)
    amount_max: Mapped[Optional[int]] = mapped_column(Integer)
    amount_text: Mapped[Optional[str]] = mapped_column(String(100))  # e.g., "$1,001 - $15,000"

    # Owner
    owner: Mapped[Optional[str]] = mapped_column(String(50))  # Self, Spouse, Joint, Child

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_congress_ticker_date", "ticker", "trade_date"),
        Index("ix_congress_rep_date", "representative", "trade_date"),
    )

    def __repr__(self) -> str:
        return f"<CongressionalTrade(rep={self.representative}, ticker={self.ticker})>"


class OptionsFlow(Base):
    """Unusual options activity."""

    __tablename__ = "options_flow"

    id: Mapped[int] = mapped_column(primary_key=True)
    observed_date: Mapped[datetime] = mapped_column(DateTime, index=True)

    # Contract info
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    expiration_date: Mapped[datetime] = mapped_column(DateTime)
    strike_price: Mapped[float] = mapped_column(Float)
    option_type: Mapped[str] = mapped_column(String(4))  # CALL or PUT

    # Volume data
    volume: Mapped[int] = mapped_column(Integer)
    open_interest: Mapped[int] = mapped_column(Integer)
    volume_oi_ratio: Mapped[float] = mapped_column(Float)

    # Price data
    premium: Mapped[Optional[float]] = mapped_column(Float)
    spot_price: Mapped[Optional[float]] = mapped_column(Float)  # Underlying price at time

    # Flags
    is_unusual: Mapped[bool] = mapped_column(Boolean, default=True)
    is_sweep: Mapped[bool] = mapped_column(Boolean, default=False)
    sentiment: Mapped[Optional[str]] = mapped_column(String(10))  # BULLISH, BEARISH, NEUTRAL

    # Source
    source: Mapped[str] = mapped_column(String(50))  # barchart, optionstrat, etc.

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_options_ticker_date", "ticker", "observed_date"),
    )

    def __repr__(self) -> str:
        return f"<OptionsFlow(ticker={self.ticker}, type={self.option_type}, strike={self.strike_price})>"


class Signal(Base):
    """Generated trading signals from analysis."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Signal info
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(500))
    signal_type: Mapped[str] = mapped_column(String(50))  # INSTITUTIONAL, INSIDER, CONGRESS, OPTIONS, COMPOSITE
    direction: Mapped[str] = mapped_column(String(10))  # BUY, SELL

    # Scoring
    confidence_score: Mapped[float] = mapped_column(Float)  # 0.0 to 1.0
    strength: Mapped[str] = mapped_column(String(10))  # WEAK, MODERATE, STRONG

    # Components (JSON-like text for SQLite compatibility)
    contributing_signals: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of signal sources

    # Context
    price_at_signal: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Tracking
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expired_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Performance tracking (filled in later)
    price_after_7d: Mapped[Optional[float]] = mapped_column(Float)
    price_after_30d: Mapped[Optional[float]] = mapped_column(Float)
    return_7d: Mapped[Optional[float]] = mapped_column(Float)
    return_30d: Mapped[Optional[float]] = mapped_column(Float)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_signals_ticker_date", "ticker", "generated_at"),
        Index("ix_signals_active", "is_active", "generated_at"),
    )

    def __repr__(self) -> str:
        return f"<Signal(ticker={self.ticker}, type={self.signal_type}, confidence={self.confidence_score})>"


def init_db(database_url: str) -> None:
    """Initialize the database and create all tables."""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
