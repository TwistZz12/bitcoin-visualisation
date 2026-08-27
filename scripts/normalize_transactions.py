"""Normalize common Bitcoin transaction API responses to ChainScope's schema."""

from datetime import datetime, timezone


def _timestamp(transaction: dict) -> str:
    value = transaction.get("timestamp")
    if value:
        return value
    block_time = transaction.get("status", {}).get("block_time")
    if block_time is None:
        raise ValueError(f"Transaction {transaction.get('txid', '<unknown>')} has no timestamp")
    return datetime.fromtimestamp(block_time, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _value_btc(output: dict) -> float:
    if "value_btc" in output:
        return float(output["value_btc"])
    if "value" in output:
        return float(output["value"]) / 100_000_000
    raise ValueError("Output is missing value_btc or satoshi value")


def normalize_transaction(transaction: dict) -> dict:
    """Convert one internal or Blockstream-style transaction object."""
    txid = transaction.get("txid") or transaction.get("id")
    if not txid:
        raise ValueError("Transaction is missing txid")

    inputs = []
    for tx_input in transaction.get("inputs", transaction.get("vin", [])):
        prev_txid = tx_input.get("prev_txid") or tx_input.get("txid")
        prev_vout = tx_input.get("prev_vout", tx_input.get("vout"))
        if prev_txid is None or prev_vout is None:
            # Coinbase inputs do not spend a previous UTXO.
            continue
        normalized_input = {"prev_txid": prev_txid, "prev_vout": int(prev_vout)}
        prevout = tx_input.get("prevout")
        if isinstance(prevout, dict):
            normalized_input["prevout"] = {
                "address": prevout.get("scriptpubkey_address") or prevout.get("address"),
                "value_btc": _value_btc(prevout),
            }
        inputs.append(normalized_input)

    outputs = []
    for index, output in enumerate(transaction.get("outputs", transaction.get("vout", []))):
        vout = int(output.get("vout", index))
        address = (
            output.get("address")
            or output.get("scriptpubkey_address")
            or output.get("scriptpubkey", "")
            or f"unknown:{txid}:{vout}"
        )
        outputs.append({"vout": vout, "address": address, "value_btc": _value_btc(output)})

    return {
        "txid": txid,
        "timestamp": _timestamp(transaction),
        "block_height": int(transaction.get("block_height") or transaction.get("status", {}).get("block_height") or 0),
        "mempool": bool(transaction.get("mempool", False)),
        "inputs": inputs,
        "outputs": outputs,
    }


def normalize_transactions(source_data: dict | list[dict]) -> list[dict]:
    """Normalize an object containing ``transactions`` or a raw transaction list."""
    raw_transactions = source_data if isinstance(source_data, list) else source_data.get("transactions")
    if not isinstance(raw_transactions, list) or not raw_transactions:
        raise ValueError("Input data must contain a non-empty 'transactions' list")
    return [normalize_transaction(transaction) for transaction in raw_transactions]
