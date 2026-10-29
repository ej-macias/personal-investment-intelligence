"""The assistant's tool-calling loop on the Claude API.

A manual loop (rather than the SDK tool runner) so the Streamlit page can show each tool
call as it happens and the tool registry stays plain data shared with the tests. Responses
are streamed, so the answer appears as it is written instead of all at once at the end.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import anthropic

from invest_intel import config
from invest_intel.assistant.tools import TOOLS, run_tool

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOOL_ROUNDS = 8
# Models that can be declined by a safety classifier and support the server-side fallback.
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """\
You are the analyst inside a personal investment dashboard. The person asking is the owner \
of the portfolio, reading on a phone, so keep answers short and lead with the number or \
conclusion they asked for.

Everything you know about the portfolio comes from the tools. Call them before stating any \
figure, and say so plainly when the tools cannot answer a question rather than estimating. \
Amounts are in EUR. Returns are fractions (0.07 means 7%) and "cumulative_twr" is the \
time-weighted return, which removes the effect of deposits and withdrawals; total_gain is \
market value minus net invested. "annual_return" is the owner's personal yearly return, \
which does depend on when money was added; call it "your annual return".

When asked for suggestions, start from the owner's plan (get_investment_plan): their goal and \
horizon, the limits that are out of range, and their rules, which you must respect. Be \
specific: name the holdings, give euro amounts, and where it helps express them in months of \
the owner's average money added. Prefer fixing a limit with new money over selling unless \
the rules say otherwise. Statuses starting with "Slightly" are small deviations that need no \
action; mention them only if asked. Judge worldwide funds by where they actually invest \
(an MSCI World fund is mostly North America), not as a single region. Without a plan, \
reason from what the data shows (concentration, costs, performance against the benchmark) \
and mention once that a plan in Airtable would make suggestions specific.{disclaimer}

Today is {today}."""

# Only the public demo, used by strangers, carries the regulatory caveat; the owner knows.
DEMO_DISCLAIMER = """ You are not a regulated financial adviser and do not know the owner's \
full circumstances, so mention that once when you give a suggestion, without repeating it."""


def system_prompt(today: date) -> str:
    disclaimer = DEMO_DISCLAIMER if config.is_demo() else ""
    return SYSTEM_PROMPT.format(today=today.isoformat(), disclaimer=disclaimer)


ToolCallback = Callable[[str, dict[str, Any]], None]
TextCallback = Callable[[str], None]


def _stream(client: anthropic.Anthropic, messages: list[dict[str, Any]]) -> Any:
    """Open a streamed request. Tool inputs here are a few short fields, so they are not
    streamed eagerly; the server keeps validating them against the schema."""
    model = config.env("ASSISTANT_MODEL", DEFAULT_MODEL)
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": 16000,
        "system": system_prompt(date.today()),
        "tools": TOOLS,
        "messages": messages,
        "output_config": {"effort": config.env("ASSISTANT_EFFORT", "medium")},
    }
    if model in FALLBACK_MODELS:
        # A fallback arrives on the same stream: text already received stays valid.
        return client.beta.messages.stream(**request, betas=[FALLBACK_BETA], fallbacks="default")
    return client.messages.stream(**request)


def answer(
    messages: list[dict[str, Any]],
    on_tool: ToolCallback | None = None,
    on_text: TextCallback | None = None,
) -> str:
    """Answer the last user message, appending every turn to `messages` in place.

    `on_text` receives the answer's text as it is generated, `on_tool` each tool call."""
    client = anthropic.Anthropic()
    for _ in range(MAX_TOOL_ROUNDS):
        with _stream(client, messages) as stream:
            for chunk in stream.text_stream:
                if on_text:
                    on_text(chunk)
            response = stream.get_final_message()
        messages.append({"role": "assistant", "content": response.content})
        text = "\n\n".join(b.text for b in response.content if b.type == "text").strip()

        if response.stop_reason == "refusal":
            return "I can't help with that request."
        if response.stop_reason != "tool_use":
            return text or "I couldn't produce an answer."

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if on_tool:
                on_tool(block.name, block.input)
            content, is_error = run_tool(block.name, block.input)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": results})
    return "I needed too many steps to answer that. Try a narrower question."
