"""PostgreSQL: API processes that open the store at the same moment all start (Security Lead, 16 Oct).

Every SqlLedgerStore re-installs the append-only guard (CREATE OR REPLACE FUNCTION, DROP and CREATE TRIGGER) when it opens. On
PostgreSQL two processes doing that at once raced on the system catalog, and one failed with "tuple concurrently updated", so a
second worker or replica could fail to start. Runs only with TERMSLEDGER_TEST_DATABASE_URL, like the rest of the PostgreSQL suite."""

from __future__ import annotations

import os
import threading

import pytest

from tests.concurrency.harness import PG_ENV, claim_postgres

pytestmark = pytest.mark.skipif(not os.environ.get(PG_ENV), reason=f"{PG_ENV} is not set: the PostgreSQL variant is UNVERIFIED")


def test_stores_opening_at_the_same_moment_all_install_the_guard() -> None:
    from app.persistence import SqlLedgerStore

    url = os.environ[PG_ENV]
    claim_postgres(url)
    def open_store(barrier: threading.Barrier, errors: list[BaseException]) -> None:
        barrier.wait()
        try:
            SqlLedgerStore(url).dispose()
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    for _round in range(5):  # the first round creates the tables on an empty database; the others re-install the guard
        barrier = threading.Barrier(8)
        errors: list[BaseException] = []
        threads = [threading.Thread(target=open_store, args=(barrier, errors)) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, [str(e).splitlines()[0] for e in errors]
