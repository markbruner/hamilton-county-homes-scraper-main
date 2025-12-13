from hashlib import sha256

def _get(row: dict, *keys: str) -> str:
    """Return the first present non-null value among keys as a stripped string."""
    for k in keys:
        v = row.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""

def make_record_key(row: dict) -> str:
    # Adjust these keys to match your DF columns
    parcel = _get(row, "parcel_number")
    transfer_date = _get(row, "transfer_date")

    parts = [parcel, transfer_date]
    return sha256("|".join(parts).encode("utf-8")).hexdigest()

def make_row_hash(row: dict) -> str:
    parts = [
        _get(row, "parcel_number"),
        _get(row, "transfer_date"),
        _get(row, "amount"),
        _get(row, "address"),
        _get(row, "use"),
        _get(row, "finsqft"),
        _get(row, "year_built"),
    ]
    return sha256("|".join(parts).encode("utf-8")).hexdigest()