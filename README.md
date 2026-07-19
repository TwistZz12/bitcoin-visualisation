# Bitcoin Realtime Visualisation and Anomaly Detection

A real-time dashboard for monitoring recent Bitcoin mempool transactions and identifying statistically unusual transactions.

## Project Overview

The system retrieves recent unconfirmed Bitcoin transactions from the mempool.space API. A FastAPI backend calculates transaction features, stores observations in SQLite, and provides REST API endpoints. A React frontend visualises transaction activity and detected anomalies.

The dashboard refreshes automatically every 10 seconds.

## Current Features

- Retrieves recent Bitcoin mempool transactions from mempool.space
- Calculates transaction fee rate in sat/vB
- Stores unique transactions in a SQLite database
- Displays transaction statistics, including average and maximum fee rate
- Visualises recent transaction fee rates in a line chart
- Detects anomalies using a multi-feature Median/MAD method
- Uses fee rate, transaction value, and virtual transaction size as anomaly features
- Explains why each detected transaction was flagged
- Refreshes dashboard data automatically every 10 seconds

## Anomaly Detection

The current baseline uses Median and Median Absolute Deviation (MAD), a robust statistical method that is less affected by extreme values than a mean-based threshold.

For each transaction, the system calculates robust anomaly scores for:

- Fee rate
- Transaction value
- Virtual size

A transaction is flagged when one or more feature scores exceed the configured threshold of 3.5. The dashboard displays the reason, such as an unusually high fee rate or transaction value.

This system identifies statistical anomalies, not confirmed illicit transactions.

## Technology Stack

- Frontend: React, JavaScript, Vite, Recharts, CSS
- Backend: Python, FastAPI, Uvicorn, httpx
- Database: SQLite
- External data source: mempool.space API

## System Architecture

```text
mempool.space API
        ↓
FastAPI backend
        ↓
SQLite storage and anomaly detection
        ↓
REST API endpoints
        ↓
React dashboard and visualisations
```

## API Endpoints

- `GET /health` - checks that the backend is running
- `GET /transactions/recent` - retrieves recent transactions and stores new records
- `GET /transactions/stats` - returns transaction statistics
- `GET /transactions/anomalies` - returns detected anomalies and explanations

## Run Locally

### Backend

```bash
source backend/.venv/bin/activate
python -m uvicorn app.main:app --reload --app-dir backend
```

The backend runs at `http://127.0.0.1:8000`.

### Frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in a browser.

## Future Work

- Compare the Median/MAD baseline with Isolation Forest
- Collect a larger historical dataset for experiments
- Add temporal and graph-based transaction features
- Evaluate detection results using labelled datasets such as Elliptic
- Improve visualisations and add a formal experimental evaluation