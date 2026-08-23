"""Small FastAPI service for the ChainScope transaction analysis pipeline.

Run with:
    uvicorn backend.api:app --reload --port 8000
"""

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = PROJECT_ROOT / "data" / "fixtures" / "worm_cluster_transactions.json"

# The existing pure analysis functions remain the source of truth for both the
# CLI pipeline and this HTTP service.
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from build_utxo_graph import build_utxo_graph  # noqa: E402
from detect_patterns import detect_anomalies  # noqa: E402


@lru_cache(maxsize=1)
def load_analysis() -> tuple[list[dict], dict, list[dict]]:
    """Load and analyse the fixture once per API process."""
    dataset = dataset_path()
    with dataset.open("r", encoding="utf-8") as file:
        transactions = json.load(file)["transactions"]
    return transactions, build_utxo_graph(transactions), detect_anomalies(transactions)


def dataset_path() -> Path:
    """Resolve the configured dataset without allowing an empty path."""
    configured = os.getenv("CHAINSCOPE_DATASET", str(DEFAULT_DATASET))
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.is_file():
        raise FileNotFoundError(f"Configured dataset does not exist: {path}")
    return path


app = FastAPI(title="ChainScope Analysis API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    """Provide a discoverable landing response for the API service."""
    return {
        "service": "ChainScope Analysis API",
        "status": "ok",
        "docs": "/docs",
        "dataset": dataset_path().name,
        "endpoints": ["/api/health", "/api/metadata", "/api/graph", "/api/anomalies"],
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "chainscope-analysis", "version": app.version, "analysis_cached": True, "dataset": dataset_path().name}


@app.get("/api/metadata")
def metadata() -> dict:
    transactions, graph_data, detected = load_analysis()
    return {
        "service": "chainscope-analysis",
        "api_version": app.version,
        "dataset": dataset_path().name,
        "dataset_type": "Synthetic demo dataset" if "fixture" in str(dataset_path()) else "Configured transaction dataset",
        "transaction_count": len(transactions),
        "anomaly_count": len(detected),
        "graph_node_count": graph_data["metadata"]["node_count"],
        "analysis_cached": True,
    }


@app.get("/api/graph")
def graph() -> dict:
    return load_analysis()[1]


@app.get("/api/anomalies")
def anomalies(min_risk: int = Query(0, ge=0, le=100)) -> dict:
    transactions, _, detected = load_analysis()
    filtered = [item for item in detected if item["risk_score"] >= min_risk]
    return {
        "metadata": {
            "source_transaction_count": len(transactions),
            "anomaly_count": len(filtered),
            "detector_version": "chainscope-pipeline-v1",
            "source": dataset_path().name,
            "analysis_cached": True,
        },
        "anomalies": filtered,
    }


@app.get("/api/anomalies/{cluster_id}")
def anomaly(cluster_id: str) -> dict:
    match = next((item for item in load_analysis()[2] if item["id"] == cluster_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Anomaly cluster not found")
    return match


@app.get("/api/transactions/{txid}")
def transaction(txid: str) -> dict:
    match = next((item for item in load_analysis()[0] if item["txid"] == txid), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return match
