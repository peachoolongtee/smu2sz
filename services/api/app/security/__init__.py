"""Security: the attack catalogue runner (an evaluation harness) and security-event helpers.

Public interface:
- `flag_events(offer_or_term_sheet, day)`: INJECTION SecurityEvents for compiler authority claims.
- `app.security.attacks`: `AttackRunner`, `load_catalogue`, `metrics`, `write_report`, the `/nl` group
  (`nl_catalogue`, `NlAttackRunner`) and the CLI `uv run python -m app.security.attacks --report`.
  Import it explicitly; it drives the whole app through the API and through POST /nl, and nothing on
  the request path may import it.
"""

from app.security.events import flag_events

__all__ = ["flag_events"]
