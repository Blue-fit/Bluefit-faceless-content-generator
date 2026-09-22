"""A failed edit must tell the client which kind of failure it was.

"Something went wrong. Please try again." sent the client round a loop that could
never work when the real cause was depleted credit or a spend cap.
"""

from __future__ import annotations

import pytest

from app.routes import chat


class _GenaiError(Exception):
    """Shaped like google-genai's APIError (carries .code)."""

    def __init__(self, code: int) -> None:
        super().__init__(f"error {code}")
        self.code = code


class _InteractionsError(Exception):
    """Shaped like the Interactions client's error family (carries .status_code)."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"error {status_code}")
        self.status_code = status_code


@pytest.mark.parametrize("exc,expected", [
    (_GenaiError(429), 429),
    (_GenaiError(503), 503),
    (_InteractionsError(500), 500),
    (ValueError("no status here"), None),
])
def test_http_status_reads_both_error_families(exc: Exception, expected: int | None) -> None:
    assert chat._http_status(exc) == expected


def test_quota_is_not_treated_as_retryable() -> None:
    """429 means out of credit: telling the client to retry is a lie."""
    assert 429 not in chat._RETRYABLE
    assert {500, 503} <= chat._RETRYABLE


def test_spend_cap_is_handled_separately_from_unknown_errors() -> None:
    """Hitting the monthly budget used to surface as a generic 'went wrong'."""
    import inspect

    source = inspect.getsource(chat.chat)
    assert "except SpendCapExceeded" in source
    # and it must be caught before the catch-all
    assert source.index("except SpendCapExceeded") < source.index("except Exception")


def test_every_failure_reply_says_the_post_is_untouched() -> None:
    """The client could never tell whether a failed edit had half-applied."""
    import inspect
    import re

    # join adjacent string literals so wrapped messages read as one line
    source = re.sub(r'"\s+"', "", inspect.getsource(chat.chat))
    reassurances = source.count("not changed") + source.count("is unchanged")
    # spend cap, quota, upstream-busy, unknown, ToolError, EditError
    assert reassurances >= 6, f"only {reassurances} failure replies reassure the client"
