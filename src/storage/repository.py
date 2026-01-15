"""Repository pattern for database operations."""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    Base,
    CongressionalTrade,
    InsiderTrade,
    Institution,
    InstitutionalHolding,
    OptionsFlow,
    Signal,
)


class Repository:
    """Database repository for Smart Money Flow data."""

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    # ==================== Institutions ====================

    def get_or_create_institution(self, session: Session, cik: str, name: str, **kwargs) -> Institution:
        """Get existing institution or create new one."""
        institution = session.query(Institution).filter(Institution.cik == cik).first()
        if not institution:
            institution = Institution(cik=cik, name=name, **kwargs)
            session.add(institution)
            session.flush()
        return institution

    def get_institution_by_cik(self, session: Session, cik: str) -> Optional[Institution]:
        """Get institution by CIK."""
        return session.query(Institution).filter(Institution.cik == cik).first()

    # ==================== Institutional Holdings ====================

    def add_institutional_holding(self, session: Session, holding: InstitutionalHolding) -> None:
        """Add a new institutional holding."""
        session.add(holding)

    def get_holdings_by_ticker(
        self,
        session: Session,
        ticker: str,
        report_date: Optional[datetime] = None,
    ) -> list[InstitutionalHolding]:
        """Get all institutional holdings for a ticker."""
        query = session.query(InstitutionalHolding).filter(InstitutionalHolding.ticker == ticker)
        if report_date:
            query = query.filter(InstitutionalHolding.report_date == report_date)
        return query.order_by(InstitutionalHolding.value_usd.desc()).all()

    def get_top_accumulated_stocks(
        self,
        session: Session,
        report_date: datetime,
        min_buyers: int = 3,
        limit: int = 20,
    ) -> list[dict]:
        """Get stocks with most institutional accumulation."""
        subquery = (
            select(
                InstitutionalHolding.ticker,
                func.count(InstitutionalHolding.id).label("buyer_count"),
                func.sum(InstitutionalHolding.shares_change).label("total_shares_added"),
            )
            .where(
                InstitutionalHolding.report_date == report_date,
                InstitutionalHolding.shares_change > 0,
                InstitutionalHolding.ticker.isnot(None),
            )
            .group_by(InstitutionalHolding.ticker)
            .having(func.count(InstitutionalHolding.id) >= min_buyers)
            .order_by(func.count(InstitutionalHolding.id).desc())
            .limit(limit)
        )

        result = session.execute(subquery)
        return [{"ticker": row.ticker, "buyer_count": row.buyer_count, "shares_added": row.total_shares_added} for row in result]

    # ==================== Insider Trades ====================

    def add_insider_trade(self, session: Session, trade: InsiderTrade) -> None:
        """Add a new insider trade."""
        existing = session.query(InsiderTrade).filter(InsiderTrade.accession_number == trade.accession_number).first()
        if not existing:
            session.add(trade)

    def get_insider_trades_by_ticker(
        self,
        session: Session,
        ticker: str,
        days_back: int = 30,
    ) -> list[InsiderTrade]:
        """Get insider trades for a ticker within the last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        return (
            session.query(InsiderTrade)
            .filter(InsiderTrade.ticker == ticker, InsiderTrade.trade_date >= cutoff)
            .order_by(InsiderTrade.trade_date.desc())
            .all()
        )

    def get_cluster_buys(
        self,
        session: Session,
        days_back: int = 30,
        min_insiders: int = 3,
    ) -> list[dict]:
        """Get stocks with multiple insider buys (cluster buying signal)."""
        cutoff = datetime.utcnow() - timedelta(days=days_back)

        subquery = (
            select(
                InsiderTrade.ticker,
                func.count(func.distinct(InsiderTrade.insider_cik)).label("insider_count"),
                func.sum(InsiderTrade.total_value).label("total_value"),
            )
            .where(
                InsiderTrade.trade_date >= cutoff,
                InsiderTrade.transaction_type == "P",  # Purchases only
                InsiderTrade.is_open_market == True,
                InsiderTrade.ticker.isnot(None),
            )
            .group_by(InsiderTrade.ticker)
            .having(func.count(func.distinct(InsiderTrade.insider_cik)) >= min_insiders)
            .order_by(func.count(func.distinct(InsiderTrade.insider_cik)).desc())
        )

        result = session.execute(subquery)
        return [{"ticker": row.ticker, "insider_count": row.insider_count, "total_value": row.total_value} for row in result]

    # ==================== Congressional Trades ====================

    def add_congressional_trade(self, session: Session, trade: CongressionalTrade) -> None:
        """Add a new congressional trade."""
        existing = session.query(CongressionalTrade).filter(CongressionalTrade.disclosure_id == trade.disclosure_id).first()
        if not existing:
            session.add(trade)

    def get_congressional_trades_by_ticker(
        self,
        session: Session,
        ticker: str,
        days_back: int = 90,
    ) -> list[CongressionalTrade]:
        """Get congressional trades for a ticker."""
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        return (
            session.query(CongressionalTrade)
            .filter(CongressionalTrade.ticker == ticker, CongressionalTrade.trade_date >= cutoff)
            .order_by(CongressionalTrade.trade_date.desc())
            .all()
        )

    def get_recent_congressional_trades(
        self,
        session: Session,
        days_back: int = 30,
        transaction_type: Optional[str] = None,
    ) -> list[CongressionalTrade]:
        """Get recent congressional trades."""
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        query = session.query(CongressionalTrade).filter(CongressionalTrade.trade_date >= cutoff)
        if transaction_type:
            query = query.filter(CongressionalTrade.transaction_type == transaction_type)
        return query.order_by(CongressionalTrade.trade_date.desc()).all()

    # ==================== Options Flow ====================

    def add_options_flow(self, session: Session, flow: OptionsFlow) -> None:
        """Add options flow data."""
        session.add(flow)

    def get_unusual_options_by_ticker(
        self,
        session: Session,
        ticker: str,
        days_back: int = 7,
    ) -> list[OptionsFlow]:
        """Get unusual options activity for a ticker."""
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        return (
            session.query(OptionsFlow)
            .filter(OptionsFlow.ticker == ticker, OptionsFlow.observed_date >= cutoff, OptionsFlow.is_unusual == True)
            .order_by(OptionsFlow.observed_date.desc())
            .all()
        )

    # ==================== Signals ====================

    def add_signal(self, session: Session, signal: Signal) -> None:
        """Add a new signal."""
        session.add(signal)

    def get_active_signals(
        self,
        session: Session,
        min_confidence: float = 0.5,
    ) -> list[Signal]:
        """Get all active signals above confidence threshold."""
        return (
            session.query(Signal)
            .filter(Signal.is_active == True, Signal.confidence_score >= min_confidence)
            .order_by(Signal.confidence_score.desc())
            .all()
        )

    def get_signals_by_ticker(
        self,
        session: Session,
        ticker: str,
        days_back: int = 30,
    ) -> list[Signal]:
        """Get signals for a specific ticker."""
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        return (
            session.query(Signal)
            .filter(Signal.ticker == ticker, Signal.generated_at >= cutoff)
            .order_by(Signal.generated_at.desc())
            .all()
        )
