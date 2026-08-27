"""Small FastAPI service for the ChainScope transaction analysis pipeline.

Run with:
    uvicorn backend.api:app --reload --port 8000
"""

import json
import os
import ssl
import sys
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = PROJECT_ROOT / "data" / "fixtures" / "worm_cluster_transactions.json"
DATASET_DIR = PROJECT_ROOT / "data" / "fixtures"
ESPLORA_API = os.getenv("CHAINSCOPE_ESPLORA_API", "https://blockstream.info/api")
LIVE_WINDOW_CACHE: dict[tuple[str, int, int, tuple[str, ...]], dict] = {}
MEMPOOL_HISTORY: dict[str, dict] = {}
MEMPOOL_RETENTION = timedelta(minutes=15)

# The existing pure analysis functions remain the source of truth for both the
# CLI pipeline and this HTTP service.
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from build_utxo_graph import build_utxo_graph  # noqa: E402
from address_labels import load_address_labels  # noqa: E402
from detect_patterns import detect_anomalies  # noqa: E402
from normalize_transactions import normalize_transactions  # noqa: E402


@lru_cache(maxsize=8)
def load_analysis(dataset: str | None = None) -> tuple[list[dict], dict, list[dict]]:
    """Load and analyse a selected dataset once per API process."""
    source_path = dataset_path(dataset)
    with source_path.open("r", encoding="utf-8") as file:
        transactions = normalize_transactions(json.load(file))
    address_labels = load_address_labels()
    return transactions, build_utxo_graph(transactions, address_labels), detect_anomalies(transactions, address_labels)


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


def build_live_overview(blocks: list[dict], transactions_by_block: list[list[dict]], anomalies: list[dict]) -> list[dict]:
    """Summarize risk events per block for the overview layer."""
    risk_by_txid = {
        txid: anomaly["risk_score"]
        for anomaly in anomalies
        for txid in anomaly["transactions"]
    }
    overview = []
    for block, block_transactions in zip(blocks, transactions_by_block, strict=True):
        scores = [risk_by_txid[transaction["txid"]] for transaction in block_transactions if transaction["txid"] in risk_by_txid]
        overview.append({
            "height": block.get("height"),
            "timestamp": block.get("timestamp"),
            "transaction_count": len(block_transactions),
            "anomaly_count": len(scores),
            "max_risk": max(scores, default=0),
        })
    return list(reversed(overview))


def fetch_mempool_window(limit: int) -> tuple[list[dict], tuple[str, ...], str]:
    """Retain recent unconfirmed transactions long enough to expose dependencies."""
    try:
        recent = fetch_esplora_json("mempool/recent")
    except Exception:
        # Mempool is volatile and public API requests can be rate-limited.
        # Confirmed-block analysis remains useful when this optional source fails.
        return [record["transaction"] for record in MEMPOOL_HISTORY.values()], (), "unavailable"
    if not isinstance(recent, list):
        return [record["transaction"] for record in MEMPOOL_HISTORY.values()], (), "unavailable"
    txids = tuple(item["txid"] for item in recent[:limit] if isinstance(item, dict) and item.get("txid"))
    now = datetime.now(timezone.utc)
    for txid in txids:
        if txid not in MEMPOOL_HISTORY:
            try:
                raw_transaction = fetch_esplora_json(f"tx/{txid}")
            except Exception:
                continue
            if not isinstance(raw_transaction, dict):
                continue
            raw_transaction["mempool"] = True
            raw_transaction["timestamp"] = now.isoformat().replace("+00:00", "Z")
            MEMPOOL_HISTORY[txid] = {"transaction": raw_transaction, "observed_at": now}
    for txid, record in list(MEMPOOL_HISTORY.items()):
        if now - record["observed_at"] > MEMPOOL_RETENTION:
            del MEMPOOL_HISTORY[txid]
    return [record["transaction"] for record in MEMPOOL_HISTORY.values()], txids, "available"


def fetch_live_analysis(window_blocks: int, transactions_per_block: int, mempool_transactions: int) -> dict:
    """Build a cached rolling window of confirmed blocks plus recent mempool context."""
    tip_hash = str(fetch_esplora_json("blocks/tip/hash"))
    raw_mempool_transactions, mempool_txids, mempool_status = fetch_mempool_window(mempool_transactions)
    cache_key = (tip_hash, window_blocks, transactions_per_block, mempool_txids)
    if cache_key in LIVE_WINDOW_CACHE:
        cached = LIVE_WINDOW_CACHE[cache_key]
        cached["metadata"]["cache_hit"] = True
        return cached

    blocks = []
    raw_transactions_by_block = []
    current_hash = tip_hash
    for _ in range(window_blocks):
        block = fetch_esplora_json(f"block/{current_hash}")
        if not isinstance(block, dict):
            raise ValueError("Esplora returned an invalid block record")
        raw_transactions = fetch_esplora_json(f"block/{current_hash}/txs/0")
        if not isinstance(raw_transactions, list):
            raise ValueError("Esplora returned an invalid block transaction list")
        blocks.append(block)
        raw_transactions_by_block.append(raw_transactions[:transactions_per_block])
        previous_hash = block.get("previousblockhash")
        if not previous_hash:
            break
        current_hash = previous_hash

    transactions_by_block = [normalize_transactions(items) for items in raw_transactions_by_block]
    mempool = normalize_transactions(raw_mempool_transactions) if raw_mempool_transactions else []
    transactions = [transaction for items in transactions_by_block for transaction in items]
    transactions.extend(mempool)
    address_labels = load_address_labels()
    graph_data = build_utxo_graph(transactions, address_labels)
    detected = detect_anomalies(transactions, address_labels)
    result = {
        "metadata": {
            "dataset": "live-rolling-window",
            "dataset_type": "Bitcoin mainnet rolling window + mempool",
            "source_api": ESPLORA_API,
            "transaction_count": len(transactions),
            "anomaly_count": len(detected),
            "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "block_height": blocks[0].get("height"),
            "block_hash": tip_hash,
            "window_block_count": len(blocks),
            "transactions_per_block": transactions_per_block,
            "confirmed_transaction_count": len(transactions) - len(mempool),
            "mempool_transaction_count": len(mempool),
            "mempool_retention_minutes": int(MEMPOOL_RETENTION.total_seconds() / 60),
            "mempool_status": mempool_status,
            "cache_hit": False,
        },
        "overview": build_live_overview(blocks, transactions_by_block, detected),
        "graph": graph_data,
        "anomalies": detected,
        "transactions": transactions,
    }
    LIVE_WINDOW_CACHE.clear()
    LIVE_WINDOW_CACHE[cache_key] = result
    return result


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
    return {"enabled": True, "source_api": ESPLORA_API, "refresh_interval_seconds": 30, "window_blocks_default": 6, "transactions_per_block_default": 25, "mempool_transactions_default": 10, "mempool_retention_minutes": 15}


@app.get("/api/live/analysis")
def live_analysis(window_blocks: int = Query(6, ge=2, le=12), transactions_per_block: int = Query(25, ge=5, le=25), mempool_transactions: int = Query(10, ge=0, le=10)) -> dict:
    try:
        return fetch_live_analysis(window_blocks, transactions_per_block, mempool_transactions)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Unable to fetch live Bitcoin data: {error}") from error


@app.get("/api/live/transactions/{txid}")
def live_transaction(txid: str) -> dict:
    for snapshot in LIVE_WINDOW_CACHE.values():
        match = next((transaction for transaction in snapshot["transactions"] if transaction["txid"] == txid), None)
        if match is not None:
            return match
    raise HTTPException(status_code=404, detail="Transaction is not in the current live window")


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
