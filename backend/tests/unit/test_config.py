import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_timezone_is_gaza():
    assert Settings().default_timezone == "Asia/Gaza"


def test_invalid_timezone_rejected():
    with pytest.raises(ValidationError):
        Settings(default_timezone="Mars/Olympus")


def test_secrets_are_not_rendered(monkeypatch):
    monkeypatch.setenv("GMI_TWELVEDATA_API_KEY", "super-secret-value")
    s = Settings()
    assert "super-secret-value" not in repr(s)
    assert "super-secret-value" not in s.model_dump_json()
    assert s.twelvedata_api_key is not None
    assert s.twelvedata_api_key.get_secret_value() == "super-secret-value"
