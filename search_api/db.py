"""
Database connection for the Search API.

Deliberately not shared with `bilingual_etl/load/db.py` — the two are
independent Docker services (see CLAUDE.md project structure) with separate
dependency sets and lifecycles, so a small amount of duplication here is
correct rather than coupling them at import time.
"""

import os

from psycopg2 import pool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://bilingual:bilingual@localhost:5434/bilingual_search",
)

_pool: pool.ThreadedConnectionPool | None = None


def _get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=int(os.getenv("DB_POOL_MAX", "10")),
            dsn=DATABASE_URL,
        )
    return _pool


class _PooledConnection:
    """Wraps a pooled connection so .close() returns it to the pool."""

    def __init__(self, conn, p):
        self._conn = conn
        self._pool = p

    def close(self):
        try:
            self._pool.putconn(self._conn)
        except Exception:
            pass

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    @property
    def autocommit(self):
        return self._conn.autocommit

    @autocommit.setter
    def autocommit(self, value):
        self._conn.autocommit = value

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_connection():
    p = _get_pool()
    return _PooledConnection(p.getconn(), p)
