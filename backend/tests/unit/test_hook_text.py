"""The shared hook-text format: splitting and choosing the highlighted word."""

from app.tools.hook_text import pick_highlight, split_hook, strip_pointers

DOWN = "\U0001F447"


def test_split_hook_and_strip_pointers() -> None:
    assert split_hook(f"Kop hier\nLees verder {DOWN}") == ("Kop hier", "Lees verder")
    assert split_hook("Kop hier") == ("Kop hier", "Lees de caption")
    assert strip_pointers(f"Antwoord ↓{DOWN}️") == "Antwoord"


def test_pick_highlight_prefers_numbers_then_longest_content_word() -> None:
    assert pick_highlight("Is natuurlijk eten de 80% regel?") == "80%"
    assert pick_highlight("Is je sociale kring je beste workout?") == "sociale"
    assert pick_highlight("De beste wellness routine gebeurt gewoon doordeweeks.") == "doordeweeks"
    assert pick_highlight("Wie is de?") is None
