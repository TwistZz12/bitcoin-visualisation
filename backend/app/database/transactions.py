from datetime import datetime, timezone

from app.database.connection import get_connection


def save_transactions(transactions):
    seen_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        for transaction in transactions:
            connection.execute(
                """
                INSERT OR IGNORE INTO transactions (
                    txid,
                    fee,
                    vsize,
                    value,
                    fee_rate,
                    seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction["txid"],
                    transaction["fee"],
                    transaction["vsize"],
                    transaction["value"],
                    transaction["fee_rate"],
                    seen_at,
                ),
            )

            

def get_transaction_stats():
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_transactions,
                AVG(fee_rate) AS average_fee_rate,
                MAX(fee_rate) AS max_fee_rate,
                MIN(fee_rate) AS min_fee_rate,
                AVG(value) AS average_value
            FROM transactions
            """
        ).fetchone()

    return {
        "total_transactions": row["total_transactions"],
        "average_fee_rate": round(row["average_fee_rate"] or 0, 2),
        "max_fee_rate": round(row["max_fee_rate"] or 0, 2),
        "min_fee_rate": round(row["min_fee_rate"] or 0, 2),
        "average_value": round(row["average_value"] or 0, 2),
    }           

def get_fee_rate_anomalies():
    stats = get_transaction_stats()
    threshold = stats["average_fee_rate"] * 3

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                txid,
                fee,
                vsize,
                value,
                fee_rate,
                seen_at
            FROM transactions
            WHERE fee_rate > ?
            ORDER BY fee_rate DESC
            """,
            (threshold,),
        ).fetchall()

    return {
        "method": "fee_rate_greater_than_3x_average",
        "average_fee_rate": stats["average_fee_rate"],
        "threshold": round(threshold, 2),
        "total_anomalies": len(rows),
        "anomalies": [dict(row) for row in rows],
    }