"""Small FastAPI service for the ChainScope transaction analysis pipeline.

Run with:
    uvicorn backend.api:app --reload --port 8000
"""

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = PROJECT_ROOT / "data" / "fixtures" / "worm_cluster_transactions.json"

# The existing pure analysis functions remain the source of truth for both the
# CLI pipeline and this HTTP service.
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from build_utxo_graph import build_utxo_graph  # noqa: E402
from detect_patterns import detect_anomalies  # noqa: E402


def load_analysis() -> tuple[dict, list[dict], list[dict]]:
    with FIXTURE.open("r", encoding="utf-8") as file:
        transactions = json.load(file)["transactions"]
    return transactions, build_utxo_graph(transactions), detect_anomalies(transactions)


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
        "endpoints": ["/api/health", "/api/graph", "/api/anomalies"],
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "chainscope-analysis", "version": app.version}


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
