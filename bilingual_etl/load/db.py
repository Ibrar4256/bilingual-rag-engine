import os
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://bilingual:bilingual@localhost:5432/bilingual_search",
)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def get_dict_cursor(conn):
    return conn.cursor(cursor_factory=RealDictCursor)


def init_schema():
    sql = SCHEMA_PATH.read_text()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("Schema initialized successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    init_schema()
