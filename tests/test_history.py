from invest_intel import db
from invest_intel.assistant import history

EMAIL = "owner@example.org"


def _capture(monkeypatch, rows=None):
    calls = []

    def fake(sql, params=None):
        calls.append((sql, params))
        return rows if rows is not None else [{"id": 7}]

    monkeypatch.setattr(db, "execute", fake)
    return calls


def test_disabled_in_the_demo(monkeypatch):
    monkeypatch.setenv("APP_ENV", "demo")
    assert not history.enabled()
    monkeypatch.setenv("APP_ENV", "prod")
    assert history.enabled()


def test_every_statement_is_limited_to_the_owner(monkeypatch):
    calls = _capture(monkeypatch, rows=[{"id": 7, "messages": [["user", "hi"]]}])
    history.list_conversations(EMAIL)
    history.load(7, EMAIL)
    history.save(7, EMAIL, [("user", "hi"), ("assistant", "hello")])
    history.save(None, EMAIL, [("user", "hi")])
    history.delete(7, EMAIL)
    history.purge(EMAIL)
    for sql, params in calls:
        assert "%(email)s" in sql and params["email"] == EMAIL
        assert EMAIL not in sql  # bound, never formatted into the SQL


def test_save_updates_then_falls_back_to_insert(monkeypatch):
    calls = _capture(monkeypatch, rows=[])
    monkeypatch.setattr(
        db,
        "execute",
        lambda sql, params=None: calls.append(sql) or ([] if "update" in sql else [{"id": 9}]),
    )
    assert history.save(3, EMAIL, [("user", "hi")]) == 9
    assert "update" in calls[0] and "insert" in calls[1]


def test_load_returns_role_text_pairs(monkeypatch):
    _capture(monkeypatch, rows=[{"messages": [["user", "Q"], ["assistant", "A"]]}])
    assert history.load(1, EMAIL) == [("user", "Q"), ("assistant", "A")]


def test_purge_keeps_twelve_months(monkeypatch):
    calls = _capture(monkeypatch)
    history.purge(EMAIL)
    assert calls[0][1]["months"] == 12


def test_title_is_the_first_question_shortened():
    long = "How " + "much " * 40 + "?"
    title = history._title([("user", long), ("assistant", "A")])
    assert len(title) == history.TITLE_LENGTH and title.endswith("…")
    assert history._title([("user", "  Am I\nahead? ")]) == "Am I ahead?"


def test_api_messages_alternate_and_start_with_the_user():
    chat = [
        ("assistant", "stray"),
        ("user", "Q1"),
        ("assistant", "A1"),
        ("assistant", "more"),
        ("user", "Q2"),
        ("assistant", "A2"),
        ("user", "unanswered"),
    ]
    assert history.api_messages(chat) == [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1\n\nmore"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2"},
    ]
    assert history.api_messages([]) == []
