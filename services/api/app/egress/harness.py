"""Test harness for the security suite and /nl tests: assert that texts leak nothing."""

from __future__ import annotations

from collections.abc import Iterable

from app.egress.protected import ProtectedSet, scan
from app.egress.values import AllowedValue


def assert_no_leak(
    texts: Iterable[str] | str,
    protected: ProtectedSet,
    recipient_id: str,
    allow: Iterable[AllowedValue] = (),
) -> None:
    """Raise AssertionError if any text states a protected value `recipient_id` may not see.

    The message names the text's index and the protected labels only, never the value or the text,
    so a failing test cannot itself print the secret.
    """
    allow = tuple(allow)
    items = [texts] if isinstance(texts, str) else list(texts)
    failures = []
    for i, text in enumerate(items):
        leaks = scan(text, protected, recipient_id=recipient_id, allow=allow)
        if leaks:
            failures.append(f"text #{i}: {sorted({x.label for x in leaks})}")
    if failures:
        raise AssertionError(f"outbound text to {recipient_id} leaked protected values: " + "; ".join(failures))
