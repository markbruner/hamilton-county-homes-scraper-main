from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd

from hch_scraper.io.supabase_client import get_supabase_client
from hch_scraper.services.similarity import find_similar_properties, rank_similar_properties


DEFAULT_DATA_PATHS = (
    Path("data/processed/homes_geocoded.csv"),
    Path("data/processed/homes_all_patched.csv"),
)
STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
DEFAULT_SUPABASE_PAGE_SIZE = 1000
DEFAULT_SUPABASE_SCHEMA = "public"
DEFAULT_SUPABASE_TABLE = "sales_enriched_api"
DEFAULT_SUPABASE_CANDIDATE_LIMIT = 1500


def load_properties(
    data_path: str | Path | None = None,
    *,
    source: str = "csv",
    supabase_schema: str = DEFAULT_SUPABASE_SCHEMA,
    supabase_table: str = DEFAULT_SUPABASE_TABLE,
    supabase_page_size: int = DEFAULT_SUPABASE_PAGE_SIZE,
    supabase_key_type: str = "anon",
) -> pd.DataFrame:
    """Load the property dataset from CSV or Supabase for the demo server."""
    if source == "supabase":
        properties = load_properties_from_supabase(
            schema=supabase_schema,
            table=supabase_table,
            page_size=supabase_page_size,
            key_type=supabase_key_type,
        )
    else:
        resolved = _resolve_data_path(data_path)
        properties = pd.read_csv(resolved, low_memory=False)

    if "parcel_number" not in properties.columns:
        raise KeyError("Loaded property dataset is missing required column: parcel_number")

    properties["parcel_number"] = properties["parcel_number"].astype("string")
    return properties


def load_properties_from_supabase(
    *,
    schema: str = DEFAULT_SUPABASE_SCHEMA,
    table: str = DEFAULT_SUPABASE_TABLE,
    page_size: int = DEFAULT_SUPABASE_PAGE_SIZE,
    key_type: str = "anon",
) -> pd.DataFrame:
    """Fetch the full demo property dataset from Supabase in paged batches."""
    client = get_supabase_client(key_type=key_type)
    rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        response = (
            client.schema(schema)
            .table(table)
            .select("*")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = response.data or []
        if not batch:
            break

        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    return pd.DataFrame(rows)


def search_properties(
    properties: pd.DataFrame,
    query: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search local property records by parcel number or address text."""
    query = query.strip()
    if not query:
        return []

    normalized_query = query.upper()
    working = properties.copy()
    working["_parcel_text"] = working["parcel_number"].astype("string").str.upper()
    working["_address_text"] = (
        working.get("address", pd.Series(index=working.index, dtype="string"))
        .astype("string")
        .fillna("")
        .str.upper()
    )

    mask = working["_parcel_text"].str.contains(normalized_query, regex=False) | working[
        "_address_text"
    ].str.contains(normalized_query, regex=False)
    results = working.loc[mask].copy()
    if results.empty:
        return []

    results["_exact_parcel"] = results["_parcel_text"] == normalized_query
    results["_starts_address"] = results["_address_text"].str.startswith(normalized_query)
    results = results.sort_values(
        by=["_exact_parcel", "_starts_address", "_address_text"],
        ascending=[False, False, True],
    )

    payload = [_serialize_property_row(row) for _, row in results.head(limit).iterrows()]
    return payload


def build_similar_response(
    properties: pd.DataFrame,
    parcel_number: str,
    *,
    top_n: int = 8,
    min_score: float | None = 40.0,
    max_distance_miles: float | None = None,
) -> dict[str, Any]:
    """Return a subject property and its ranked local similarity matches."""
    matches = properties.loc[
        properties["parcel_number"].astype("string") == str(parcel_number)
    ]
    if matches.empty:
        raise KeyError(f"Parcel number not found: {parcel_number}")

    subject = matches.iloc[0]
    ranked = find_similar_properties(
        properties,
        parcel_number,
        top_n=top_n,
        min_score=min_score,
        max_distance_miles=max_distance_miles,
    )

    subject_payload = _serialize_property_row(subject)
    subject_payload["similarity_score"] = 100.0
    subject_payload["distance_miles"] = 0.0

    return {
        "subject": subject_payload,
        "similar": [_serialize_property_row(row) for _, row in ranked.iterrows()],
    }


def run_demo_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    data_path: str | Path | None = None,
    source: str = "csv",
    supabase_schema: str = DEFAULT_SUPABASE_SCHEMA,
    supabase_table: str = DEFAULT_SUPABASE_TABLE,
    supabase_key_type: str = "anon",
) -> None:
    """Start the HTTP demo server backed by CSV data or Supabase queries."""
    properties = None
    if source == "csv":
        properties = load_properties(
            data_path,
            source=source,
            supabase_schema=supabase_schema,
            supabase_table=supabase_table,
            supabase_key_type=supabase_key_type,
        )

    server = ThreadingHTTPServer(
        (host, port),
        _build_handler(
            properties,
            source=source,
            supabase_schema=supabase_schema,
            supabase_table=supabase_table,
            supabase_key_type=supabase_key_type,
        ),
    )
    print(
        f"Serving similarity demo at http://{host}:{port} "
        f"(source={source}, schema={supabase_schema}, table={supabase_table}, key_type={supabase_key_type})"
    )
    server.serve_forever()


def _build_handler(
    properties: pd.DataFrame | None,
    *,
    source: str,
    supabase_schema: str,
    supabase_table: str,
    supabase_key_type: str,
) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to the configured data source."""
    class DemoHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            """Serve static assets and JSON API responses for the similarity demo."""
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            try:
                if path == "/":
                    self._serve_static("index.html", "text/html; charset=utf-8")
                    return
                if path == "/app.js":
                    self._serve_static("app.js", "application/javascript; charset=utf-8")
                    return
                if path == "/styles.css":
                    self._serve_static("styles.css", "text/css; charset=utf-8")
                    return
                if path == "/api/properties/search":
                    query = _first_param(params, "q", default="")
                    limit = int(_first_param(params, "limit", default="10"))
                    if source == "supabase":
                        payload = search_properties_from_supabase(
                            query,
                            limit=limit,
                            schema=supabase_schema,
                            table=supabase_table,
                            key_type=supabase_key_type,
                        )
                    else:
                        payload = search_properties(properties, query, limit=limit)
                    self._send_json(payload)
                    return
                if path.startswith("/api/properties/") and path.endswith("/similar"):
                    parcel_number = unquote(path[len("/api/properties/") : -len("/similar")])
                    top_n = int(_first_param(params, "top_n", default="8"))
                    min_score_param = _first_param(params, "min_score", default="40")
                    max_distance_param = _first_param(
                        params, "max_distance_miles", default=""
                    )
                    min_score = float(min_score_param) if min_score_param != "" else None
                    max_distance = (
                        float(max_distance_param) if max_distance_param != "" else None
                    )
                    if source == "supabase":
                        payload = build_similar_response_from_supabase(
                            parcel_number,
                            top_n=top_n,
                            min_score=min_score,
                            max_distance_miles=max_distance,
                            schema=supabase_schema,
                            table=supabase_table,
                            key_type=supabase_key_type,
                        )
                    else:
                        payload = build_similar_response(
                            properties,
                            parcel_number,
                            top_n=top_n,
                            min_score=min_score,
                            max_distance_miles=max_distance,
                        )
                    self._send_json(payload)
                    return

                self.send_error(HTTPStatus.NOT_FOUND, "Route not found")
            except KeyError as exc:
                self.send_error(HTTPStatus.NOT_FOUND, str(exc))
            except ValueError as exc:
                self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
            except Exception as exc:  # pragma: no cover
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

        def log_message(self, format: str, *args: object) -> None:
            """Silence the default request logging for the lightweight demo server."""
            return

        def _serve_static(self, filename: str, content_type: str) -> None:
            """Return a static frontend asset from the demo's bundled web directory."""
            path = STATIC_DIR / filename
            payload = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, payload: Any) -> None:
            """Serialize a Python payload as a JSON HTTP response."""
            body = json.dumps(payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return DemoHandler


def search_properties_from_supabase(
    query: str,
    *,
    limit: int = 10,
    schema: str = DEFAULT_SUPABASE_SCHEMA,
    table: str = DEFAULT_SUPABASE_TABLE,
    key_type: str = "anon",
) -> list[dict[str, Any]]:
    """Search Supabase properties by parcel number and address text."""
    query = query.strip()
    if not query:
        return []

    table_client = _supabase_table(schema=schema, table=table, key_type=key_type)
    collected: dict[str, dict[str, Any]] = {}

    parcel_matches = (
        table_client.select("*")
        .ilike("parcel_number", f"%{query}%")
        .limit(limit)
        .execute()
        .data
        or []
    )
    for row in parcel_matches:
        parcel_number = str(row.get("parcel_number", "")).strip()
        if parcel_number:
            collected[parcel_number] = row

    address_matches = (
        _supabase_table(schema=schema, table=table, key_type=key_type)
        .select("*")
        .ilike("address", f"%{query}%")
        .limit(limit)
        .execute()
        .data
        or []
    )
    for row in address_matches:
        parcel_number = str(row.get("parcel_number", "")).strip()
        if parcel_number and parcel_number not in collected:
            collected[parcel_number] = row

    if not collected:
        return []

    frame = pd.DataFrame(collected.values())
    if "parcel_number" in frame.columns:
        frame["parcel_number"] = frame["parcel_number"].astype("string")
    return search_properties(frame, query, limit=limit)


def build_similar_response_from_supabase(
    parcel_number: str,
    *,
    top_n: int = 8,
    min_score: float | None = 40.0,
    max_distance_miles: float | None = None,
    schema: str = DEFAULT_SUPABASE_SCHEMA,
    table: str = DEFAULT_SUPABASE_TABLE,
    key_type: str = "anon",
    candidate_limit: int = DEFAULT_SUPABASE_CANDIDATE_LIMIT,
) -> dict[str, Any]:
    """Return a subject property and ranked similarity matches fetched from Supabase."""
    subject = fetch_subject_from_supabase(
        parcel_number,
        schema=schema,
        table=table,
        key_type=key_type,
    )
    candidates = fetch_candidate_properties_from_supabase(
        subject,
        schema=schema,
        table=table,
        key_type=key_type,
        candidate_limit=candidate_limit,
    )
    ranked = rank_similar_properties(
        subject,
        candidates,
        top_n=top_n,
        min_score=min_score,
        max_distance_miles=max_distance_miles,
    )

    subject_payload = _serialize_property_row(subject)
    subject_payload["similarity_score"] = 100.0
    subject_payload["distance_miles"] = 0.0

    return {
        "subject": subject_payload,
        "similar": [_serialize_property_row(row) for _, row in ranked.iterrows()],
    }


def fetch_subject_from_supabase(
    parcel_number: str,
    *,
    schema: str = DEFAULT_SUPABASE_SCHEMA,
    table: str = DEFAULT_SUPABASE_TABLE,
    key_type: str = "anon",
) -> pd.Series:
    """Fetch a single subject property row from Supabase by parcel number."""
    response = (
        _supabase_table(schema=schema, table=table, key_type=key_type)
        .select("*")
        .eq("parcel_number", parcel_number)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise KeyError(f"Parcel number not found: {parcel_number}")
    return pd.Series(rows[0])


def fetch_candidate_properties_from_supabase(
    subject: pd.Series | dict[str, Any],
    *,
    schema: str = DEFAULT_SUPABASE_SCHEMA,
    table: str = DEFAULT_SUPABASE_TABLE,
    key_type: str = "anon",
    candidate_limit: int = DEFAULT_SUPABASE_CANDIDATE_LIMIT,
) -> pd.DataFrame:
    """Fetch a constrained candidate set from Supabase for similarity ranking."""
    subject_parcel = _coerce_string(_get_value(subject, "parcel_number"))
    query = _supabase_table(schema=schema, table=table, key_type=key_type).select("*")

    if subject_parcel:
        query = query.neq("parcel_number", subject_parcel)

    primary_location = _coerce_string(_get_value(subject, "zipcode"))
    school_district = _coerce_string(_get_value(subject, "school_district"))
    use_code = _coerce_int(_get_value(subject, "use"))

    if primary_location:
        query = query.eq("zipcode", primary_location)
    elif school_district:
        query = query.eq("school_district", school_district)

    if use_code is not None:
        query = query.eq("use", use_code)

    bedrooms = _coerce_int(_get_value(subject, "bedrooms"))
    if bedrooms is not None:
        query = query.gte("bedrooms", max(0, bedrooms - 1)).lte("bedrooms", bedrooms + 1)

    full_baths = _coerce_int(_get_value(subject, "full_baths"))
    if full_baths is not None:
        query = query.gte("full_baths", max(0, full_baths - 1)).lte(
            "full_baths", full_baths + 1
        )

    year_built = _coerce_int(_get_value(subject, "year_built"))
    if year_built is not None:
        query = query.gte("year_built", year_built - 30).lte("year_built", year_built + 30)

    finsqft = _coerce_int(_get_value(subject, "finsqft"))
    if finsqft is not None:
        lower_sqft = max(300, int(finsqft * 0.5))
        upper_sqft = int(finsqft * 1.75)
        query = query.gte("finsqft", lower_sqft).lte("finsqft", upper_sqft)

    rows = query.limit(candidate_limit).execute().data or []

    if len(rows) < 25:
        rows = _fetch_fallback_candidates_from_supabase(
            subject,
            schema=schema,
            table=table,
            key_type=key_type,
            candidate_limit=candidate_limit,
        )

    frame = pd.DataFrame(rows)
    if not frame.empty and "parcel_number" in frame.columns:
        frame["parcel_number"] = frame["parcel_number"].astype("string")
    return frame


def _fetch_fallback_candidates_from_supabase(
    subject: pd.Series | dict[str, Any],
    *,
    schema: str,
    table: str,
    key_type: str,
    candidate_limit: int,
) -> list[dict[str, Any]]:
    """Fetch a broader Supabase candidate set when the primary query is too small."""
    subject_parcel = _coerce_string(_get_value(subject, "parcel_number"))
    school_district = _coerce_string(_get_value(subject, "school_district"))
    zipcode = _coerce_string(_get_value(subject, "zipcode"))
    use_code = _coerce_int(_get_value(subject, "use"))

    query = _supabase_table(schema=schema, table=table, key_type=key_type).select("*")
    if subject_parcel:
        query = query.neq("parcel_number", subject_parcel)

    if school_district:
        query = query.eq("school_district", school_district)
    elif zipcode:
        query = query.eq("zipcode", zipcode)

    if use_code is not None:
        query = query.eq("use", use_code)

    return query.limit(candidate_limit).execute().data or []


def _supabase_table(*, schema: str, table: str, key_type: str):
    """Return a schema-scoped Supabase table client for the configured dataset."""
    client = get_supabase_client(key_type=key_type)
    return client.schema(schema).table(table)


def _serialize_property_row(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    """Project a raw property row into the JSON shape used by the frontend."""
    parcel_number = _coerce_string(_get_value(row, "parcel_number"))
    address = _coerce_string(_get_value(row, "address"))
    beds = _coerce_number(_get_value(row, "bedrooms"))
    full_baths = _coerce_number(_get_value(row, "full_baths"))
    half_baths = _coerce_number(_get_value(row, "half_baths"))
    latitude = _coerce_number(_get_value(row, "lat", "latitude"), places=6)
    longitude = _coerce_number(_get_value(row, "lon", "longitude"), places=6)

    return {
        "parcel_number": parcel_number,
        "address": address,
        "amount": _coerce_string(_get_value(row, "amount")),
        "finsqft": _coerce_number(_get_value(row, "finsqft")),
        "year_built": _coerce_number(_get_value(row, "year_built")),
        "bedrooms": beds,
        "full_baths": full_baths,
        "half_baths": half_baths,
        "bathrooms_total": (
            None
            if full_baths is None and half_baths is None
            else round((full_baths or 0) + ((half_baths or 0) * 0.5), 1)
        ),
        "acreage": _coerce_number(_get_value(row, "acreage"), places=3),
        "school_district": _coerce_string(_get_value(row, "school_district")),
        "similarity_score": _coerce_number(
            _get_value(row, "similarity_score"), places=2
        ),
        "distance_miles": _coerce_number(
            _get_value(row, "distance_miles"), places=5
        ),
        "latitude": latitude,
        "longitude": longitude,
    }


def _get_value(row: pd.Series | dict[str, Any], *aliases: str) -> Any:
    """Return the first non-null value found under any of the provided aliases."""
    for alias in aliases:
        value = row.get(alias) if hasattr(row, "get") else None
        if value is None or pd.isna(value):
            continue
        return value
    return None


def _coerce_number(
    value: Any,
    *,
    places: int | None = 3,
) -> int | float | None:
    """Convert a value to a rounded numeric type suitable for API responses."""
    if value is None or pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if places is None:
        return number
    rounded = round(number, places)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def _coerce_int(value: Any) -> int | None:
    """Convert a scalar value to an integer when possible."""
    if value is None or pd.isna(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_string(value: Any) -> str | None:
    """Convert a scalar value to stripped text, returning `None` for empties."""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _first_param(params: dict[str, list[str]], key: str, *, default: str) -> str:
    """Return the first parsed query parameter value or a default."""
    values = params.get(key)
    if not values:
        return default
    return values[0]


def _resolve_data_path(data_path: str | Path | None) -> Path:
    """Resolve an explicit CSV path or fall back to the project's default datasets."""
    if data_path is not None:
        path = Path(data_path)
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")
        return path

    for candidate in DEFAULT_DATA_PATHS:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No processed property dataset found.")


def _parse_args() -> argparse.Namespace:
    """Parse CLI options for the standalone similarity demo server."""
    parser = argparse.ArgumentParser(description="Property similarity web demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-path", default=None)
    parser.add_argument(
        "--source",
        choices=("csv", "supabase"),
        default="csv",
        help="Data source for the demo.",
    )
    parser.add_argument(
        "--supabase-schema",
        default=DEFAULT_SUPABASE_SCHEMA,
        help="Supabase schema to query when --source supabase is used.",
    )
    parser.add_argument(
        "--supabase-table",
        default=DEFAULT_SUPABASE_TABLE,
        help="Supabase table to query when --source supabase is used.",
    )
    parser.add_argument(
        "--supabase-key-type",
        choices=("anon", "service_role"),
        default="anon",
        help="Supabase key type to use when --source supabase is used.",
    )
    return parser.parse_args()


def main() -> None:
    """Launch the standalone similarity demo server from CLI arguments."""
    args = _parse_args()
    run_demo_server(
        host=args.host,
        port=args.port,
        data_path=args.data_path,
        source=args.source,
        supabase_schema=args.supabase_schema,
        supabase_table=args.supabase_table,
        supabase_key_type=args.supabase_key_type,
    )


__all__ = [
    "build_similar_response",
    "build_similar_response_from_supabase",
    "fetch_candidate_properties_from_supabase",
    "fetch_subject_from_supabase",
    "load_properties",
    "load_properties_from_supabase",
    "main",
    "run_demo_server",
    "search_properties",
    "search_properties_from_supabase",
]
