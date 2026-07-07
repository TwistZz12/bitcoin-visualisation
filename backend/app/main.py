from fastapi import FastAPI, HTTPException
from httpx import HTTPError

from app.database.connection import initialise_database
from app.services.mempool import fetch_recent_transactions
from app.database.transactions import get_fee_rate_anomalies,get_transaction_stats, save_transactions

app = FastAPI(
    title="Bitcoin Anomaly Detection API",
    version="0.1.0",
)

initialise_database()

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/transactions/recent")
async def recent_transactions():
    try:
        transactions = await fetch_recent_transactions()
        save_transactions(transactions)
        return transactions
    except HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve Bitcoin transactions.",
        ) from error
    
@app.get("/transactions/stats")
def transaction_stats():
    return get_transaction_stats()    

@app.get("/transactions/anomalies")
def transaction_anomalies():
    return get_fee_rate_anomalies()