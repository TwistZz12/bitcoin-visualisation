"""Run the complete ChainScope analysis pipeline.

This is the single reproducible entry point used to turn a transaction fixture
into the graph and anomaly datasets consumed by the application.
"""

import json
from pathlib import Path

from build_utxo_graph import build_utxo_graph
from detect_patterns import detect_anomalies


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "fixtures" / "worm_cluster_transactions.json"
GRAPH_OUTPUT = PROJECT_ROOT / "public" / "data" / "demo_utxo_graph.json"
ANOMALY_OUTPUT = PROJECT_ROOT / "public" / "data" / "anomaly_clusters.json"


def run_pipeline(input_file: Path = DEFAULT_INPUT) -> dict:
    """Analyse *input_file* and persist both public datasets."""
    with input_file.open("r", encoding="utf-8") as file:
        source_data = json.load(file)

    transactions = source_data.get("transactions")
    if not isinstance(transactions, list) or not transactions:
        raise ValueError("Input data must contain a non-empty 'transactions' list")

    graph = build_utxo_graph(transactions)
    anomalies = detect_anomalies(transactions)
    anomaly_data = {
        "metadata": {
            "source_transaction_count": len(transactions),
            "anomaly_count": len(anomalies),
            "source_file": input_file.name,
            "detector_version": "chainscope-pipeline-v1",
        },
        "anomalies": anomalies,
    }

    GRAPH_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_OUTPUT.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    ANOMALY_OUTPUT.write_text(json.dumps(anomaly_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"graph": graph, "anomalies": anomaly_data}


def main() -> None:
    result = run_pipeline()
    print(
        f"ChainScope pipeline complete: {result['graph']['metadata']['transaction_count']} transactions, "
        f"{result['anomalies']['metadata']['anomaly_count']} anomaly clusters"
    )
    print(f"Graph: {GRAPH_OUTPUT}")
    print(f"Anomalies: {ANOMALY_OUTPUT}")


if __name__ == "__main__":
    main()
