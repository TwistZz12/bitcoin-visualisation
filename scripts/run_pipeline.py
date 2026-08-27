"""Run the complete ChainScope analysis pipeline.

This is the single reproducible entry point used to turn a transaction fixture
into the graph and anomaly datasets consumed by the application.
"""

import json
import os
from pathlib import Path

from build_utxo_graph import build_utxo_graph
from address_labels import load_address_labels
from detect_patterns import detect_anomalies
from normalize_transactions import normalize_transactions


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "fixtures" / "worm_cluster_transactions.json"
GRAPH_OUTPUT = PROJECT_ROOT / "public" / "data" / "demo_utxo_graph.json"
ANOMALY_OUTPUT = PROJECT_ROOT / "public" / "data" / "anomaly_clusters.json"


def run_pipeline(input_file: Path | None = None) -> dict:
    """Analyse *input_file* and persist both public datasets."""
    if input_file is None:
        configured = os.getenv("CHAINSCOPE_DATASET")
        input_file = Path(configured) if configured else DEFAULT_INPUT
        if not input_file.is_absolute():
            input_file = PROJECT_ROOT / input_file
    with input_file.open("r", encoding="utf-8") as file:
        source_data = json.load(file)

    transactions = normalize_transactions(source_data)
    address_labels = load_address_labels()

    graph = build_utxo_graph(transactions, address_labels)
    anomalies = detect_anomalies(transactions, address_labels)
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
