import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore


@pytest.fixture
def client():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app
    yield TestClient(app, headers={"X-Owner-Token": "demo-owner-token"})
    set_runtime(None)


# ---------------------------------------------------------------- the zh Business-string helper (wayfinder #65 Wave 7, F28)
#
# A Business read in Chinese must carry the same figures, ids, statuses and days as the English one, in words that are not
# English. `strip_names` removes what is allowed to stay Latin: ids, enum codes, currency, FLOW, and the names the books
# give to facilities and buyers (a buyer's own name stays original). `english_leaks` lists the Business strings that still
# hold a run of three or more ASCII letters after that; `RAW_FIELDS` names the audit-level fields that stay the engine's
# English by design (stability mode: the hash-chained log is not rewritten).

import re as _re
from collections.abc import Iterable as _Iterable
from typing import Any as _Any

_ID = _re.compile(r"[A-Za-z0-9]+(?:[-_:#./][A-Za-z0-9]+)+|[A-Z][A-Z0-9_]{2,}|[0-9a-f]{12,}|/[a-z/]+")
_LATIN_RUN = _re.compile(r"[A-Za-z]{3,}")
_CODE_WORD = _re.compile(r"[a-z]+(?:_[a-z]+)*")  # a lowercase code word ("buyer", "router"), never a sentence


def strip_names(text: str, names: _Iterable[str] = ()) -> str:
    for n in sorted(set(names), key=len, reverse=True):
        if n:
            text = text.replace(n, " ")
    return _ID.sub(" ", text)


def _walk(x: _Any, path: str = ""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(x, list):
        for v in x:
            yield from _walk(v, f"{path}[]")
    elif isinstance(x, str):
        yield path, x


def english_leaks(data: _Any, names: _Iterable[str] = (), raw_fields: _Iterable[str] = ()) -> list[tuple[str, str]]:
    """(path, string) of every Business string left in English: `raw_fields` are regexes over the index-free dotted path
    (".approvals[].reason") of the audit-level fields that stay the engine's English."""
    skip = [_re.compile(p) for p in raw_fields]
    return [(p, s) for p, s in _walk(data)
            if not _CODE_WORD.fullmatch(s) and not any(r.fullmatch(p) for r in skip) and _LATIN_RUN.search(strip_names(s, names))]


_CODE = _re.compile(r"[A-Z][A-Z0-9_:.#-]*|[A-Za-z]+-[\w:.#-]+")


def figures(x: _Any, path: str = "") -> dict[str, _Any]:
    """The figures, ids, statuses and days of a response without its words: every number, boolean and null by path, and every string
    under an id, status, kind or state key that is a code (an upper-case code or an id). Hashes are left out (two runs of one walk
    chain differently). Two languages of one read have one `figures`."""
    out: dict[str, _Any] = {}
    if isinstance(x, dict):
        for k, v in x.items():
            if k.endswith("_hash"):
                continue
            if isinstance(v, str) and (k in ("id", "status", "kind", "tier") or k.endswith(("_id", "_ids", "_status", "_state"))):
                if _CODE.fullmatch(v):
                    out[f"{path}.{k}"] = v
            else:
                out.update(figures(v, f"{path}.{k}"))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            out.update(figures(v, f"{path}[{i}]"))
    elif not isinstance(x, str):
        out[path] = x
    return out


WORD_KEY = _re.compile(r"(_when|_text|headline|title|detail|note|label|what|protects|if_decline|summary_text|after)$")


def unchanged_words(en: _Any, zh: _Any, names: _Iterable[str] = (), raw_fields: _Iterable[str] = ()) -> list[tuple[str, str]]:
    """The `*_when`, `*_text` and headline-like strings the Chinese read left equal to the English one, unless they are figures only
    (no Latin word once names and ids are removed) or an audit-level field named in `raw_fields` (index-free regexes, as `english_leaks`)."""
    skip = [_re.compile(p) for p in raw_fields]
    z = dict(_walk(zh))
    return [(p, s) for p, s in _walk(en)
            if WORD_KEY.search(p) and z.get(p) == s and not any(r.fullmatch(p) for r in skip) and _LATIN_RUN.search(strip_names(s, names))]
