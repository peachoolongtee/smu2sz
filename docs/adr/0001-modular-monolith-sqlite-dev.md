# ADR-0001: One modular monolith; SQLite for dev and tests, Postgres to deploy

TermsLedger is built as one FastAPI service with strict internal module boundaries, one Next.js app and one database. It has no microservices, queues or solver. The role split in handoff §6 (compiler, engine and verifier, executor, kernel) is enforced by module boundaries and import rules, not by separate processes.

The dev machine has no Docker. Tests and local dev therefore run on SQLite through SQLAlchemy 2, and the Docker Compose stack uses Postgres through `DATABASE_URL`. The `LedgerStore` interface also has an in-memory implementation for unit tests. There are separate Postgres roles per module (handoff §6), applied only in the Compose deployment.

**Consequence:** nothing may use Postgres-only SQL. The hash-chained operations log is computed in Python, not by triggers.
