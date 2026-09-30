"""Property tests: a protected value in any surface form, inside any text, is always caught."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.egress import OWNER_ID, ValueKind, renderings, scan
from tests.egress.helpers import golden_set

FORMS = [
    (v.label, v.owner, r)
    for v in golden_set().values
    if v.kind is not ValueKind.TERMS
    for r in renderings(v)
]
NUMERIC_FORMS = [(label, owner, r) for label, owner, r in FORMS if not label.startswith(("counterparty.",))]
RECIPIENTS = ["BUYER-1", "BUYER-2", "BANK-1", "BANK-2", "PLATFORM-1", "LESSOR-1", "FASTCAPITAL"]

# Any text: Latin, CJK (including numerals), digits, punctuation, currency signs, symbols and spaces.
noise = st.text(
    alphabet=st.one_of(
        st.characters(codec="utf-8", categories=["L", "N", "P", "S", "Zs"]),
        st.sampled_from(list("¥元万%xk ,.-十百千零一二三四五六七八九点")),
    ),
    max_size=60,
)


@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(form=st.sampled_from(FORMS), before=noise, after=noise)
def test_an_inserted_protected_value_is_always_caught(form: tuple[str, str | None, str], before: str,
                                                      after: str) -> None:
    label, _, surface = form
    text = f"{before} {surface} {after}"
    assert label in {x.label for x in scan(text, golden_set(), recipient_id="FASTCAPITAL")}


@settings(max_examples=300, deadline=None)
@given(form=st.sampled_from(NUMERIC_FORMS), recipient=st.sampled_from(RECIPIENTS), before=noise, after=noise)
def test_a_value_is_caught_unless_the_recipient_owns_it(form: tuple[str, str | None, str], recipient: str,
                                                        before: str, after: str) -> None:
    label, owner, surface = form
    leaks = {x.label for x in scan(f"{before} {surface} {after}", golden_set(), recipient_id=recipient)}
    if owner != recipient:
        # caught, unless the recipient owns another value with the same canonical form
        owned_twin = any(
            v.owner == recipient and v.label != label and surface in renderings(v) for v in golden_set().values
        )
        assert label in leaks or owned_twin
    else:
        assert label not in leaks


@settings(max_examples=200, deadline=None)
@given(
    words=st.lists(st.text(alphabet=st.characters(codec="ascii", categories=["L"]), min_size=1, max_size=8),
                   max_size=12),
    numbers=st.lists(st.one_of(st.integers(1, 999), st.integers(1900, 2100)), max_size=8),
    unit=st.sampled_from(["", " days", "-day", "天", " rounds", " invoices"]),
)
def test_small_integers_and_years_are_never_protected(words: list[str], numbers: list[int], unit: str) -> None:
    tokens = [*words, *(f"{n}{unit}" for n in numbers)]
    text = " ".join(tokens)
    leaks = scan(text, golden_set(), recipient_id="FASTCAPITAL")
    assert not [x for x in leaks if x.kind is not ValueKind.TEXT], text


@settings(max_examples=100, deadline=None)
@given(form=st.sampled_from(NUMERIC_FORMS), before=noise, after=noise)
def test_the_owner_sees_its_own_state_but_never_a_canary(form: tuple[str, str | None, str], before: str,
                                                         after: str) -> None:
    label, _, surface = form
    leaks = {x.label for x in scan(f"{before} {surface} {after}", golden_set(), recipient_id=OWNER_ID)}
    if label.startswith("canary."):
        assert label in leaks
    else:
        assert label not in leaks
