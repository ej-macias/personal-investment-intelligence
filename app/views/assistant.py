import streamlit as st

from invest_intel import config
from invest_intel.assistant import agent

st.title("AI assistant")
st.caption(
    "Answers come from a fixed set of analytical tools over your portfolio data. Not advice."
)

# `messages` is the full API conversation (including tool calls); `chat` is what is shown.
messages = st.session_state.setdefault("assistant_messages", [])
chat = st.session_state.setdefault("assistant_chat", [])
limit = int(config.env("ASSISTANT_MAX_QUESTIONS_PER_SESSION", "15"))

for role, text in chat:
    st.chat_message(role).markdown(text)

if not chat:
    st.markdown(
        "Try: *How has my portfolio done this year?* · *Am I beating the benchmark?* · "
        "*Where am I most concentrated?*"
    )

asked = sum(1 for role, _ in chat if role == "user")
question = st.chat_input("Ask about your investments", disabled=asked >= limit)
if asked >= limit:
    st.info("Question limit for this session reached. Reload the page to start again.")

if question:
    st.chat_message("user").markdown(question)
    chat.append(("user", question))
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
