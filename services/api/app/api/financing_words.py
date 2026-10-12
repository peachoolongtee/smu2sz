"""The three words for an invoice-financing advance, said one way everywhere (map #88, ticket #107; the owner's rule of 12 Oct).

    ARRANGED  the lot exists, its cash has not landed        "Never the word advanced for an unlanded lot"
    RECEIVED  the cash has landed: it is in the account from that day
    REPAID    a receipt cleared the claim
    NONE      no financing (and no word)

`state_of` is the one function that says which, for the net at collection, the rows and every sentence.

The states are never mixed in one sentence. A leaf module (domain imports only) so that the Chinese engine templates, the
presentation helpers and the strategy words can all use the one vocabulary without an import cycle.
"""

from __future__ import annotations

from typing import Literal

from app.domain.models import FundingLot

State = Literal["ARRANGED", "RECEIVED", "REPAID", "NONE"]

_WORD: dict[State, tuple[str, str]] = {
    "NONE": ("", ""),
    "ARRANGED": ("arranged", "已安排"),
    "RECEIVED": ("received", "已到账"),
    "REPAID": ("repaid", "已还清"),
}


def state_of(lot: FundingLot | None, *, repaid: bool = False) -> State:
    """The state of an advance by its lot: not landed -> ARRANGED; landed and still on the lender's books -> RECEIVED; a lot with
    nothing left -> REPAID. With no lot the books keep no trace of a cleared advance, so the caller that read the log says whether
    one was repaid (`repaid`): REPAID then, else NONE (never financed)."""
    if lot is None:
        return "REPAID" if repaid else "NONE"
    if lot.remaining_fen <= 0:
        return "REPAID"
    return "RECEIVED" if lot.settled else "ARRANGED"


def state_word(lang: str, state: State) -> str:
    """The one word for the state ("arranged", "received", "repaid"), in the page's language."""
    en, zh = _WORD[state]
    return zh if lang == "zh" else en


def _distance(day: int, today: int, lang: str) -> str:
    n = day - today
    if n == 0:
        return "今天" if lang == "zh" else "today"
    if n == 1:
        return "明天" if lang == "zh" else "tomorrow"
    if n == -1:
        return "昨天" if lang == "zh" else "yesterday"
    if n > 0:
        return f"{n} 天后" if lang == "zh" else f"in {n} days"
    return f"{-n} 天前" if lang == "zh" else f"{-n} days ago"


def financing_state_words(lang: str, lot: FundingLot | None, today: int, *, repaid: bool = False) -> dict[str, str]:
    """`state`, `word` and `text` for an advance lot as of `today`: "financing arranged, expected in 3 days", "financing received
    29 days ago", "financing repaid". The caller passes the lot it holds (and `repaid` when the log says a cleared advance had none left);
    no financing at all reads as NONE with no words."""
    state = state_of(lot, repaid=repaid)
    word = state_word(lang, state)
    zh = lang == "zh"
    if state == "ARRANGED" and lot is not None:
        text = f"融资{word}，预计{_distance(lot.arrival_day, today, lang)}到账" if zh else (
            f"financing {word}, expected {_distance(lot.arrival_day, today, lang)}")
    elif state == "RECEIVED" and lot is not None:
        text = f"融资{word}（{_distance(lot.arrival_day, today, lang)}）" if zh else (
            f"financing {word} {_distance(lot.arrival_day, today, lang)}")
    elif state == "REPAID":
        text = f"融资{word}" if zh else f"financing {word}"
    else:
        text = ""
    return {"state": state, "word": word, "text": text}


__all__ = ["State", "financing_state_words", "state_of", "state_word"]
