# ChainScope

ChainScope is a Bitcoin transaction graph explorer for explainable anomaly
detection. The Python pipeline builds a Transaction → UTXO → Transaction graph,
detects Collection, Split and high-frequency Worm patterns, and exposes the
results to the Next.js visualisation.

## Run the demo

```bash
npm install
npm run data:pipeline
npm run dev
```

The web app uses the local Next.js routes (`/api/graph` and `/api/anomalies`)
by default. These routes read the reproducible datasets in `public/data`.
When `NEXT_PUBLIC_ANALYSIS_API_URL` is set, the dataset selector in the header
uses the standalone FastAPI service and reloads the selected fixture.

## Run the Python analysis API

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm run data:pipeline
npm run backend:dev
```

The FastAPI service is available at `http://localhost:8000`. Set
`NEXT_PUBLIC_ANALYSIS_API_URL=http://localhost:8000` before starting Next.js to
make the UI consume the standalone Python service instead of its local routes.

Useful endpoints:

- `GET /api/health`
- `GET /api/metadata`
- `GET /api/datasets`
- `GET /api/graph`
- `GET /api/anomalies?min_risk=65`
- `GET /api/anomalies/{cluster_id}`
- `GET /api/transactions/{txid}`
- `GET /api/live/status`
- `GET /api/live/analysis?window_blocks=6&transactions_per_block=25&mempool_transactions=10`
- `GET /api/live/transactions/{txid}`

## Data flow

```text
data/fixtures/*.json
        ↓  npm run data:pipeline
scripts/run_pipeline.py
        ├── public/data/demo_utxo_graph.json
        └── public/data/anomaly_clusters.json
        ↓
Next.js API routes or backend/api.py
        ↓
app/page.tsx + app/TransactionGraph.tsx
```

The generated data is deterministic, so the same input produces the same
graph and anomaly scores. This makes the synthetic Worm scenario suitable for
testing and demonstrations while the API boundary is ready for real Bitcoin
transaction data later.

Live mode uses the public Bitcoin Esplora endpoints to analyse a rolling
window of consecutive blocks. By default it samples the first 25 transactions
from each of the latest 6 blocks (up to 150 confirmed transactions) and the
10 most recently observed mempool transactions. Mempool transactions are kept
for 15 minutes in process memory so dependencies seen across refreshes can be
analysed together. The UI refreshes at most every 30 seconds. Mempool timestamps
are observation times, not claimed broadcast times, and any resulting Worm
signal is therefore an investigative lead rather than a final attribution.

To switch the Python API to another transaction dataset, set
`CHAINSCOPE_DATASET` to a JSON file containing a `transactions` array before
starting Uvicorn.

The loader accepts both ChainScope's normalized schema and common Bitcoin API
objects with `vin`, `vout`, and `status.block_time` fields. Satoshi output
values are converted to BTC and API addresses are mapped to the graph schema
before anomaly detection runs. `data/fixtures/bitcoin_api_sample.json` shows
the supported API-style format.

## Address intelligence

`data/fixtures/address_labels.json` is a small, local address-label source.
Its labels are added to UTXO nodes and to the selected anomaly's explanatory
evidence. They are contextual information only: an `Exchange` label does not
by itself increase an anomaly score or establish illicit activity. The checked-in
`DemoExchange` label is synthetic and exists solely to demonstrate the feature;
the same schema can later be populated from a documented public or commercial
attribution source.

## Reproducible real-world cases

`data/fixtures/case_catalog.json` records the provenance of real-world case
fixtures. Each case stores a seed address or transaction, a source URL,
confidence statement, retrieval timestamp, and a limitation statement. The
included `ofac_cryptex_case.json` is a Bitcoin-mainnet context around a public
OFAC-listed Cryptex BTC address. It is an investigation case, not a claim that
all adjacent addresses are sanctioned or illicit.

Create another case with:

```bash
python3 scripts/fetch_esplora_case.py \
  --txid <transaction-id> \
  --case-id <case-id> \
  --title "Case title" \
  --source-type <source-category> \
  --source-url <provenance-url> \
  --seed-address <address> \
  --confidence "Source confidence" \
  --output data/fixtures/<case-id>.json
```

To reproduce the checked-in real-mainnet case from the public Blockstream
Esplora API, run:

```bash
python3 scripts/fetch_esplora_case.py
export CHAINSCOPE_DATASET=data/fixtures/real_blockstream_case.json
```

The case contains the target transaction plus one-hop parent context and stores
the source API, target txid, network, and retrieval timestamp in its metadata.
