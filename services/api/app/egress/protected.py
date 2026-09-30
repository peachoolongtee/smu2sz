"""The protected set (everything that must never leave in text) and the deterministic scanner.

`ProtectedSet.build(state, mandate)` collects the mandate, facility, balance, counterparty-terms and
concession values of the supplier's verified state, lender and buyer names, and the canaries.
Reservation values of buyers are passed in by the caller as `extra_private` (this package never
imports the hidden buyer profiles).

`scan(text, protected, recipient_id=..., allow=...)` normalises the text once, tokenises every
number and looks each canonical token up in precomputed indexes. A match is a leak unless the
recipient is entitled to a value with that same canonical form (it owns it) or the message's
`allow` list covers it. Canaries always leak.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from fractions import Fraction

from pydantic import BaseModel, ConfigDict

from app.domain.models import Counterparty, FinancialState, Mandate
from app.egress.canaries import Canary, load_canaries
from app.egress.normalise import day_counts, fold, sentences, squash, tokens
from app.egress.normalise import normalise as _normalise
from app.egress.values import (
    OWNER_ID,
    AllowedValue,
    Category,
    PrivateValue,
    ValueKind,
    canary_squash,
    money_bare_ok,
    money_key,
    rate_keys,
    ratio_key,
    terms_alias_key,
    text_key,
)

_NAME_SUFFIXES = re.compile(
    r"[\s,]*(?:co\.?,?\s*ltd\.?|co\.?|ltd\.?|limited|inc\.?|llc|corp\.?|company|有限公司|公司)\s*$",
    re.IGNORECASE,
)
_ROLE_ID = re.compile(r"^(BUYER|SUPPLIER|LENDER)-(\d{1,2})$")
_MIN_CANARY_SQUASH = 8


def counterparty_aliases(cp: Counterparty) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(name aliases, extra terms-context aliases) for a counterparty.

    Name aliases are the registered name, the name without its company suffix (if still two words
    or more) and the id. Terms-context aliases add role forms such as "Buyer B" / "Buyer 2" / "买方B",
    which only count when they sit in the same sentence as a protected day count. The letters A and
    I are skipped in English forms because "the buyer a ..." is ordinary English.
    """
    names = [cp.name]
    core = _NAME_SUFFIXES.sub("", cp.name).strip()
    if core and core != cp.name and (len(core.split()) >= 2 or not core.isascii()):
        names.append(core)
    names.append(cp.id)
    extra: list[str] = []
    m = _ROLE_ID.match(cp.id)
    if m and 1 <= int(m.group(2)) <= 26:
        role, n = m.group(1).lower(), int(m.group(2))
        letter = chr(ord("a") + n - 1)
        extra += [f"{role} {n}", f"{role} #{n}"]
        if letter not in ("a", "i"):
            extra += [f"{role} {letter}", f"{role}-{letter}"]
        if role == "buyer":
            extra += [f"买方{letter}", f"客户{letter}", f"买方{n}", f"客户{n}"]
            if letter not in ("a", "i"):
                extra.append(f"customer {letter}")
    return tuple(names), tuple(extra)


def _all_in_rate(rate_bp: int, fee_bp: int, fee_period_days: int | None) -> Fraction | None:
    if not fee_bp or not fee_period_days:
        return None
    return Fraction(rate_bp, 10_000) + Fraction(fee_bp, 10_000) * Fraction(365, fee_period_days)


class Leak(BaseModel):
    """One protected value found in outbound text. Labels only: the value itself is never carried."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    label: str
    kind: ValueKind
    category: Category
    owner: str | None


class ProtectedSet:
    """An immutable, indexed set of protected values. Build once per state/mandate version."""

    __slots__ = (
        "_canary_tokens",
        "_money_bare",
        "_money_marked",
        "_rate_frac",
        "_rate_pct",
        "_ratio",
        "_terms",
        "_text",
        "_text_re",
        "_values",
    )

    def __init__(self, values: Iterable[PrivateValue]) -> None:
        vals = tuple(values)
        labels = [v.label for v in vals]
        if len(set(labels)) != len(labels):
            dup = sorted({x for x in labels if labels.count(x) > 1})
            raise ValueError(f"duplicate protected labels: {dup}")
        self._values = vals
        self._rate_pct: dict[str, list[PrivateValue]] = {}
        self._rate_frac: dict[str, list[PrivateValue]] = {}
        self._ratio: dict[str, list[PrivateValue]] = {}
        self._money_marked: dict[str, list[PrivateValue]] = {}
        self._money_bare: dict[str, list[PrivateValue]] = {}
        self._terms: list[tuple[PrivateValue, re.Pattern[str]]] = []
        self._text: dict[str, list[PrivateValue]] = {}
        self._canary_tokens: list[tuple[str, PrivateValue]] = []
        for v in vals:
            self._index(v)
        keys = sorted(self._text, key=len, reverse=True)
        self._text_re = (
            re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(k) for k in keys) + r")(?![a-z0-9])")
            if keys else None
        )

    def _index(self, v: PrivateValue) -> None:
        if v.kind is ValueKind.MONEY:
            fen = int(v.value)  # type: ignore[arg-type]
            key = money_key(fen)
            self._money_marked.setdefault(key, []).append(v)
            if money_bare_ok(fen):
                self._money_bare.setdefault(key, []).append(v)
        elif v.kind is ValueKind.RATE:
            pct, frac = rate_keys(v.value)  # type: ignore[arg-type]
            for k in pct:
                self._rate_pct.setdefault(k, []).append(v)
            for k in frac:
                self._rate_frac.setdefault(k, []).append(v)
        elif v.kind is ValueKind.RATIO:
            self._ratio.setdefault(ratio_key(int(v.value)), []).append(v)  # type: ignore[arg-type]
        elif v.kind is ValueKind.TERMS:
            alias_keys = sorted({terms_alias_key(a) for a in v.aliases if terms_alias_key(a)}, key=len,
                                reverse=True)
            pattern = re.compile(
                r"(?<![a-z0-9])(?:" + "|".join(re.escape(a) for a in alias_keys) + r")(?![a-z0-9])"
            )
            self._terms.append((v, pattern))
        else:
            for s in (str(v.value), *v.aliases):
                k = text_key(s)
                if len(k) >= 3:
                    self._text.setdefault(k, []).append(v)
            if v.category is Category.CANARY:
                sq = canary_squash(str(v.value))
                if len(sq) >= _MIN_CANARY_SQUASH:
                    self._canary_tokens.append((sq, v))

    # construction ----------------------------------------------------------------------------

    @classmethod
    def from_values(cls, values: Iterable[PrivateValue]) -> ProtectedSet:
        return cls(values)

    @classmethod
    def build(
        cls,
        state: FinancialState,
        mandate: Mandate,
        *,
        extra_private: Sequence[PrivateValue] = (),
        canaries: Sequence[Canary] | None = None,
    ) -> ProtectedSet:
        """Every value that must never leave in text to a counterparty that does not own it."""
        out: list[PrivateValue] = []
        M, F, B = Category.MANDATE, Category.FACILITY, Category.BALANCE
        T, C, N = Category.COUNTERPARTY_TERMS, Category.CONCESSION, Category.NAME

        def money(label: str, fen: int, owner: str | None, cat: Category) -> None:
            if fen and fen > 0:
                out.append(PrivateValue.money(label, fen, owner=owner, category=cat))

        def rate(label: str, bp: int | None, owner: str | None, cat: Category) -> None:
            if bp and bp > 0:
                out.append(PrivateValue.rate_bp(label, bp, owner=owner, category=cat))

        def ratio(label: str, bp: int | None, owner: str | None, cat: Category) -> None:
            if bp and bp > 0:
                out.append(PrivateValue.ratio_bp(label, bp, owner=owner, category=cat))

        # mandate: nobody but the owner
        money("mandate.min_cash", mandate.min_cash_fen, None, M)
        money("mandate.max_aggregate_forward_concession", mandate.max_aggregate_forward_concession_fen, None, M)
        for buyer, cap in sorted(mandate.per_buyer_caps_fen.items()):
            money(f"mandate.per_buyer_cap.{buyer}", cap, None, M)
        rate("mandate.max_immediate_discount", mandate.max_immediate_discount_bp, None, M)
        ratio("mandate.min_dscr", mandate.min_dscr_bp, None, M)
        ratio("mandate.max_leverage", mandate.max_leverage_bp, None, M)
        rate("mandate.max_apr", mandate.max_apr_bp, None, M)
        money("mandate.tier2_single_commitment", mandate.tier2_single_commitment_fen, None, M)

        # facilities: visible to their own lender only
        for f in state.facilities:
            lender = f.lender_id
            p = f"facility.{f.id}"
            money(f"{p}.limit", f.limit_fen, lender, F)
            money(f"{p}.drawn", f.drawn_fen, lender, F)
            rate(f"{p}.rate", f.rate_bp, lender, F)
            rate(f"{p}.fee", f.fee_bp_per_advance, lender, F)
            rate(f"{p}.upfront_fee", f.upfront_fee_bp, lender, F)
            rate(f"{p}.advance_rate", f.advance_rate_bp, lender, F)
            all_in = _all_in_rate(f.rate_bp, f.fee_bp_per_advance, f.fee_period_days)
            if all_in:
                out.append(PrivateValue.rate(f"{p}.all_in_rate", all_in, owner=lender, category=F))
            for cov in f.covenants:
                ratio(f"{p}.covenant.{cov.id}", cov.threshold_bp, lender, F)

        # balances
        money("state.cash", state.cash_fen, None, B)
        money("state.monthly_ebitda", state.monthly_ebitda_fen, None, B)
        for d in state.debts:
            money(f"debt.{d.id}.principal", d.principal_fen, None, B)
            money(f"debt.{d.id}.monthly_service", d.monthly_debt_service_fen, None, B)
        for fl in state.flows:
            money(f"flow.{fl.id}", abs(fl.amount_fen), fl.counterparty_id, B)

        # counterparty names, and the aliases that identify whose terms a sentence states
        aliases: dict[str, tuple[str, ...]] = {}
        for cp in state.counterparties:
            names, extra = counterparty_aliases(cp)
            aliases[cp.id] = names + extra
            if cp.role in ("BUYER", "LENDER", "SUPPLIER"):
                out.append(PrivateValue.text(f"counterparty.{cp.id}.name", cp.name, owner=cp.id,
                                             aliases=names[1:], category=N))

        def terms_aliases(cp_id: str) -> tuple[str, ...]:
            if cp_id not in aliases:  # a counterparty missing from the registry: id-derived aliases only
                names, extra = counterparty_aliases(Counterparty(id=cp_id, name=cp_id, role="BUYER"))
                aliases[cp_id] = tuple(dict.fromkeys(names + extra))
            return aliases[cp_id]

        # other buyers' receivables and terms: visible to that buyer only
        for r in state.receivables:
            money(f"receivable.{r.id}.face", r.face_fen, r.counterparty_id, T)
            out.append(PrivateValue.terms(f"receivable.{r.id}.terms", r.terms_days, owner=r.counterparty_id,
                                          aliases=terms_aliases(r.counterparty_id)))
        for ri in state.recurring_invoices:
            money(f"recurring.{ri.counterparty_id}.face", ri.face_fen, ri.counterparty_id, T)
            out.append(PrivateValue.terms(f"recurring.{ri.counterparty_id}.terms", ri.terms_days,
                                          owner=ri.counterparty_id, aliases=terms_aliases(ri.counterparty_id)))

        # concessions already committed, by counterparty
        for fc in state.forward_concessions:
            money(f"concession.{fc.id}", fc.value_fen, fc.counterparty_id, C)

        out.extend(extra_private)
        out.extend(c.private_value() for c in (load_canaries() if canaries is None else canaries))
        return cls(out)

    # inspection --------------------------------------------------------------------------------

    @property
    def values(self) -> tuple[PrivateValue, ...]:
        return self._values

    def labels(self) -> list[str]:
        return [v.label for v in self._values]

    def get(self, label: str) -> PrivateValue:
        for v in self._values:
            if v.label == label:
                return v
        raise KeyError(label)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"ProtectedSet({len(self._values)} values)"


class _Allowed:
    __slots__ = ("days", "frac", "money", "pct", "ratio", "text")

    def __init__(self, allow: Iterable[AllowedValue]) -> None:
        self.pct: set[str] = set()
        self.frac: set[str] = set()
        self.ratio: set[str] = set()
        self.money: set[str] = set()
        self.days: set[int] = set()
        self.text: set[str] = set()
        for a in allow:
            if a.kind is ValueKind.MONEY:
                self.money.add(money_key(int(a.value)))  # type: ignore[arg-type]
            elif a.kind is ValueKind.RATE:
                pct, frac = rate_keys(a.value)  # type: ignore[arg-type]
                self.pct |= pct
                self.frac |= frac
            elif a.kind is ValueKind.RATIO:
                self.ratio.add(ratio_key(int(a.value)))  # type: ignore[arg-type]
            elif a.kind is ValueKind.TERMS:
                self.days.add(int(a.value))  # type: ignore[arg-type]
            else:
                self.text.add(text_key(str(a.value)))


def scan(
    text: str,
    protected: ProtectedSet,
    *,
    recipient_id: str,
    allow: Iterable[AllowedValue] = (),
) -> list[Leak]:
    """Protected values stated in `text` that `recipient_id` is not entitled to see.

    A leak needs a boundary-delimited match of a protected surface form. Small amounts and years
    match only next to a currency marker, rates need a %/bp suffix (or a distinctive decimal fraction
    like 0.064), ratios need x/×/times/倍, and payment terms need an alias of their owner in the same
    sentence. A value the recipient owns, or one in `allow`, is not a leak. Canaries always are.
    """
    if not isinstance(text, str) or not text:
        return []
    norm = _normalise(text)
    allowed = _Allowed(allow)
    found: dict[str, Leak] = {}

    def report(v: PrivateValue) -> None:
        if v.label not in found:
            found[v.label] = Leak(label=v.label, kind=v.kind, category=v.category, owner=v.owner)

    def hit(bucket: list[PrivateValue] | None, is_allowed: bool) -> None:
        if not bucket:
            return
        permitted = is_allowed or any(v.entitled(recipient_id) for v in bucket)
        for v in bucket:
            if v.category is Category.CANARY or not permitted:
                report(v)

    p = protected
    for tok in tokens(norm):
        c = tok.canon
        if tok.suffix == "%":
            hit(p._rate_pct.get(c + "%"), c + "%" in allowed.pct)
        elif tok.suffix == "x":
            hit(p._ratio.get(c + "x"), c + "x" in allowed.ratio)
        if tok.marked:
            hit(p._money_marked.get(c), c in allowed.money)
        elif not tok.identifier:
            hit(p._money_bare.get(c), c in allowed.money)
        if not tok.identifier:
            hit(p._rate_frac.get(c), c in allowed.frac)

    if p._terms:
        for sent in sentences(norm):
            days = day_counts(sent)
            if not days:
                continue
            for v, pattern in p._terms:
                if v.value in days and v.value not in allowed.days and not v.entitled(recipient_id) \
                        and pattern.search(sent):
                    report(v)

    folded = fold(text)
    if p._text_re is not None:
        for m in p._text_re.finditer(folded):
            k = m.group(0)
            hit(p._text.get(k), k in allowed.text)

    if p._canary_tokens:
        squashed = squash(folded)
        for sq, v in p._canary_tokens:
            if sq in squashed:
                report(v)

    return list(found.values())


def canary_tripped(text: str, canaries: Sequence[Canary] | None = None) -> list[str]:
    """Ids of the canaries present in `text`, in any surface form. Call it on LLM output or outbound text."""
    cs = load_canaries() if canaries is None else tuple(canaries)
    pset = _canary_set(cs)
    by_label = {c.label: c.id for c in cs}
    return [by_label[leak.label] for leak in scan(text, pset, recipient_id=OWNER_ID)]


_CANARY_SETS: dict[tuple[Canary, ...], ProtectedSet] = {}


def _canary_set(cs: tuple[Canary, ...]) -> ProtectedSet:
    if cs not in _CANARY_SETS:
        _CANARY_SETS[cs] = ProtectedSet.from_values(c.private_value() for c in cs)
    return _CANARY_SETS[cs]
