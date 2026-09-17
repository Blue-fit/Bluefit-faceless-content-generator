"""The on-screen hook's text format, shared by prompts and rendering.

A hook is two parts in one string: the headline, a newline, then the caption
call-to-action (the generator ends it with a pointer such as 👇). Images render it
in-picture via the image model; videos overlay it — both need the same split and
the same "which word gets the highlight" choice, so it lives here, dependency-free.
"""

from __future__ import annotations

import re

DEFAULT_CTA = "Lees de caption"
# Pointer glyphs used at the end of the CTA (emoji / arrows / variation selector).
_POINTERS = re.compile(r"[↓⬇\U0001F447️]")
_STOP = {
    "de", "het", "een", "je", "jouw", "jij", "jou", "is", "in", "op", "en", "of", "van",
    "voor", "met", "dan", "wat", "waarom", "hoe", "wie", "niet", "nooit", "ook", "al",
    "the", "a", "an", "is", "your", "why", "how", "what", "who", "not", "and", "or",
}


def strip_pointers(text: str) -> str:
    return _POINTERS.sub("", text).strip()


def split_hook(hook: str) -> tuple[str, str]:
    """`'hook line\\nLees de caption 👇'` -> `('hook line', 'Lees de caption')`.

    The first line is the headline; the rest is the CTA with any pointer stripped.
    A single-line hook gets the default CTA — every post must point at its caption.
    """
    lines = [ln.strip() for ln in hook.split("\n") if ln.strip()]
    if not lines:
        return hook.strip(), DEFAULT_CTA
    headline = strip_pointers(lines[0])
    cta = strip_pointers(" ".join(lines[1:])) if len(lines) > 1 else ""
    return headline, cta or DEFAULT_CTA


def pick_highlight(headline: str) -> str | None:
    """The one word of the headline to put on the highlight pill (casefolded, no punctuation).

    A number or percentage wins ("80%"); otherwise the longest content word. None
    for a headline with nothing worth highlighting.
    """
    words = [w.strip(".,?!:;\"'()") for w in headline.split()]
    words = [w for w in words if w]
    for w in words:
        if any(ch.isdigit() for ch in w):
            return w.casefold()
    content = [w for w in words if w.casefold() not in _STOP and len(w) >= 4]
    if not content:
        return None
    return max(content, key=len).casefold()
