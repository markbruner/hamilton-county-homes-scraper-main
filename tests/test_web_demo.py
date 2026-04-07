import pandas as pd

from hch_scraper.web_demo import (
    DEFAULT_SUPABASE_SCHEMA,
    DEFAULT_SUPABASE_TABLE,
    build_similar_response,
    build_similar_response_from_supabase,
    load_properties_from_supabase,
    search_properties,
    search_properties_from_supabase,
)


def _properties_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "parcel_number": "P1",
                "address": "100 MAIN ST",
                "finsqft": 1500,
                "year_built": 1950,
                "bedrooms": 3,
                "full_baths": 2,
                "half_baths": 1,
                "acreage": 0.20,
                "amount": "$250,000",
                "use": 510,
                "school_district": "CINCINNATI CSD",
                "latitude": 39.1000,
                "longitude": -84.5000,
            },
            {
                "parcel_number": "P2",
                "address": "102 MAIN ST",
                "finsqft": 1525,
                "year_built": 1952,
                "bedrooms": 3,
                "full_baths": 2,
                "half_baths": 1,
                "acreage": 0.19,
                "amount": "$255,000",
                "use": 510,
                "school_district": "CINCINNATI CSD",
                "latitude": 39.1005,
                "longitude": -84.5003,
            },
            {
                "parcel_number": "P3",
                "address": "999 FAR RD",
                "finsqft": 2900,
                "year_built": 2005,
                "bedrooms": 5,
                "full_baths": 3,
                "half_baths": 1,
                "acreage": 1.40,
                "amount": "$510,000",
                "use": 599,
                "school_district": "OTHER CSD",
                "latitude": 39.3000,
                "longitude": -84.7000,
            },
        ]
    )


def _build_fake_supabase_client(rows):
    class FakeQuery:
        def __init__(self, rows):
            self.rows = list(rows)
            self.filters = []
            self._limit = None
            self._range = None

        def select(self, *_args, **_kwargs):
            return self

        def range(self, start, end):
            self._range = (start, end)
            return self

        def limit(self, value):
            self._limit = value
            return self

        def eq(self, column, value):
            self.filters.append(lambda row: row.get(column) == value)
            return self

        def neq(self, column, value):
            self.filters.append(lambda row: row.get(column) != value)
            return self

        def ilike(self, column, pattern):
            needle = pattern.strip("%").upper()
            self.filters.append(
                lambda row: needle in str(row.get(column, "")).upper()
            )
            return self

        def gte(self, column, value):
            self.filters.append(
                lambda row: row.get(column) is not None and row.get(column) >= value
            )
            return self

        def lte(self, column, value):
            self.filters.append(
                lambda row: row.get(column) is not None and row.get(column) <= value
            )
            return self

        def execute(self):
            filtered = list(self.rows)
            for condition in self.filters:
                filtered = [row for row in filtered if condition(row)]

            if self._range is not None:
                start, end = self._range
                filtered = filtered[start : end + 1]
            if self._limit is not None:
                filtered = filtered[: self._limit]

            return type("Resp", (), {"data": filtered})()

    class FakeSchema:
        def __init__(self, rows):
            self.rows = rows

        def table(self, _table):
            return FakeQuery(self.rows)

    class FakeClient:
        def __init__(self, rows):
            self.rows = rows

        def schema(self, _schema):
            return FakeSchema(self.rows)

    return FakeClient(rows)


def test_search_properties_matches_address_and_parcel():
    properties = _properties_frame()

    address_results = search_properties(properties, "main", limit=5)
    parcel_results = search_properties(properties, "P1", limit=5)

    assert [item["parcel_number"] for item in address_results] == ["P1", "P2"]
    assert parcel_results[0]["parcel_number"] == "P1"


def test_build_similar_response_returns_subject_and_similar_rows():
    properties = _properties_frame()

    payload = build_similar_response(properties, "P1", top_n=2, min_score=0)

    assert payload["subject"]["parcel_number"] == "P1"
    assert payload["subject"]["distance_miles"] == 0.0
    assert len(payload["similar"]) == 2
    assert payload["similar"][0]["parcel_number"] == "P2"
    assert "latitude" in payload["similar"][0]


def test_build_similar_response_preserves_small_nonzero_distance():
    properties = pd.DataFrame(
        [
            {
                "parcel_number": "S1",
                "address": "1 CLOSE ST",
                "finsqft": 1000,
                "year_built": 1950,
                "bedrooms": 2,
                "full_baths": 1,
                "half_baths": 0,
                "acreage": 0.10,
                "amount": "$100,000",
                "use": 510,
                "school_district": "CINCINNATI CSD",
                "latitude": 39.100000,
                "longitude": -84.500000,
            },
            {
                "parcel_number": "S2",
                "address": "2 CLOSE ST",
                "finsqft": 1002,
                "year_built": 1951,
                "bedrooms": 2,
                "full_baths": 1,
                "half_baths": 0,
                "acreage": 0.10,
                "amount": "$101,000",
                "use": 510,
                "school_district": "CINCINNATI CSD",
                "latitude": 39.100010,
                "longitude": -84.500000,
            },
        ]
    )

    payload = build_similar_response(properties, "S1", top_n=1, min_score=0)

    assert payload["similar"][0]["distance_miles"] > 0


def test_load_properties_from_supabase_paginates(monkeypatch):
    class FakeQuery:
        def __init__(self, pages):
            self.pages = pages
            self.current_offset = 0
            self.current_end = 0

        def select(self, *_args, **_kwargs):
            return self

        def range(self, start, end):
            self.current_offset = start
            self.current_end = end
            return self

        def execute(self):
            batch = self.pages.get(self.current_offset, [])
            return type("Resp", (), {"data": batch})()

    class FakeSchema:
        def __init__(self, pages):
            self.pages = pages

        def table(self, _table):
            return FakeQuery(self.pages)

    class FakeClient:
        def __init__(self, pages):
            self.pages = pages

        def schema(self, _schema):
            return FakeSchema(self.pages)

    pages = {
        0: [
            {"parcel_number": "P1", "address": "100 MAIN ST"},
            {"parcel_number": "P2", "address": "102 MAIN ST"},
        ],
        2: [{"parcel_number": "P3", "address": "104 MAIN ST"}],
    }

    monkeypatch.setattr(
        "hch_scraper.web_demo.get_supabase_client",
        lambda key_type="anon": FakeClient(pages),
    )

    loaded = load_properties_from_supabase(
        schema="public",
        table="sales_hamilton",
        page_size=2,
        key_type="anon",
    )

    assert loaded["parcel_number"].tolist() == ["P1", "P2", "P3"]


def test_supabase_defaults_target_silver_sales_enriched():
    assert DEFAULT_SUPABASE_SCHEMA == "public"
    assert DEFAULT_SUPABASE_TABLE == "sales_enriched_api"


def test_search_properties_from_supabase_queries_subset(monkeypatch):
    monkeypatch.setattr(
        "hch_scraper.web_demo.get_supabase_client",
        lambda key_type="anon": _build_fake_supabase_client(_properties_frame().to_dict("records")),
    )

    results = search_properties_from_supabase(
        "MAIN",
        schema="public",
        table="sales_enriched_api",
        key_type="anon",
    )

    assert [item["parcel_number"] for item in results] == ["P1", "P2"]


def test_build_similar_response_from_supabase_is_lazy_and_ranked(monkeypatch):
    supabase_rows = [
        {
            "parcel_number": "P1",
            "address": "100 MAIN ST",
            "finsqft": 1500,
            "year_built": 1950,
            "bedrooms": 3,
            "full_baths": 2,
            "half_baths": 1,
            "amount": "$250,000",
            "use": 510,
            "school_district": "CINCINNATI CSD",
            "zipcode": "45201",
            "latitude": 39.1000,
            "longitude": -84.5000,
        },
        {
            "parcel_number": "P2",
            "address": "102 MAIN ST",
            "finsqft": 1525,
            "year_built": 1952,
            "bedrooms": 3,
            "full_baths": 2,
            "half_baths": 1,
            "amount": "$255,000",
            "use": 510,
            "school_district": "CINCINNATI CSD",
            "zipcode": "45201",
            "latitude": 39.1005,
            "longitude": -84.5003,
        },
        {
            "parcel_number": "P3",
            "address": "999 FAR RD",
            "finsqft": 2900,
            "year_built": 2005,
            "bedrooms": 5,
            "full_baths": 3,
            "half_baths": 1,
            "amount": "$510,000",
            "use": 599,
            "school_district": "OTHER CSD",
            "zipcode": "99999",
            "latitude": 39.3000,
            "longitude": -84.7000,
        },
    ]

    monkeypatch.setattr(
        "hch_scraper.web_demo.get_supabase_client",
        lambda key_type="anon": _build_fake_supabase_client(supabase_rows),
    )

    payload = build_similar_response_from_supabase(
        "P1",
        top_n=2,
        min_score=0,
        schema="public",
        table="sales_enriched_api",
        key_type="anon",
        candidate_limit=50,
    )

    assert payload["subject"]["parcel_number"] == "P1"
    assert payload["similar"][0]["parcel_number"] == "P2"


def test_build_similar_response_from_supabase_handles_float_like_int_filters(monkeypatch):
    supabase_rows = [
        {
            "parcel_number": "P1",
            "address": "100 MAIN ST",
            "finsqft": 1500.0,
            "year_built": 1950.0,
            "bedrooms": 3.0,
            "full_baths": 2.0,
            "half_baths": 1.0,
            "amount": "$250,000",
            "use": 510.0,
            "school_district": "CINCINNATI CSD",
            "zipcode": "45201",
            "latitude": 39.1000,
            "longitude": -84.5000,
        },
        {
            "parcel_number": "P2",
            "address": "102 MAIN ST",
            "finsqft": 1525.0,
            "year_built": 1952.0,
            "bedrooms": 3.0,
            "full_baths": 2.0,
            "half_baths": 1.0,
            "amount": "$255,000",
            "use": 510.0,
            "school_district": "CINCINNATI CSD",
            "zipcode": "45201",
            "latitude": 39.1005,
            "longitude": -84.5003,
        },
    ]

    monkeypatch.setattr(
        "hch_scraper.web_demo.get_supabase_client",
        lambda key_type="anon": _build_fake_supabase_client(supabase_rows),
    )

    payload = build_similar_response_from_supabase(
        "P1",
        top_n=1,
        min_score=0,
        schema="public",
        table="sales_enriched_api",
        key_type="anon",
        candidate_limit=50,
    )

    assert payload["similar"][0]["parcel_number"] == "P2"
