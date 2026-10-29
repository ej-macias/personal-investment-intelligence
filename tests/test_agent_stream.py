from types import SimpleNamespace

from invest_intel.assistant import agent


class _FakeStream:
    def __init__(self, chunks, message):
        self.text_stream = iter(chunks)
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


def _client(turns):
    """A client whose streamed requests return `turns` in order and record the requests."""
    calls = []

    def stream(**request):
        calls.append(request)
        return turns.pop(0)

    messages = SimpleNamespace(stream=stream)
    return SimpleNamespace(messages=messages, beta=SimpleNamespace(messages=messages)), calls


def test_text_is_passed_on_as_it_streams_and_tools_still_run(monkeypatch):
    tool_turn = _FakeStream(
        [],
        SimpleNamespace(
            stop_reason="tool_use",
            content=[
                SimpleNamespace(type="tool_use", id="t1", name="get_portfolio_summary", input={})
            ],
        ),
    )
    answer_turn = _FakeStream(
        ["Your portfolio ", "is up 5%."],
        SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="Your portfolio is up 5%.")],
        ),
    )
    client, calls = _client([tool_turn, answer_turn])
    monkeypatch.setattr(agent.anthropic, "Anthropic", lambda: client)
    monkeypatch.setattr(agent, "run_tool", lambda name, args: ('{"ok": true}', False))

    chunks, tools_called = [], []
    messages = [{"role": "user", "content": "How am I doing?"}]
    reply = agent.answer(
        messages, on_tool=lambda n, a: tools_called.append(n), on_text=chunks.append
    )

    assert reply == "Your portfolio is up 5%."
    assert chunks == ["Your portfolio ", "is up 5%."]
    assert tools_called == ["get_portfolio_summary"]
    assert len(calls) == 2 and calls[0]["fallbacks"] == "default"
    assert messages[2]["content"][0]["tool_use_id"] == "t1"
