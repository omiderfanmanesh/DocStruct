import pytest

from docstruct.config import AgentConfig
from docstruct.infrastructure.llm import factory


def test_agent_config_uses_openai_model_when_provider_is_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("DOCSTRUCT_AGENT_PROVIDER", raising=False)
    monkeypatch.delenv("DOCSTRUCT_AGENT_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")

    config = AgentConfig.from_env()

    assert config.provider == "openai"
    assert config.model == "gpt-4.1"


def test_build_client_requires_openai_api_key(monkeypatch, capsys):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        factory.build_client()

    assert exc_info.value.code == 3
    assert "OPENAI_API_KEY not set" in capsys.readouterr().err


def test_build_client_returns_openai_adapter(monkeypatch):
    class DummyAdapter:
        def __init__(self, *, api_key: str):
            self.api_key = api_key

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(factory, "OpenAIAdapter", DummyAdapter)

    client = factory.build_client()

    assert isinstance(client, DummyAdapter)
    assert client.api_key == "test-key"
