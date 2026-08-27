import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_utxo_graph import build_utxo_graph
from address_labels import load_address_labels
from detect_patterns import detect_anomalies
from normalize_transactions import normalize_transactions


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = PROJECT_ROOT / "data" / "fixtures" / "worm_cluster_transactions.json"
        cls.transactions = json.loads(fixture.read_text(encoding="utf-8"))["transactions"]

    def test_graph_contains_real_utxo_spend_edges(self):
        graph = build_utxo_graph(self.transactions)
        self.assertEqual(graph["metadata"]["transaction_count"], 33)
        self.assertGreater(graph["metadata"]["edge_count"], 0)
        self.assertTrue(any(edge["type"] == "spends" for edge in graph["edges"]))

    def test_worm_detection_returns_explainable_cluster(self):
        anomalies = detect_anomalies(self.transactions)
        worms = [item for item in anomalies if item["pattern"] == "Worm"]
        self.assertEqual(len(worms), 1)
        worm = worms[0]
        self.assertEqual(worm["transaction_count"], 25)
        self.assertGreaterEqual(worm["risk_score"], 65)
        self.assertIn("avg_hop_seconds", worm["features"])
        self.assertEqual(len(worm["evidence"]), 5)

    def test_address_labels_enrich_worm_evidence_without_changing_detection_rule(self):
        labels = load_address_labels()
        worm = next(item for item in detect_anomalies(self.transactions, labels) if item["pattern"] == "Worm")
        self.assertEqual(worm["entity_labels"][0]["entity"], "DemoExchange")
        self.assertTrue(any("Exchange entity DemoExchange" in item for item in worm["evidence"]))

    def test_risk_scores_are_bounded(self):
        for anomaly in detect_anomalies(self.transactions):
            self.assertGreaterEqual(anomaly["risk_score"], 0)
            self.assertLessEqual(anomaly["risk_score"], 100)

    def test_blockstream_style_transactions_are_normalized(self):
        source = {
            "transactions": [{
                "txid": "api_tx_1",
                "status": {"block_height": 100, "block_time": 1716026400},
                "vin": [],
                "vout": [{"scriptpubkey_address": "bc1qexample", "value": 100000000}],
            }]
        }
        normalized = normalize_transactions(source)[0]
        self.assertEqual(normalized["outputs"][0]["value_btc"], 1.0)
        self.assertEqual(normalized["block_height"], 100)
        self.assertTrue(normalized["timestamp"].endswith("Z"))

    def test_checked_in_real_case_has_source_metadata(self):
        case = json.loads((PROJECT_ROOT / "data" / "fixtures" / "real_blockstream_case.json").read_text(encoding="utf-8"))
        self.assertEqual(case["metadata"]["network"], "bitcoin-mainnet")
        self.assertEqual(case["metadata"]["transaction_count"], 3)
        self.assertEqual(len(case["transactions"]), 3)

    def test_missing_parent_inputs_are_represented_as_external_utxos(self):
        source = {
            "transactions": [{
                "txid": "child",
                "timestamp": "2024-01-01T00:00:00Z",
                "block_height": 1,
                "inputs": [{"prev_txid": "parent", "prev_vout": 0, "prevout": {"address": "bc1qexternal", "value_btc": 0.5}}],
                "outputs": [{"vout": 0, "address": "bc1qrecipient", "value_btc": 0.49}],
            }]
        }
        graph = build_utxo_graph(source["transactions"])
        external = [node for node in graph["nodes"] if node.get("external")]
        self.assertEqual(len(external), 1)
        self.assertEqual(external[0]["value_btc"], 0.5)


if __name__ == "__main__":
    unittest.main()
