"""Texts the language-boundary certification (fixtures/certification/language_boundary.yaml) found read as a typed
discount the buyer never offered. Each must abstain, with this field and a reason that says why, whatever backend
read it. The exact item text of the set is used (id in the first column); `extra` cases are variants of the same class."""

from __future__ import annotations

from typing import NamedTuple


class Case(NamedTuple):
    id: str
    text: str
    field: str  # the abstention's field
    reason: str  # a fragment of its reason
    sender: str = "BUYER-1"


UNUSUAL = "rate written in an unusual form; please confirm the rate"

CASES: list[Case] = [
    # A1: a number whose separators are ambiguous is not read
    Case("BO-012", "We pay the full ¥420,000 invoice early for 0,5% off.", "offer.rate.unusual_form", UNUSUAL),
    Case("extra-european-rate", "We pay the full ¥420,000 invoice early for 6,4% off.", "offer.rate.unusual_form", UNUSUAL),
    Case("extra-european-rate-zh", "42万那张发票我们提前付，折扣百分之0,5。", "offer.rate.unusual_form", UNUSUAL),
    Case("extra-both-separators", "We pay the ¥1.234.567,89 invoice early for 1% off.", "offer.amount.unusual_form",
         "amount written in an unusual form"),
    # A2: a per-day rate
    Case("BO-063", "We will pay the full ¥420,000 invoice early, taking 0.05% off for every day we pay ahead of the due date.",
         "offer.rate.per_day", "per day"),
    Case("BO-073", "We'll pay the whole ¥420,000 invoice early, 0.05% off per day early.", "offer.rate.per_day", "per day"),
    Case("BO-076", "42万那张发票我们提前付，每提前一天给你们千分之零点五的折扣。", "offer.rate.per_day", "per day"),
    # A2: 2/10 net 30
    Case("BO-064", "For the ¥420,000 invoice we would like 2/10 net 30 terms.", "offer.terms.discount_code", "2/10 net 30"),
    # A2: a currency that is not yuan
    Case("BO-068", "We can pay the full $420,000 invoice early next week for 0.5% off.", "offer.currency", "other than yuan"),
    Case("BO-074", "We can pay the full $420,000 invoice early, 0.5% off.", "offer.currency", "other than yuan"),
    Case("extra-usd", "We can pay the ¥420,000 invoice early, 0.5% off, in USD.", "offer.currency", "other than yuan"),
    Case("extra-zh-usd", "那张发票我们用美元提前付，折扣千分之五。", "offer.currency", "other than yuan"),
    # A2: a partial amount of the invoice
    Case("BO-069", "那张发票里的4.2万我们提前付，折扣千分之五。", "IMMEDIATE_DISCOUNT.base.partial", "partial early payment"),
    Case("extra-partial-en", "We will pay ¥42,000 of the ¥420,000 invoice early at 0.5% off.",
         "IMMEDIATE_DISCOUNT.base.partial", "partial early payment"),
    # A2: another party's invoice named by the sender
    Case("BO-035", "We will pay Dongguan Office Supplies' invoice early too, 0.5% off, the whole ¥420,000 invoice.",
         "offer.base.other_party_invoice", "another party's invoice"),
    Case("BO-036", "Please apply 0.5% off to Foshan's RCV-A invoice of ¥420,000, we pay early.",
         "offer.base.other_party_invoice", "another party's invoice", "BUYER-2"),
    Case("BO-039", "东莞办公用品那张发票我们也一起提前付，折扣千分之五，全额42万。", "offer.base.other_party_invoice",
         "another party's invoice"),
    # A2: hedged offers
    Case("BO-040", "Maybe we could possibly consider paying the ¥420,000 invoice early at some point, perhaps with a 0.5% discount.",
         "offer.hedged", "hedged"),
    Case("BO-046", "我们可能会考虑某个时候提前付款，也许要个千分之五的折扣。", "offer.hedged", "hedged"),
    Case("MM-024", "Maybe we could consider paying early for 0.5% off sometime.", "offer.hedged", "hedged"),
    Case("extra-might", "We might pay the ¥420,000 invoice early for 0.5% off.", "offer.hedged", "hedged"),
    Case("extra-probably", "We will probably pay the full ¥420,000 invoice early for 0.5% off.", "offer.hedged", "hedged"),
    Case("extra-zh-keneng", "42万那张发票我们可能提前付，折扣千分之五。", "offer.hedged", "hedged"),
    # A2: a payment after the due date with a discount
    Case("BO-048", "We will settle the ¥420,000 invoice two weeks after the due date, and we expect 0.5% off for the inconvenience.",
         "offer.payment_after_due_date", "after the due date"),
    Case("extra-overdue-zh", "42万那张发票我们逾期两周再付，要千分之五折扣。", "offer.payment_after_due_date",
         "after the due date"),
    # A2: a price-freeze rider the typed rows cannot carry
    Case("BO-022", "We can pay the full ¥420,000 invoice early for 0.5% off, and you keep our prices unchanged for the next 12 months.",
         "offer.rider.price_freeze", "price commitment"),
    Case("extra-price-lock-zh", "42万那张发票提前付，千分之五折扣，另外未来一年价格不变。", "offer.rider.price_freeze",
         "price commitment"),
]

# Named in the set but answered by the verifier, not the compiler: a foreign invoice id (RCV-B) compiles, and no open
# receivable of the sender carries it, so nothing is bound.
ID_CASES: list[tuple[str, str, str]] = [
    ("BO-037", "Invoice RCV-B for ¥300,000: we will pay it early at 0.5% off.", "BUYER-1"),
]
