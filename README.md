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
- `GET /api/graph`
- `GET /api/anomalies?min_risk=65`
- `GET /api/anomalies/{cluster_id}`
- `GET /api/transactions/{txid}`

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

To switch the Python API to another transaction dataset, set
`CHAINSCOPE_DATASET` to a JSON file containing a `transactions` array before
starting Uvicorn.

The loader accepts both ChainScope's normalized schema and common Bitcoin API
objects with `vin`, `vout`, and `status.block_time` fields. Satoshi output
values are converted to BTC and API addresses are mapped to the graph schema
before anomaly detection runs. `data/fixtures/bitcoin_api_sample.json` shows
the supported API-style format.
