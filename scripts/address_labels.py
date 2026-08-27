"""Load local address-intelligence labels without coupling detection to a vendor."""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LABEL_FILE = PROJECT_ROOT / "data" / "fixtures" / "address_labels.json"


def load_address_labels(label_file: Path = DEFAULT_LABEL_FILE) -> dict[str, dict]:
    """Return labels indexed by address; malformed entries are ignored."""
    if not label_file.is_file():
        return {}
    data = json.loads(label_file.read_text(encoding="utf-8"))
    return {
        entry["address"]: {
            "entity": entry["entity"],
            "category": entry["category"],
            "confidence": entry.get("confidence", "Unspecified"),
        }
        for entry in data.get("labels", [])
        if all(entry.get(key) for key in ("address", "entity", "category"))
    }
