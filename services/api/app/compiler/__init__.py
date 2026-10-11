"""Offer, term-sheet and contract compiler (untrusted). Sees documents only; its output is a proposal.

Public API: `compile_offer(docs, counterparty_id)`, `compile_term_sheet(doc)`, `compile_contract(doc)` and the
`Compiler` class (implements `app.domain.ports.OfferCompiler`, with injectable backends).
"""

from app.compiler.contract import MAX_CHUNKS, ContractTooLong
from app.compiler.service import Compiler, compile_contract, compile_offer, compile_term_sheet

__all__ = ["MAX_CHUNKS", "Compiler", "ContractTooLong", "compile_contract", "compile_offer", "compile_term_sheet"]
