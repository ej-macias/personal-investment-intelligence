import logging

import streamlit as st

from invest_intel import config
from invest_intel.assistant import agent, history
from invest_intel.assistant.limits import DailyCounter, code_matches

log = logging.getLogger(__name__)

st.title("AI assistant")
st.caption(
    "Answers come from a fixed set of analytical tools over your portfolio data. Not advice."
)


@st.cache_resource
def _daily_counter() -> DailyCounter:
    """Shared by every session in this app process, so it resets when the app restarts."""
    limit = config.env("ASSISTANT_DAILY_LIMIT")
    return DailyCounter(int(limit) if limit else None)


# Optional access code, for deployments open to anyone such as the demo.
access_code = config.env("ASSISTANT_ACCESS_CODE")
if access_code and not st.session_state.get("assistant_unlocked"):
    st.info("The assistant is available on request. Enter the access code to use it.")
    given = st.text_input("Access code", type="password")
    if given and code_matches(given, access_code):
        st.session_state["assistant_unlocked"] = True
        st.rerun()
    if given:
        st.error("That code is not valid.")
    st.stop()

# `messages` is the full API conversation (including tool calls); `chat` is what is shown.
messages = st.session_state.setdefault("assistant_messages", [])
chat = st.session_state.setdefault("assistant_chat", [])
limit = int(config.env("ASSISTANT_MAX_QUESTIONS_PER_SESSION", "15"))


def _start(new_chat: list[tuple[str, str]], conversation_id: int | None) -> None:
    """Show another conversation. Its API context is rebuilt only when a question is sent."""
    st.session_state["assistant_chat"] = new_chat
    st.session_state["assistant_messages"] = []
    st.session_state["assistant_conversation_id"] = conversation_id
    st.rerun()


# Saved conversations (private app only): reading them never calls the Anthropic API.
saving = history.enabled()
email = (st.user.get("email") or "").lower() if saving else ""
if saving and email:
    try:
        if not st.session_state.get("assistant_purged"):
            history.purge(email)
            st.session_state["assistant_purged"] = True
        saved = history.list_conversations(email)
    except Exception as exc:  # noqa: BLE001 - history is a convenience; the chat works without it
        saved = None
        log.warning("Conversation history unavailable: %s: %s", type(exc).__name__, exc)
        st.warning(f"Past conversations are unavailable right now ({type(exc).__name__}).")
    if saved is not None:
        with st.expander("Past conversations"):
            if saved:
                labels = {row["id"]: history.label(row) for row in saved}
                chosen = st.selectbox(
                    "Conversation",
                    list(labels),
                    format_func=labels.get,
                    label_visibility="collapsed",
                )
                left, right = st.columns(2)
                if left.button("Open", use_container_width=True):
                    _start(history.load(chosen, email), chosen)
                if right.button("Delete", use_container_width=True):
                    history.delete(chosen, email)
                    if st.session_state.get("assistant_conversation_id") == chosen:
                        _start([], None)
                    st.rerun()
            else:
                st.caption("Conversations are saved here for 12 months.")
            if chat and st.button("New conversation", use_container_width=True):
                _start([], None)

for role, text in chat:
    st.chat_message(role).markdown(text)

if not chat:
    st.markdown(
        "Try: *How has my portfolio done this year?* · *Am I beating the benchmark?* · "
        "*Where am I most concentrated?*"
    )

asked = st.session_state.get("assistant_asked", 0)
question = st.chat_input("Ask about your investments", disabled=asked >= limit)
if asked >= limit:
    st.info("You have reached the question limit for this session.")

if question:
    st.session_state["assistant_asked"] = asked + 1
    if not messages and chat:
        # A reopened conversation, or one interrupted by an error: earlier turns as plain text.
        messages.extend(history.api_messages(chat))
    st.chat_message("user").markdown(question)
    chat.append(("user", question))
    if not _daily_counter().try_acquire():
        reply = "The assistant has reached today's question limit. Try again tomorrow."
        st.chat_message("assistant").markdown(reply)
        chat.append(("assistant", reply))
        st.stop()
    messages.append({"role": "user", "content": question})
    with st.chat_message("assistant"):
        with st.status("Looking at the data…") as status:
            try:
                reply = agent.answer(
                    messages, on_tool=lambda name, args: status.write(f"`{name}` {args or ''}")
                )
            except Exception as exc:  # noqa: BLE001 - keep the page usable whatever the API returns
                reply = f"The assistant is unavailable right now ({type(exc).__name__})."
                del messages[:]  # a half-finished tool exchange cannot be resent
            status.update(label="Done", state="complete")
        st.markdown(reply)
    chat.append(("assistant", reply))
    if saving and email:
        try:
            st.session_state["assistant_conversation_id"] = history.save(
                st.session_state.get("assistant_conversation_id"), email, chat
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Conversation not saved: %s: %s", type(exc).__name__, exc)
            st.caption(f"This conversation could not be saved ({type(exc).__name__}).")
