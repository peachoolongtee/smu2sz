"""Ask FLOW's router (ADR-0015): the model routes an owner's question to read-only tools from a closed catalogue, code answers.

`route(question, lang, ctx) -> AnswerReply | None` (route.py); the catalogue is `catalogue.TOOLS`. Behind FEATURE_ASK_ROUTER, owner
turns only, after the deterministic answers (app/nl/ask.py).
"""

from app.nl.router.route import route

__all__ = ["route"]
