"""Read-only answers to the owner's top 30 questions (research/owner-questions BASELINE sections 4 and 5).

Public interface: `answer(question, lang, ctx) -> AnswerReply | None` and `AnswerReply`. `metrics` holds the reusable metrics the
answers are written from. Nothing in this package writes, books, sends or executes.
"""

from app.nl.answers.answers import AnswerReply, answer, match, question_ids

__all__ = ["AnswerReply", "answer", "match", "question_ids"]
