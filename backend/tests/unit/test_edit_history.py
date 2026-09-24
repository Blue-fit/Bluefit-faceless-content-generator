"""The thread the classifier gets to see.

Without it, an answer to the agent's own question ("de foto") reads as a fresh
vague request and earns the same question back, forever.
"""

from __future__ import annotations

from app.tools.edit_post import _HISTORY_CHARS, _HISTORY_TURNS, ChatTurn, _history_block


def _turns(n: int) -> list[ChatTurn]:
    return [
        ChatTurn(role="user" if i % 2 == 0 else "model", text=f"turn {i}")
        for i in range(n)
    ]


def test_no_history_adds_no_section() -> None:
    """A first message must not carry an empty heading into the prompt."""
    assert _history_block([]) == ""


def test_speakers_are_named_so_the_model_knows_who_asked() -> None:
    block = _history_block(
        [
            ChatTurn(role="model", text="Wat mag anders: de foto of de caption?"),
            ChatTurn(role="user", text="de photo"),
        ]
    )
    assert "YOU: Wat mag anders: de foto of de caption?" in block
    assert "CLIENT: de photo" in block


def test_only_the_tail_is_sent() -> None:
    """Every turn is paid for on each edit, so the thread cannot grow unbounded."""
    block = _history_block(_turns(_HISTORY_TURNS + 4))
    assert block.count("\n") == _HISTORY_TURNS  # heading + N lines
    assert "turn 0" not in block
    assert f"turn {_HISTORY_TURNS + 3}" in block  # the most recent survives


def test_a_long_message_is_clipped() -> None:
    block = _history_block([ChatTurn(role="user", text="x" * (_HISTORY_CHARS + 500))])
    assert "x" * _HISTORY_CHARS in block
    assert "x" * (_HISTORY_CHARS + 1) not in block


def test_the_route_reads_the_thread_before_storing_the_new_message() -> None:
    """Order matters: history is what came BEFORE this instruction, not including it."""
    import inspect

    from app.routes import chat

    source = inspect.getsource(chat.chat)
    assert source.index("get_messages_for_post") < source.index("insert_message")
    assert "history=history" in source
