"""Shared test setup.

Set SUT_TEST_FORCE_DATABASE_URL=postgresql://... to run the whole suite against
PostgreSQL (as production does). Each test then starts from empty tables.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PG_URL = os.getenv('SUT_TEST_FORCE_DATABASE_URL', '')


@pytest.fixture(autouse=True)
def _fresh_postgres():
    if not PG_URL:
        yield
        return
    import psycopg
    from config import Config
    from store import connect
    with connect(Config()):          # creates the schema on first use
        pass
    with psycopg.connect(PG_URL, autocommit=True) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()]
        if tables:
            conn.execute('TRUNCATE ' + ','.join(tables) + ' RESTART IDENTITY CASCADE')
    yield
