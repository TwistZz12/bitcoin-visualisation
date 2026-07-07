from fastapi import FastAPI, HTTPException
from httpx import HTTPError

from app.services.mempool import fetch_recent_transactions

app = FastAPI(
    title="Bitcoin Anomaly Detection API",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/transactions/recent")
async def recent_transactions():
    try:
        return await fetch_recent_transactions()
    except HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve Bitcoin transactions.",
        ) from error