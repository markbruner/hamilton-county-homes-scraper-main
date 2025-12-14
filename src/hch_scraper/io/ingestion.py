from __future__ import annotations

from typing import List

import pandas as pd
from supabase import Client

from hch_scraper.loaders.supabase_loader import make_record_key, make_row_hash


def upsert_sales_raw(
    df: pd.DataFrame,
    *,
    supabase: Client,
    schema_name: str = "raw",
    table_name: str = "sales_hamilton",
    batch_size: int = 500,
) -> int:
    """
    Upsert cleaned sales data into the Supabase raw.sales_hamilton table.

    Args:
        df: Cleaned pandas DataFrame with columns like:
            Parcel Number, Address, BBB, FinSqFt, Use, Year Built,
            Transfer Date, Amount.
        supabase: An authenticated Supabase Client (service-role).
        table_name: Target table, including schema if used.
                    Default: 'raw.sales_hamilton'.
        batch_size: Number of rows per upsert batch (to avoid huge payloads).

    Returns:
        Total number of rows attempted to upsert.
    """
    if df.empty:
        return 0

    df = df.drop_duplicates().loc[lambda d: d["parcel_number"].notna()]
    df.columns = df.columns.str.lower()

    records: List[dict] = df.to_dict(orient="records")
    print(records[0])
    total = 0
    for r in records:
        r["record_key"] = make_record_key(r)
        r["row_hash"] = make_row_hash(r)
        response = supabase.rpc("upsert_sales_hamilton_one", {"p": r}).execute()

        # Optionally check for errors
        if getattr(response, "error", None):
            # You can swap print for logging here
            raise RuntimeError(f"Supabase upsert error: {response.error}")

        total += 1

    return total
