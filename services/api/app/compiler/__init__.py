"""Offer and term-sheet compiler (untrusted). Sees documents only; its output is a proposal.

Public API: `compile_offer(docs, counterparty_id)`, `compile_term_sheet(doc)` and the `Compiler` class
(implements `app.domain.ports.OfferCompiler`, with injectable backends).
"""

from app.compiler.service import Compiler, compile_offer, compile_term_sheet

__all__ = ["Compiler", "compile_offer", "compile_term_sheet"]
