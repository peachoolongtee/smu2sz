# Fresh red team, 3 Oct 2026

A subagent with no knowledge of the backlog attacked `dev` at `fbd35ba` (after the consent, buyer-channel,
admission, capex and invoice-terms merges). It read the code first and reproduced every finding with the probes in
this folder. Run a probe from the repo root:

```
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONPATH=services/api PYTHONUTF8=1 uv run --project services/api python docs/research/redteam-2026-10-03/<probe>.py
```

The probes assert the defect as it stood. Once a finding is fixed its probe fails or prints the corrected behaviour.

## Findings

| # | Severity | Finding | Probe | Status |
| --- | --- | --- | --- | --- |
| 1 | HIGH | A receipt of any size on a financed invoice repaid the whole advance and its charges from the owner's cash (a 1-fen receipt took cash to −¥62,994.07), reopened the invoice and let it be financed again | `p03` | In progress on `fix/funding-lots`: the lender is paid from the receipt only, cash never falls on a receipt, the invoice stays FINANCED until the advance is cleared |
| 2 | HIGH | Three refused agent-key operations on a buyer's invoice opened that buyer's circuit; the bank feed's real receipt was then refused, and its retry was a DUPLICATE of the refusal | `p01` | Fixed 3 Oct (`tests/operations/test_circuit_scope.py`): the circuit gates and counts only offer operations; a refused key can run again |
| 3 | MEDIUM | An advance is booked as cash on the request day, so a reserve alert clears before the money arrives (audit A08, found independently) | `p02` | In progress on `fix/funding-lots` (ADR-0010) |

## Attacked and not broken

- Approval binding in chat: "approve the pending one" resolves only to the item shown (`p04`).
- Charges on a fully repaid advance match the engine to the fen.
- Route authentication: read, alert, decision, capex, what-if and borrower-file routes need the owner.
- Sessions are bound to actor and credential; an agent key cannot continue the owner's session.
- Consent grammar: negation, condition, future time and questions never execute; look-alike digits match no id.
- Tier 3 operations are refused for everyone; an approval re-runs every gate against today's mandate.

## Suggested next attacks, and what was done

- Price cut on a partly settled invoice making the face lower than the settled amount: guarded 3 Oct
  (`test_a_price_cut_cannot_take_an_invoice_below_what_is_already_settled`).
- Backdated bank receipts counting toward a circuit: closed by the fix to finding 2.
- A buyer tripping its own circuit to have its payments refused: closed by the fix to finding 2.
- Unauthenticated `POST /offers` with any `counterparty_id`: open (backlog R04).
- `RequestOwnerApproval` free-text subject shown to the owner as the reason; non-unique `payload_op_id`: open
  (backlog R08).
- Idempotency-key squatting by getting a refusal logged under a predictable key: closed by the fix to finding 2.
