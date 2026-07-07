import httpx

MEMPOOL_RECENT_URL = "https://mempool.space/api/mempool/recent"


async def fetch_recent_transactions():
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(MEMPOOL_RECENT_URL)
        response.raise_for_status()
        transactions = response.json()

    for transaction in transactions:
        vsize = transaction.get("vsize", 0)
        transaction["fee_rate"] = (
            round(transaction["fee"] / vsize, 2) if vsize else 0
        )

    return transactions