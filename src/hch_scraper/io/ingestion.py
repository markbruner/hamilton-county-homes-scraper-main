from __future__ import annotations

from typing import List

import pandas as pd
from supabase import Client


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

    records: List[dict] = df.to_dict(orient="records")

    # Insert in batches
    total = 0
    for start in range(0, len(records), batch_size):
        chunk = records[start : start + batch_size]

        # You can use insert or upsert, depending on whether you want de-duplication.
        # Here we use upsert; you must set a unique constraint on the table for it to work well.
        response = (
            supabase.schema(schema_name).table(table_name).upsert(chunk).execute()
        )

        # Optionally check for errors
        if getattr(response, "error", None):
            # You can swap print for logging here
            raise RuntimeError(f"Supabase upsert error: {response.error}")

        total += len(chunk)

    return total
