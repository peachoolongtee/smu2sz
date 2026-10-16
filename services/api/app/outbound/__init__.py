"""The message FLOW prepares for a buyer: a verified counter in words the buyer can read, for the owner to copy and send themself.

Pure: this package imports only `app.domain`. It sends nothing, stores nothing and decides nothing. The words are a deterministic function of the
counter's typed obligations, the books' own dates (`FinancialState.as_of` is day 0) and the buyer's name; no model writes them, and a term this
module has no wording for is refused (`NoWording`), never guessed. The API guards the result (`app.egress`) before anyone sees it.
"""

from app.outbound.message import (
    OFFER_DAYS,
    TEMPLATE_VERSION,
    BuyerMessage,
    NoWording,
    calendar_date,
    message_hash,
    render,
    valid_until,
)

__all__ = [
    "OFFER_DAYS",
    "TEMPLATE_VERSION",
    "BuyerMessage",
    "NoWording",
    "calendar_date",
    "message_hash",
    "render",
    "valid_until",
]
