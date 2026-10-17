"""The read-only tools the Ask FLOW router routes to, by area. Each area module declares `SPECS`; `app.nl.router.catalogue`
collects them into `TOOLS`. Every tool reads the books and writes words; none writes to the store."""

from app.nl.router.tools import activity, advice, capex, covenants, customers, deals, debt, liquidity, mandate

AREAS = (liquidity, debt, customers, deals, covenants, capex, activity, mandate, advice)

__all__ = ["AREAS"]
