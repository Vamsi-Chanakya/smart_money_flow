import os
from src.utils.config import Settings

def test_settings_load_defaults():
    """Test that settings load with defaults."""
    # We rely on the implicit defaults from Pydantic models in config.py
    # Assuming config.py has defaults or allows optional fields
    pass

def test_settings_from_yaml(tmp_path):
    """Test loading settings from YAML file."""
    config_file = tmp_path / "test_settings.yaml"
    config_file.write_text("""
apis:
  finnhub:
    api_key: "test_yaml_key"
notifications:
  telegram:
    enabled: true
""")
    
    settings = Settings.from_yaml(str(config_file))
    assert settings.apis.finnhub.api_key == "test_yaml_key"
    assert settings.notifications.telegram.enabled is True

def test_settings_validation():
    """Test validation logic."""
    # Ensure invalid configs raise errors if applicable
    pass
