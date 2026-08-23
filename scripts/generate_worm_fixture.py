"""Generate a deterministic Bitcoin transaction window for the ChainScope demo.

The fixture deliberately contains ordinary payments plus one labelled, high-frequency
worm cluster.  Labels live only in metadata and must not be used by the detector.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "fixtures" / "worm_cluster_transactions.json"


def transaction(txid: str, timestamp: datetime, inputs: list[dict], outputs: list[dict], block_height: int) -> dict:
    return {
        "txid": txid,
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "block_height": block_height,
        "inputs": inputs,
        "outputs": outputs,
    }


def build_fixture() -> dict:
    start = datetime(2024, 5, 18, 10, 0, tzinfo=timezone.utc)
    transactions = []

    # Eight ordinary transactions give the anomaly visual context and comparison cases.
    transactions.append(transaction("tx_coinbase_normal_001", start, [], [
        {"vout": 0, "address": "miner_normal", "value_btc": 15.0},
    ], 840112))
    transactions.append(transaction("tx_salary_normal_002", start + timedelta(seconds=90), [
        {"prev_txid": "tx_coinbase_normal_001", "prev_vout": 0},
    ], [
        {"vout": 0, "address": "salary_recipient", "value_btc": 4.0},
        {"vout": 1, "address": "normal_wallet_a", "value_btc": 10.98},
    ], 840113))
    transactions.append(transaction("tx_purchase_normal_003", start + timedelta(seconds=210), [
        {"prev_txid": "tx_salary_normal_002", "prev_vout": 0},
    ], [
        {"vout": 0, "address": "merchant_bookshop", "value_btc": 1.2},
        {"vout": 1, "address": "salary_recipient", "value_btc": 2.79},
    ], 840114))
    transactions.append(transaction("tx_exchange_fund_004", start + timedelta(seconds=330), [
        {"prev_txid": "tx_salary_normal_002", "prev_vout": 1},
    ], [
        {"vout": 0, "address": "exchange_deposit", "value_btc": 8.0},
        {"vout": 1, "address": "normal_wallet_a", "value_btc": 2.96},
    ], 840115))
    transactions.append(transaction("tx_tip_normal_005", start + timedelta(seconds=420), [
        {"prev_txid": "tx_purchase_normal_003", "prev_vout": 1},
    ], [
        {"vout": 0, "address": "creator_tip", "value_btc": 0.2},
        {"vout": 1, "address": "salary_recipient", "value_btc": 2.58},
    ], 840116))
    transactions.append(transaction("tx_merchant_settlement_006", start + timedelta(seconds=510), [
        {"prev_txid": "tx_purchase_normal_003", "prev_vout": 0},
    ], [{"vout": 0, "address": "merchant_bank", "value_btc": 1.19}], 840117))
    transactions.append(transaction("tx_change_normal_007", start + timedelta(seconds=650), [
        {"prev_txid": "tx_exchange_fund_004", "prev_vout": 1},
    ], [{"vout": 0, "address": "normal_wallet_b", "value_btc": 2.95}], 840118))
    transactions.append(transaction("tx_donation_normal_008", start + timedelta(seconds=790), [
        {"prev_txid": "tx_tip_normal_005", "prev_vout": 1},
    ], [
        {"vout": 0, "address": "charity", "value_btc": 1.0},
        {"vout": 1, "address": "salary_recipient", "value_btc": 1.57},
    ], 840119))

    # The worm: 25 fast hops, repetitive relay addresses, and small side outputs.
    # Its main UTXO is consumed at every hop; the detector must recover this without
    # consulting the ground-truth labels below.
    previous_txid = "tx_exchange_fund_004"
    previous_vout = 0
    value = 8.0
    worm_ids = []
    worm_start = start + timedelta(seconds=840)
    elapsed_seconds = 0
    for hop in range(1, 26):
        txid = f"tx_worm_{hop:03d}"
        worm_ids.append(txid)
        current_time = worm_start + timedelta(seconds=elapsed_seconds)
        main_value = round(value * 0.982, 8)
        side_value = round(value * 0.012, 8)
        transactions.append(transaction(txid, current_time, [
            {"prev_txid": previous_txid, "prev_vout": previous_vout},
        ], [
            {"vout": 0, "address": f"worm_relay_{hop % 6:02d}", "value_btc": main_value},
            {"vout": 1, "address": f"worm_dust_{hop % 4:02d}", "value_btc": side_value},
            {"vout": 2, "address": "miner_fee_sink", "value_btc": 0.001},
        ], 840120 + hop // 8))
        previous_txid, previous_vout, value = txid, 0, main_value
        elapsed_seconds += 2 + hop % 3

    return {
        "metadata": {
            "description": "33 transactions: 8 normal context transactions and one 25-hop worm cluster",
            "generated_at": "deterministic-demo",
            "ground_truth": {"worm_transaction_ids": worm_ids},
        },
        "transactions": transactions,
    }


def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(build_fixture(), file, ensure_ascii=False, indent=2)
    print(f"Worm fixture generated: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
