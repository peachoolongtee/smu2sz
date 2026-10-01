"""/nl: natural-language requests -> intent + typed slots -> verifier -> typed operations.

Public interface: `handle()` (one turn of a multi-turn session), `opener()` (an agent-initiated turn), `NlRequest`, `NlResponse`, `Intent`,
`reset_sessions()`. A request can only ever produce typed operations sent to the executor, and never
skips the verifier (INVARIANTS 1, 2 and 12).
"""

from app.nl.models import Intent, NlRequest, NlResponse, PlanStep
from app.nl.service import handle, opener
from app.nl.sessions import SESSIONS, reset_sessions

__all__ = ["SESSIONS", "Intent", "NlRequest", "NlResponse", "PlanStep", "handle", "opener", "reset_sessions"]
