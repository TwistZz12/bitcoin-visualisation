"""Small FastAPI service for the ChainScope transaction analysis pipeline.

Run with:
    uvicorn backend.api:app --reload --port 8000
"""

import json
import os
import ssl
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = PROJECT_ROOT / "data" / "fixtures" / "worm_cluster_transactions.json"
DATASET_DIR = PROJECT_ROOT / "data" / "fixtures"
ESPLORA_API = os.getenv("CHAINSCOPE_ESPLORA_API", "https://blockstream.info/api")

# The existing pure analysis functions remain the source of truth for both the
# CLI pipeline and this HTTP service.
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from build_utxo_graph import build_utxo_graph  # noqa: E402
from detect_patterns import detect_anomalies  # noqa: E402
from normalize_transactions import normalize_transactions  # noqa: E402


@lru_cache(maxsize=8)
def load_analysis(dataset: str | None = None) -> tuple[list[dict], dict, list[dict]]:
    """Load and analyse a selected dataset once per API process."""
    source_path = dataset_path(dataset)
    with source_path.open("r", encoding="utf-8") as file:
        transactions = normalize_transactions(json.load(file))
    return transactions, build_utxo_graph(transactions), detect_anomalies(transactions)


def dataset_path(dataset: str | None = None) -> Path:
    """Resolve the configured dataset without allowing an empty path."""
    configured = dataset or os.getenv("CHAINSCOPE_DATASET", str(DEFAULT_DATASET))
    path = Path(configured)
    if not path.is_absolute():
        path = DATASET_DIR / path if dataset else PROJECT_ROOT / path
    if dataset and (path.parent != DATASET_DIR or path.suffix.lower() != ".json"):
        raise HTTPException(status_code=400, detail="dataset must be a JSON file in data/fixtures")
    if not path.is_file():
        raise FileNotFoundError(f"Configured dataset does not exist: {path}")
    return path


def fetch_esplora_json(path: str) -> object:
    request = Request(f"{ESPLORA_API.rstrip('/')}/{path.lstrip('/')}", headers={"User-Agent": "ChainScope/1.0"})
    context = ssl.create_default_context()
    system_ca = Path("/etc/ssl/cert.pem")
    if system_ca.is_file():
        context = ssl.create_default_context(cafile=str(system_ca))
    with urlopen(request, timeout=20, context=context) as response:
        payload = response.read().decode("utf-8")
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload.strip()


def fetch_live_analysis(limit: int) -> dict:
    block_hash = str(fetch_esplora_json("blocks/tip/hash"))
    block = fetch_esplora_json(f"block/{block_hash}")
    txids = fetch_esplora_json(f"block/{block_hash}/txids")
    raw_transactions = [fetch_esplora_json(f"tx/{txid}") for txid in list(txids)[:limit]]
    transactions = normalize_transactions(raw_transactions)
    graph_data = build_utxo_graph(transactions)
    detected = detect_anomalies(transactions)
    return {
        "metadata": {
            "dataset": "live-block",
            "dataset_type": "Bitcoin mainnet live block",
            "source_api": ESPLORA_API,
            "transaction_count": len(transactions),
            "anomaly_count": len(detected),
            "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "block_height": block.get("height"),
            "block_hash": block_hash,
            "block_timestamp": block.get("timestamp"),
        },
        "block": block,
        "graph": graph_data,
        "anomalies": detected,
    }


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
def metadata(dataset: str | None = Query(None)) -> dict:
    transactions, graph_data, detected = load_analysis(dataset)
    return {
        "service": "chainscope-analysis",
        "api_version": app.version,
        "dataset": dataset_path(dataset).name,
        "dataset_type": "Synthetic demo dataset" if "worm" in dataset_path(dataset).name or "demo" in dataset_path(dataset).name else "Bitcoin transaction dataset",
        "transaction_count": len(transactions),
        "anomaly_count": len(detected),
        "graph_node_count": graph_data["metadata"]["node_count"],
        "analysis_cached": True,
    }


@app.get("/api/datasets")
def datasets() -> dict:
    available = []
    for path in sorted(DATASET_DIR.glob("*.json")):
        try:
            transactions, _, detected = load_analysis(path.name)
            available.append({"name": path.name, "transaction_count": len(transactions), "anomaly_count": len(detected)})
        except (ValueError, KeyError):
            continue
    return {"datasets": available, "selected": dataset_path().name}


@app.get("/api/live/status")
def live_status() -> dict:
    return {"enabled": True, "source_api": ESPLORA_API, "refresh_interval_seconds": 30, "limit_default": 10}


@app.get("/api/live/analysis")
def live_analysis(limit: int = Query(10, ge=1, le=20)) -> dict:
    try:
        return fetch_live_analysis(limit)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Unable to fetch live Bitcoin data: {error}") from error


@app.get("/api/graph")
def graph(dataset: str | None = Query(None)) -> dict:
    return load_analysis(dataset)[1]


@app.get("/api/anomalies")
def anomalies(min_risk: int = Query(0, ge=0, le=100), dataset: str | None = Query(None)) -> dict:
    transactions, _, detected = load_analysis(dataset)
    filtered = [item for item in detected if item["risk_score"] >= min_risk]
    return {
        "metadata": {
            "source_transaction_count": len(transactions),
            "anomaly_count": len(filtered),
            "detector_version": "chainscope-pipeline-v1",
            "source": dataset_path(dataset).name,
            "analysis_cached": True,
        },
        "anomalies": filtered,
    }


@app.get("/api/anomalies/{cluster_id}")
def anomaly(cluster_id: str, dataset: str | None = Query(None)) -> dict:
    match = next((item for item in load_analysis(dataset)[2] if item["id"] == cluster_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Anomaly cluster not found")
    return match


@app.get("/api/transactions/{txid}")
def transaction(txid: str, dataset: str | None = Query(None)) -> dict:
    match = next((item for item in load_analysis(dataset)[0] if item["txid"] == txid), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return match
