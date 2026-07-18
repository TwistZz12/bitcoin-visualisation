from datetime import datetime, timezone
from statistics import median

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

ANOMALY_Z_SCORE_THRESHOLD = 3.5


def calculate_mad(values, centre):
    return median(abs(value - centre) for value in values)


def calculate_robust_z_score(value, centre, mad):
    if mad == 0:
        return 0

    return 0.6745 * (value - centre) / mad


def get_transaction_anomalies():
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
            """
        ).fetchall()

    transactions = [dict(row) for row in rows]

    if len(transactions) < 5:
        return {
            "method": "Median/MAD multi-feature anomaly detection",
            "total_anomalies": 0,
            "anomalies": [],
            "message": "At least 5 transactions are needed for detection.",
        }

    fee_rates = [transaction["fee_rate"] for transaction in transactions]
    values = [transaction["value"] for transaction in transactions]
    vsizes = [transaction["vsize"] for transaction in transactions]

    fee_rate_median = median(fee_rates)
    value_median = median(values)
    vsize_median = median(vsizes)

    fee_rate_mad = calculate_mad(fee_rates, fee_rate_median)
    value_mad = calculate_mad(values, value_median)
    vsize_mad = calculate_mad(vsizes, vsize_median)

    anomalies = []

    for transaction in transactions:
        fee_rate_score = calculate_robust_z_score(
            transaction["fee_rate"], fee_rate_median, fee_rate_mad
        )
        value_score = calculate_robust_z_score(
            transaction["value"], value_median, value_mad
        )
        vsize_score = calculate_robust_z_score(
            transaction["vsize"], vsize_median, vsize_mad
        )

        reasons = []

        if fee_rate_score > ANOMALY_Z_SCORE_THRESHOLD:
            reasons.append("Unusually high fee rate")

        if value_score > ANOMALY_Z_SCORE_THRESHOLD:
            reasons.append("Unusually high transaction value")

        if vsize_score > ANOMALY_Z_SCORE_THRESHOLD:
            reasons.append("Unusually large transaction size")

        if reasons:
            transaction["anomaly_reasons"] = reasons
            transaction["fee_rate_score"] = round(fee_rate_score, 2)
            transaction["value_score"] = round(value_score, 2)
            transaction["vsize_score"] = round(vsize_score, 2)
            anomalies.append(transaction)

    anomalies.sort(
        key=lambda transaction: max(
            transaction["fee_rate_score"],
            transaction["value_score"],
            transaction["vsize_score"],
        ),
        reverse=True,
    )

    return {
        "method": "Median/MAD multi-feature anomaly detection",
        "score_threshold": ANOMALY_Z_SCORE_THRESHOLD,
        "total_transactions_analysed": len(transactions),
        "total_anomalies": len(anomalies),
        "anomalies": anomalies,
    }