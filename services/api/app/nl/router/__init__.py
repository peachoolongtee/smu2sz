"""Ask FLOW's router (ADR-0015): the model routes an owner's question to read-only tools from a closed catalogue, code answers.

`app.nl.router.route.route(question, lang, ctx) -> AnswerReply | None`; the catalogue is `app.nl.router.catalogue.TOOLS`. Behind
FEATURE_ASK_ROUTER, owner turns only, after the deterministic answers (app/nl/ask.py).
"""
