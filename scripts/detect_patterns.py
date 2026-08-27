import json
from collections import Counter
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "data" / "fixtures" / "worm_cluster_transactions.json"
OUTPUT_FILE = PROJECT_ROOT / "public" / "data" / "anomaly_clusters.json"


def get_output_statistics(transaction: dict) -> dict:
    """计算交易输出的数量、总额、最大输出占比等基础特征。"""
    outputs = transaction["outputs"]
    total_output_value = sum(output["value_btc"] for output in outputs)

    if total_output_value == 0:
        return {
            "output_count": 0,
            "total_output_value": 0,
            "largest_output_ratio": 0
        }

    largest_output = max(
        output["value_btc"]
        for output in outputs
    )

    return {
        "output_count": len(outputs),
        "total_output_value": total_output_value,
        "largest_output_ratio": largest_output / total_output_value
    }


def entity_labels_for_addresses(addresses: set[str], address_labels: dict[str, dict]) -> list[dict]:
    """Expose known entity context without treating it as proof of wrongdoing."""
    return [
        {"address": address, **address_labels[address]}
        for address in sorted(addresses)
        if address in address_labels
    ]


def entity_evidence(entity_labels: list[dict]) -> list[str]:
    return [
        f"Flow touches labelled {item['category']} entity {item['entity']} ({item['confidence']} confidence)"
        for item in entity_labels
    ]


def detect_collection(transaction: dict, address_labels: dict[str, dict] | None = None) -> dict | None:
    """
    归集型交易：
    多个输入汇集到一个或少量主要输出中。
    """
    input_count = len(transaction["inputs"])
    stats = get_output_statistics(transaction)

    is_collection = (
        input_count >= 2
        and stats["output_count"] <= 2
        and stats["largest_output_ratio"] >= 0.85
    )

    if not is_collection:
        return None

    risk_score = min(
        95,
        60
        + input_count * 8
        + int(stats["largest_output_ratio"] * 15)
    )

    entity_labels = entity_labels_for_addresses(
        {output["address"] for output in transaction["outputs"]}, address_labels or {}
    )
    return {
        "id": f"collection:{transaction['txid']}",
        "pattern": "Collection",
        "risk_score": risk_score,
        "transactions": [transaction["txid"]],
        "transaction_count": 1,
        "value_btc": round(stats["total_output_value"], 8),
        "time_range": {
            "start": transaction["timestamp"],
            "end": transaction["timestamp"]
        },
        "entity_labels": entity_labels,
        "evidence": [
            f"{input_count} input UTXOs converge in this transaction",
            f"The largest output represents {stats['largest_output_ratio']:.0%} of the total output value",
            f"The transaction creates only {stats['output_count']} outputs"
        ] + entity_evidence(entity_labels)
    }


def detect_split(transaction: dict, address_labels: dict[str, dict] | None = None) -> dict | None:
    """
    拆分型交易：
    少量输入被拆成多个输出。
    """
    input_count = len(transaction["inputs"])
    stats = get_output_statistics(transaction)

    is_split = (
        input_count <= 2
        and stats["output_count"] >= 3
        and stats["largest_output_ratio"] <= 0.45
    )

    if not is_split:
        return None

    risk_score = min(
        95,
        55
        + stats["output_count"] * 7
        + (2 - input_count) * 5
    )

    entity_labels = entity_labels_for_addresses(
        {output["address"] for output in transaction["outputs"]}, address_labels or {}
    )
    return {
        "id": f"split:{transaction['txid']}",
        "pattern": "Split",
        "risk_score": risk_score,
        "transactions": [transaction["txid"]],
        "transaction_count": 1,
        "value_btc": round(stats["total_output_value"], 8),
        "time_range": {
            "start": transaction["timestamp"],
            "end": transaction["timestamp"]
        },
        "entity_labels": entity_labels,
        "evidence": [
            f"The transaction uses only {input_count} input UTXOs",
            f"It creates {stats['output_count']} output UTXOs",
            f"The largest output accounts for {stats['largest_output_ratio']:.0%}, indicating dispersed value"
        ] + entity_evidence(entity_labels)
    }


def detect_worms(transactions: list[dict], address_labels: dict[str, dict] | None = None) -> list[dict]:
    """检测高频 Worm：主 UTXO 快速连续花费，并伴随小额输出和地址复用。"""
    spent_by = {
        (tx_input["prev_txid"], tx_input["prev_vout"]): transaction
        for transaction in transactions
        for tx_input in transaction["inputs"]
    }
    output_index = {
        (transaction["txid"], output["vout"]): output
        for transaction in transactions
        for output in transaction["outputs"]
    }
    worms = []
    claimed = set()

    for start in transactions:
        if start["txid"] in claimed:
            continue
        chain = [start]
        current = start
        while True:
            outputs = current["outputs"]
            if not outputs:
                break
            largest = max(outputs, key=lambda output: output["value_btc"])
            next_tx = spent_by.get((current["txid"], largest["vout"]))
            if next_tx is None:
                break
            seconds = (parse_time(next_tx["timestamp"]) - parse_time(current["timestamp"])).total_seconds()
            retained = largest["value_btc"] / max(sum(output["value_btc"] for output in current["outputs"]), 0.00000001)
            if seconds < 0 or seconds > 90 or retained < 0.90:
                break
            chain.append(next_tx)
            current = next_tx

        # 长链门槛刻意高于普通连续支付，降低将正常找零路径误报为 Worm 的概率。
        if len(chain) < 8:
            continue
        chain_ids = [transaction["txid"] for transaction in chain]
        if any(txid in claimed for txid in chain_ids):
            continue
        claimed.update(chain_ids)
        duration = int((parse_time(chain[-1]["timestamp"]) - parse_time(chain[0]["timestamp"])).total_seconds())
        hop_count = len(chain) - 1
        avg_hop_seconds = duration / hop_count
        all_outputs = [output for transaction in chain for output in transaction["outputs"]]
        addresses = [output["address"] for output in all_outputs]
        address_counts = Counter(addresses)
        address_reuse_count = sum(count - 1 for count in address_counts.values() if count > 1)
        address_reuse_ratio = address_reuse_count / max(len(addresses), 1)
        small_output_count = sum(
            output["value_btc"] <= max(item["value_btc"] for item in transaction["outputs"]) * 0.05
            for transaction in chain
            for output in transaction["outputs"]
        )
        small_output_ratio = small_output_count / max(len(all_outputs), 1)
        main_output_ratios = [
            max(output["value_btc"] for output in transaction["outputs"])
            / sum(output["value_btc"] for output in transaction["outputs"])
            for transaction in chain
        ]
        starting_inputs = [
            output_index.get((tx_input["prev_txid"], tx_input["prev_vout"]))
            for tx_input in chain[0]["inputs"]
        ]
        starting_value = sum(output["value_btc"] for output in starting_inputs if output is not None)
        ending_value = max(output["value_btc"] for output in chain[-1]["outputs"])
        value_retention_ratio = ending_value / max(starting_value, ending_value)
        transferred = max(output["value_btc"] for output in chain[0]["outputs"])
        risk_score = min(99, round(
            35
            + min(25, len(chain) * 1.2)
            + min(20, 60 / max(avg_hop_seconds, 1))
            + min(10, address_reuse_ratio * 15)
            + min(10, small_output_ratio * 15)
        ))
        features = {
            "chain_length": len(chain),
            "hop_count": hop_count,
            "duration_seconds": duration,
            "avg_hop_seconds": round(avg_hop_seconds, 2),
            "unique_address_count": len(address_counts),
            "address_reuse_count": address_reuse_count,
            "address_reuse_ratio": round(address_reuse_ratio, 4),
            "small_output_count": small_output_count,
            "small_output_ratio": round(small_output_ratio, 4),
            "avg_main_output_ratio": round(sum(main_output_ratios) / len(main_output_ratios), 4),
            "avg_branching_factor": round(len(all_outputs) / len(chain), 2),
            "value_retention_ratio": round(value_retention_ratio, 4),
        }
        labelled_addresses = {output["address"] for transaction in chain for output in transaction["outputs"]}
        labelled_addresses.update(
            output["address"] for transaction in chain for tx_input in transaction["inputs"]
            if (output := output_index.get((tx_input["prev_txid"], tx_input["prev_vout"]))) is not None
        )
        entity_labels = entity_labels_for_addresses(labelled_addresses, address_labels or {})
        worms.append({
            "id": f"worm:{chain_ids[0]}:{chain_ids[-1]}",
            "pattern": "Worm",
            "risk_score": risk_score,
            "transactions": chain_ids,
            "transaction_count": len(chain_ids),
            "value_btc": round(transferred, 8),
            "time_range": {"start": chain[0]["timestamp"], "end": chain[-1]["timestamp"]},
            "features": features,
            "entity_labels": entity_labels,
            "evidence": [
                f"{len(chain_ids)} transactions repeatedly spend the main UTXO across {hop_count} hops",
                f"The full chain completes in {duration} seconds, averaging {avg_hop_seconds:.1f} seconds per hop",
                f"Output addresses are reused {address_reuse_count} times, a reuse rate of {address_reuse_ratio:.0%}",
                f"{small_output_count} low-value side outputs represent {small_output_ratio:.0%} of all outputs",
                f"The final hop retains {value_retention_ratio:.0%} of the initial main-path value"
            ] + entity_evidence(entity_labels)
        })
    return worms


def parse_time(timestamp: str):
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def detect_anomalies(transactions: list[dict], address_labels: dict[str, dict] | None = None) -> list[dict]:
    """逐笔执行异常规则，返回按风险从高到低排列的结果。"""
    anomalies = []

    for transaction in transactions:
        collection_result = detect_collection(transaction, address_labels)
        split_result = detect_split(transaction, address_labels)

        if collection_result is not None:
            anomalies.append(collection_result)

        if split_result is not None:
            anomalies.append(split_result)

    anomalies.extend(detect_worms(transactions, address_labels))

    return sorted(
        anomalies,
        key=lambda anomaly: anomaly["risk_score"],
        reverse=True
    )


def main() -> None:
    with INPUT_FILE.open("r", encoding="utf-8") as file:
        source_data = json.load(file)

    anomalies = detect_anomalies(source_data["transactions"])

    result = {
        "metadata": {
            "source_transaction_count": len(source_data["transactions"]),
            "anomaly_count": len(anomalies),
            "source_file": INPUT_FILE.name,
            "detector_version": "worm-cluster-v2"
        },
        "anomalies": anomalies
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    print(f"Detected {len(anomalies)} anomaly patterns:")

    for anomaly in anomalies:
        print(
            f"- [{anomaly['pattern']}] "
            f"{anomaly['transactions'][0]} "
            f"(Risk {anomaly['risk_score']})"
        )

    print(f"\nOutput file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
