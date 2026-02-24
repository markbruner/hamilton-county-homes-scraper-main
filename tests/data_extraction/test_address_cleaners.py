import pandas as pd
import pytest
from hch_scraper.pipelines.daily_scraper import _enrich_addresses
from hch_scraper.io.ingestion import upsert_sales_raw

from hch_scraper.utils.data_extraction.address_cleaners import (
    AddressParts,
    tag_address,
    normalize_address_parts,
    _preclean,
    _coerce_address_number
)

# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────


def make_row(addr: str | None, parcel: str = "603-0A23-0254-00",bbb: str = "6 - 2 - 2 - 0", use: int = 550) -> pd.Series:
    return pd.Series(
        {
        
            "address": addr,
            "parcel_number": parcel,
            "bbb": bbb,
            "use":use
        }
    )


# ─────────────────────────────────────────────────────────
# tag_address tests
# ─────────────────────────────────────────────────────────

def test_tag_address_basic_success():
    """
    Simple happy-path: standard address parses into AddressParts
    and returns no issues.
    """
    row = make_row("1935 G A CHAUCER DR", use=550)

    parts, issues = tag_address(row, addr_col="address", parcel_col="parcel_number")
    assert issues == []
    assert isinstance(parts, AddressParts)

    # Spot-check a few core fields from usaddress
    assert parts.ParcelNumber == "603-0A23-0254-00"
    assert parts.parcelid_join == "06030A230254"
    assert parts.AddressNumber == "1935"
    assert parts.OccupancyIdentifier == "GA"
    assert parts.StreetName  == "CHAUCER"
    assert parts.StreetNamePostType  == "DR"
    assert parts.OccupancyType == "UNIT"



def test_tag_address_handles_empty_input():
    """
    Empty / None address should return (None, issues) and not blow up.
    """
    row = make_row(None)

    parts, issues = tag_address(row, addr_col="address", parcel_col="parcel_number")

    assert parts is None
    assert any("Empty or non-string input" in msg for msg in issues)


def test_tag_address_fraction_preclean_does_not_crash():
    """
    Addresses with fractional house numbers should survive precleaning/tagging.
    We don't assert exact behavior of usaddress here, just that it parses.
    """
    row = make_row("915 1/2 Elm St, Cincinnati OH 45202")

    parts, issues = tag_address(row, addr_col="address", parcel_col="parcel_number")

    # Either we get a parsed parts object, or at least no exception.
    assert parts.AddressNumber == "915.5"
    assert issues == []
    assert isinstance(parts, AddressParts)


# ─────────────────────────────────────────────────────────
# normalize_address_parts tests
# ─────────────────────────────────────────────────────────

def test_normalize_address_parts_usps_suffix_and_unit():
    """
    After normalization, suffix and unit type should be in USPS abbreviations
    and names uppercased.
    15 106 W FOURTH ST
    11025 REED HARTMAN HW
    2401 7C INGLESIDE AVE
    """
    row = make_row("15 106 W FOURTH ST")
    parts, issues = tag_address(row, addr_col="address", parcel_col="parcel_number")
    assert issues == []
    assert parts is not None

    norm = normalize_address_parts(parts)

    # House number stays numeric
    assert norm.AddressNumber == "15"

    # Street name uppercased
    assert norm.StreetName == parts.StreetName.upper()

    # If usaddress gave us a directional, it should now be full-word
    if norm.StreetNamePreDirectional:
        assert norm.StreetNamePreDirectional in {
            "NORTH",
            "SOUTH",
            "EAST",
            "WEST",
            "NORTHEAST",
            "NORTHWEST",
            "SOUTHEAST",
            "SOUTHWEST",
        }
    if norm.StreetNamePostDirectional:
        assert norm.StreetNamePostDirectional in {
            "NORTH",
            "SOUTH",
            "EAST",
            "WEST",
            "NORTHEAST",
            "NORTHWEST",
            "SOUTHEAST",
            "SOUTHWEST",
        }

    # Suffix normalized to USPS (e.g., ST, AVE, RD, etc.)
    if norm.StreetNamePostType:
        assert norm.StreetNamePostType.isupper()
        assert len(norm.StreetNamePostType) <= 4  # most USPS suffixes are short

    # Unit type normalized to USPS abbrev if present
    if norm.OccupancyType:
        assert norm.OccupancyType.isupper()
        # Common ones you expect: APT, STE, UNIT, etc.
        assert len(norm.OccupancyType) <= 4

    if norm.OccupancyIdentifier:
        assert norm.OccupancyIdentifier == "106"

    # City/state uppercased
    if norm.PlaceName:
        assert norm.PlaceName == norm.PlaceName.upper()
    if norm.StateName:
        assert norm.StateName == norm.StateName.upper()


def test_normalize_address_parts_no_crash_on_missing_fields():
    """
    If some fields are None, normalization should still succeed
    and return an AddressParts instance.
    """
    parts = AddressParts(
        ParcelNumber="0001",
        AddressNumber="10",
        StreetName="Oak",
        StreetNamePostType=None,  # missing suffix
        PlaceName=None,
        StateName=None,
    )

    norm = normalize_address_parts(parts)
    assert isinstance(norm, AddressParts)
    assert norm.AddressNumber == "10"
    assert norm.StreetName == "OAK"  # should be uppercased
    assert norm.StreetNamePostType is None


# ─────────────────────────────────────────────────────────
# Helper-level tests (_preclean, _coerce_address_number)
# ─────────────────────────────────────────────────────────

def test_preclean_collapses_whitespace_and_fractions():
    raw = "  915   1/2    Elm St   (Rear) "
    cleaned = _preclean(raw)

    # Parenthetical removed, whitespace normalized, fraction collapsed
    assert "Rear" not in cleaned
    assert "  " not in cleaned
    assert "915.5" in cleaned or "915.5 Elm" in cleaned


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("123", "123"),
        ("00123", "00123"),
        ("one hundred twenty three", "123"),
        ("Twenty-One", "21"),
    ],
)
def test_coerce_address_number_words_to_numeric(input_value, expected):
    assert _coerce_address_number(input_value) == expected


def test_coerce_address_number_leaves_unparseable_values():
    """
    If word_to_num can't parse it, we should just return the original value.
    """
    value = "ABC123"
    assert _coerce_address_number(value) == value

def test_tag_address_range_space_separated():
    row = make_row("1308 1310 WILLIAM H TAFT RD", use=None)
    parts, issues = tag_address(row, addr_col="address", parcel_col="parcel_number")

    assert issues == []
    assert parts is not None
    assert parts.AddressNumber == "1308"
    assert parts.AddressNumberLow == "1308"
    assert parts.AddressNumberHigh == "1310"
    assert parts.StreetName == "WILLIAM H TAFT"


def test_enrich_addresses_keeps_unit_out_of_addressnumber():
    df = pd.DataFrame(
        [
            {
                "address": "1119 E E MCMILLAN AVE",
                "parcel_number": "603-0A23-0254-00",
                "bbb": "6 - 2 - 2 - 0",
                "use": 550,
            }
        ]
    )

    enriched, issues = _enrich_addresses(df)

    assert issues == []
    assert enriched.loc[0, "AddressNumber"] == "1119"
    assert enriched.loc[0, "OccupancyIdentifier"] is None
    assert enriched.loc[0, "StreetNamePreDirectional"] == "EAST"
    assert enriched.loc[0, "StreetName"] == "E MCMILLAN"


def test_upsert_payload_addressnumber_is_house_number_only():
    class _DummyResp:
        error = None

    class _DummyRpc:
        def __init__(self, sink):
            self._sink = sink

        def execute(self):
            self._sink.append(self.payload)
            return _DummyResp()

    class _DummySupabase:
        def __init__(self):
            self.calls = []

        def rpc(self, _name, payload):
            rpc = _DummyRpc(self.calls)
            rpc.payload = payload
            return rpc

    df = pd.DataFrame(
        [
            {
                "address": "4951 305 N ARBOR WOODS CT",
                "parcel_number": "603-0A23-0254-00",
                "bbb": "6 - 2 - 2 - 0",
                "use": 550,
                "transfer_date": "2026-02-20",
            }
        ]
    )
    enriched, _issues = _enrich_addresses(df)
    supabase = _DummySupabase()

    upsert_sales_raw(df=enriched, supabase=supabase)

    payload = supabase.calls[0]["p"]
    assert payload["addressnumber"] == "4951"
    assert payload["occupancyidentifier"] == "305"
