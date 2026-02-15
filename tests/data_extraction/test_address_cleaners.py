import pandas as pd
import pytest

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
    row = make_row("116 #206 W FIFTEENTH ST", use=550)
    parts, issues = tag_address(row, addr_col="address", parcel_col="parcel_number")
    
    assert issues == []
    assert isinstance(parts, AddressParts)

    # Spot-check a few core fields from usaddress
    assert parts.ParcelNumber == "603-0A23-0254-00"
    assert parts.parcelid_join == "06030A230254"
    assert parts.OccupancyType == "UNIT"
    assert parts.AddressNumber == "116"
    assert parts.OccupancyIdentifier == "206"
    assert parts.StreetName  == "FIFTEENTH"
    assert parts.StreetNamePostType  == "ST"



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

    # If usaddress gave us a directional, it should now be USPS abbrev
    if norm.StreetNamePreDirectional:
        assert norm.StreetNamePreDirectional in {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
    if norm.StreetNamePostDirectional:
        assert norm.StreetNamePostDirectional in {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}

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