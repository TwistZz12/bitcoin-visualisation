import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "data" / "fixtures" / "worm_cluster_transactions.json"
OUTPUT_FILE = PROJECT_ROOT / "public" / "data" / "demo_utxo_graph.json"


def get_utxo_id(txid: str, vout: int) -> str:
    """为每个输出建立唯一 UTXO 标识。"""
    return f"utxo:{txid}:{vout}"


def build_utxo_graph(transactions: list[dict]) -> dict:
    """
    将交易列表转换为图结构。

    节点：
    - transaction：交易
    - utxo：交易输出

    边：
    - creates：Transaction -> UTXO
    - spends：UTXO -> Transaction
    """
    nodes = []
    edges = []
    utxo_index = {}
    utxos_by_address = {}

    # 第一轮：建立交易节点、UTXO 节点和创建关系
    for transaction in transactions:
        txid = transaction["txid"]

        nodes.append(
            {
                "id": f"tx:{txid}",
                "type": "transaction",
                "txid": txid,
                "timestamp": transaction["timestamp"],
                "block_height": transaction["block_height"],
                "input_count": len(transaction["inputs"]),
                "output_count": len(transaction["outputs"])
            }
        )

        for output in transaction["outputs"]:
            utxo_id = get_utxo_id(txid, output["vout"])

            utxo = {
                "id": utxo_id,
                "type": "utxo",
                "txid": txid,
                "vout": output["vout"],
                "address": output["address"],
                "value_btc": output["value_btc"],
                "spent_by": None
            }

            nodes.append(utxo)
            utxo_index[utxo_id] = utxo
            utxos_by_address.setdefault(output["address"], []).append(utxo_id)

            edges.append(
                {
                    "id": f"creates:{txid}:{utxo_id}",
                    "source": f"tx:{txid}",
                    "target": utxo_id,
                    "type": "creates"
                }
            )

    # 同一地址的 UTXO 按出现顺序串联，作为低亮度辅助关系。
    # 这类边不代表资金被花费，只用于暴露论文中强调的地址复用行为。
    reused_address_count = 0
    for address, utxo_ids in utxos_by_address.items():
        if len(utxo_ids) < 2:
            continue
        reused_address_count += 1
        for index in range(1, len(utxo_ids)):
            edges.append(
                {
                    "id": f"address_reuse:{address}:{index}",
                    "source": utxo_ids[index - 1],
                    "target": utxo_ids[index],
                    "type": "address_reuse",
                    "address": address
                }
            )

    # 第二轮：读取输入，建立 UTXO 被后续交易花费的关系
    for transaction in transactions:
        current_tx_node_id = f"tx:{transaction['txid']}"

        for tx_input in transaction["inputs"]:
            utxo_id = get_utxo_id(
                tx_input["prev_txid"],
                tx_input["prev_vout"]
            )

            previous_utxo = utxo_index.get(utxo_id)

            if previous_utxo is None:
                # Live windows often omit the parent transaction. Use the
                # prevout metadata supplied by Esplora as an external input
                # node so the selected transaction still shows all inputs.
                prevout = tx_input.get("prevout", {})
                previous_utxo = {
                    "id": utxo_id,
                    "type": "utxo",
                    "txid": tx_input["prev_txid"],
                    "vout": tx_input["prev_vout"],
                    "address": prevout.get("address", "external input"),
                    "value_btc": prevout.get("value_btc", 0),
                    "spent_by": None,
                    "external": True,
                }
                nodes.append(previous_utxo)
                utxo_index[utxo_id] = previous_utxo

            previous_utxo["spent_by"] = transaction["txid"]

            edges.append(
                {
                    "id": f"spends:{utxo_id}:{transaction['txid']}",
                    "source": utxo_id,
                    "target": current_tx_node_id,
                    "type": "spends"
                }
            )

    return {
        "metadata": {
            "transaction_count": len(transactions),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "reused_address_count": reused_address_count
        },
        "nodes": nodes,
        "edges": edges
    }


def main() -> None:
    with INPUT_FILE.open("r", encoding="utf-8") as file:
        source_data = json.load(file)

    graph = build_utxo_graph(source_data["transactions"])

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(graph, file, indent=2, ensure_ascii=False)

    print("UTXO 图数据已生成：")
    print(f"交易数：{graph['metadata']['transaction_count']}")
    print(f"节点数：{graph['metadata']['node_count']}")
    print(f"边数：{graph['metadata']['edge_count']}")
    print(f"输出文件：{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
