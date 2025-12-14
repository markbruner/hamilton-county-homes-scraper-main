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
        _get(row, "address"),
        _get(row, "bbb"),
        _get(row, "finsqft"),
        _get(row, "use"),
        _get(row, "year_built"),
        _get(row, "transfer_date"),
        _get(row, "amount"),
        _get(row, "recipient"),
        _get(row, "addressnumber"),
        _get(row, "addressnumberlow"),
        _get(row, "addressnumberhigh"),
        _get(row, "addressnumberprefix"),
        _get(row, "addressnumbersuffix"),
        _get(row, "streetname"),
        _get(row, "streetnamepredirectional"),
        _get(row, "streetnamepremodifier"),
        _get(row, "streetnamepretype"),
        _get(row, "streetnamepostdirectional"),
        _get(row, "streetnamepostmodifier"),
        _get(row, "streetnameposttype"),
        _get(row, "cornerof"),
        _get(row, "intersectionseparator"),
        _get(row, "landmarkname"),
        _get(row, "uspsboxgroupid"),
        _get(row, "uspsboxgrouptype"),
        _get(row, "uspsuspsboxid"),
        _get(row, "uspsboxtype"),
        _get(row, "buildingname"),
        _get(row, "occupancytype"),
        _get(row, "occupancyidentifier"),
        _get(row, "subaddressidentifier"),
        _get(row, "subaddresstype"),
        _get(row, "placename"),
        _get(row, "statename"),
        _get(row, "addresstype"),
    ]
    return sha256("|".join(parts).encode("utf-8")).hexdigest()
