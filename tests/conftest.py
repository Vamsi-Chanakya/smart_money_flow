import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.utils.config import Settings
from src.storage.repository import Repository
from src.storage.models import Base

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("SMF_DATABASE__URL", "sqlite:///:memory:")
    monkeypatch.setenv("SMF_APIS__FINNHUB__API_KEY", "test_key")
    monkeypatch.setenv("SMF_NOTIFICATIONS__TELEGRAM__ENABLED", "false")

@pytest.fixture
def repository():
    """Create an in-memory database repository for testing."""
    # Use SQLite in-memory database
    repo = Repository("sqlite:///:memory:")
    return repo

@pytest.fixture
def db_session(repository):
    """Get a database session."""
    session = repository.get_session()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def mock_settings():
    """Create mock settings."""
    return Settings(
        database={"url": "sqlite:///:memory:"},
        apis={
            "finnhub": {"api_key": "test", "base_url": "https://test.com"},
            "financial_modeling_prep": {"api_key": "test", "base_url": "https://test.com"}
        },
        notifications={"telegram": {"enabled": False}}
    )
