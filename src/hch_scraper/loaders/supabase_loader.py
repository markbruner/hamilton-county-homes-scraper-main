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
    finsqft = _get(row, "finsqft")  
    year_built = _get(row, "year_built") 
    amount = _get(row, "amount") 

    parts = [parcel, transfer_date, finsqft, year_built, amount]
    return sha256("|".join(parts).encode("utf-8")).hexdigest()