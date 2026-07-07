import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parents[2] / "bitcoin.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialise_database():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                txid TEXT PRIMARY KEY,
                fee INTEGER NOT NULL,
                vsize INTEGER NOT NULL,
                value INTEGER NOT NULL,
                fee_rate REAL NOT NULL,
                seen_at TEXT NOT NULL
            )
            """
        )