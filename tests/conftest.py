import pytest


@pytest.fixture
def mockapikey(monkeypatch):
    return monkeypatch.setenv("OPENAI_API_KEY", "key")
