"""Fetch a reproducible Bitcoin investigation case from a public Esplora API.

The script deliberately stores provenance alongside raw chain data. Address
labels identify an investigative starting point; they do not establish that
every connected transaction is illicit.
"""

import argparse
import json
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API = "https://blockstream.info/api"
DEFAULT_TXID = "2c7c8a02eaed1e4118ce665aa50f15397a86777f2081966414d76082057c9682"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "fixtures" / "real_blockstream_case.json"


def fetch_transaction(api_base: str, txid: str) -> dict:
    request = Request(f"{api_base.rstrip('/')}/tx/{txid}", headers={"User-Agent": "ChainScope/1.0"})
    # macOS Python installations sometimes do not inherit the system CA path.
    context = ssl.create_default_context()
    system_ca = Path("/etc/ssl/cert.pem")
    if system_ca.is_file():
        context = ssl.create_default_context(cafile=str(system_ca))
    with urlopen(request, timeout=20, context=context) as response:
        return json.load(response)


def build_case(
    txid: str = DEFAULT_TXID,
    api_base: str = DEFAULT_API,
    case_id: str = "real-blockstream-case",
    title: str = "Real Bitcoin transaction with one-hop context",
    source_type: str = "public-blockchain-data",
    source_url: str = "https://blockstream.info/",
    seed_address: str | None = None,
    confidence: str = "On-chain record",
) -> dict:
    target = fetch_transaction(api_base, txid)
    transactions = []
    parent_ids = {item["txid"] for item in target.get("vin", []) if item.get("txid")}
    for parent_id in sorted(parent_ids):
        transactions.append(fetch_transaction(api_base, parent_id))
    transactions.append(target)
    return {
        "metadata": {
            "case_id": case_id,
            "title": title,
            "description": "One real Bitcoin mainnet transaction with one-hop parent context",
            "network": "bitcoin-mainnet",
            "source_api": api_base,
            "source_type": source_type,
            "source_url": source_url,
            "seed_address": seed_address,
            "confidence": confidence,
            "interpretation": "The seed label is an investigative lead and does not attribute all connected transactions.",
            "target_txid": txid,
            "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "transaction_count": len(transactions),
        },
        "transactions": transactions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--txid", default=DEFAULT_TXID)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case-id", default="real-blockstream-case")
    parser.add_argument("--title", default="Real Bitcoin transaction with one-hop context")
    parser.add_argument("--source-type", default="public-blockchain-data")
    parser.add_argument("--source-url", default="https://blockstream.info/")
    parser.add_argument("--seed-address")
    parser.add_argument("--confidence", default="On-chain record")
    args = parser.parse_args()
    case = build_case(
        txid=args.txid,
        api_base=args.api,
        case_id=args.case_id,
        title=args.title,
        source_type=args.source_type,
        source_url=args.source_url,
        seed_address=args.seed_address,
        confidence=args.confidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(case, indent=2), encoding="utf-8")
    print(f"Saved {case['metadata']['transaction_count']} transactions to {args.output}")


if __name__ == "__main__":
    main()
