from datetime import date

from invest_intel.assistant import agent


def test_disclaimer_only_in_the_demo(monkeypatch):
    monkeypatch.setenv("APP_ENV", "demo")
    assert "regulated financial adviser" in agent.system_prompt(date(2026, 1, 1))
    monkeypatch.setenv("APP_ENV", "prod")
    prompt = agent.system_prompt(date(2026, 1, 1))
    assert "regulated financial adviser" not in prompt and "2026-01-01" in prompt
