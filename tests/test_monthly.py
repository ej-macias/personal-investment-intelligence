import logging
from datetime import date
from email import message_from_bytes

import pytest

from invest_intel.insights import monthly

SUMMARY = "## The month in brief\n\nValue up **€1,234** (secret figure)."
ADDRESS = "owner@example.com"


@pytest.fixture
def env(monkeypatch):
    for name, value in {
        "APP_ENV": "prod",
        "SMTP_HOST": "smtp.example.com",
        "SMTP_USER": ADDRESS,
        "SMTP_PASSWORD": "app-password",
        "MAIL_FROM": ADDRESS,
        "MAIL_TO": ADDRESS,
    }.items():
        monkeypatch.setenv(name, value)
    prompts = []

    def answer(messages, **_):
        prompts.append(messages[0]["content"])
        return SUMMARY

    monkeypatch.setattr(monthly.agent, "answer", answer)
    return prompts


class _FakeSMTP:
    instances: list["_FakeSMTP"] = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.sent, self.login_as = host, port, [], None
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        self.login_as = (user, password)

    def send_message(self, message):
        self.sent.append(message)


def test_previous_complete_month():
    assert monthly.previous_month(date(2026, 11, 1)) == (date(2026, 10, 1), date(2026, 10, 31))
    assert monthly.previous_month(date(2026, 1, 15)) == (date(2025, 12, 1), date(2025, 12, 31))
    assert monthly.month_bounds("2024-02") == (date(2024, 2, 1), date(2024, 2, 29))


def test_sends_text_and_html_without_logging_the_content(env, monkeypatch, caplog):
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(monthly.smtplib, "SMTP_SSL", _FakeSMTP)
    caplog.set_level(logging.INFO)

    assert monthly.main(["--month", "2026-10"]) == 0

    (smtp,) = _FakeSMTP.instances
    assert (smtp.host, smtp.port) == ("smtp.example.com", 465)
    assert smtp.login_as == (ADDRESS, "app-password")
    (message,) = smtp.sent
    assert message["Subject"] == "Portfolio summary – October 2026"
    assert message["From"] == message["To"] == ADDRESS
    parts = {part.get_content_type(): part.get_content() for part in message.iter_parts()}
    assert "**€1,234**" in parts["text/plain"]
    assert "<strong>€1,234</strong>" in parts["text/html"]
    assert "2026-10-01" in env[0] and "2026-10-31" in env[0]
    assert "secret figure" not in caplog.text and ADDRESS not in caplog.text
    assert "sent" in caplog.text


def test_failure_logs_only_the_error_type(env, monkeypatch, caplog):
    def refuse(*args, **kwargs):
        raise OSError(f"cannot reach {ADDRESS}")

    monkeypatch.setattr(monthly.smtplib, "SMTP_SSL", refuse)
    assert monthly.main(["--month", "2026-10"]) == 1
    assert "OSError" in caplog.text and ADDRESS not in caplog.text


def test_dry_run_writes_a_file_and_sends_nothing(env, monkeypatch, tmp_path):
    monkeypatch.setattr(monthly.smtplib, "SMTP_SSL", lambda *a, **k: pytest.fail("sent"))
    target = tmp_path / "summary.eml"
    assert monthly.main(["--month", "2026-10", "--dry-run", str(target)]) == 0
    assert message_from_bytes(target.read_bytes())["To"] == ADDRESS


def test_never_runs_on_the_demo(env, monkeypatch):
    monkeypatch.setenv("APP_ENV", "demo")
    assert monthly.main([]) == 2


def test_missing_smtp_server_fails_without_details(env, monkeypatch, caplog):
    monkeypatch.delenv("SMTP_HOST")
    monkeypatch.setattr(monthly.smtplib, "SMTP_SSL", lambda *a, **k: pytest.fail("sent"))
    assert monthly.main(["--month", "2026-10"]) == 1
    assert "RuntimeError" in caplog.text and ADDRESS not in caplog.text
