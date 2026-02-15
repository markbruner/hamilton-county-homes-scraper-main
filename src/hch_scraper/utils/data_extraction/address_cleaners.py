import re
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, List

import pandas as pd
import usaddress
from word2number import w2n

import logging

from hch_scraper.config.mappings.street_types import (
    street_suffix_normalization_map,
    direction_normalization_map,
)
from hch_scraper.config.mappings.secondary_units import secondary_unit_normalization_map

logger = logging.getLogger(__name__)


"""
Address Parsing and Enrichment Utility

This module provides functionality to extract structured address components (house number, street, apartment)
from raw address strings using spaCy, and enrich them with ZIP code and city information using Hamilton County's
centerline and ZIP code datasets.

Key Features:
- Parses raw addresses into structured components using NLP.

"""

# ─────────────────────────────────────────────────────────────────────────────
# Pre-compiled regexes
# ─────────────────────────────────────────────────────────────────────────────

HYPHEN_RE = re.compile(r"\b(\d+)\s*-\s*(\d+)+\s(.*)$\b")
AMOUNT_RE = re.compile(r"^[$]\d+[,]\d+")
FRACTION_RE = re.compile(r"\b(\d+)\s+(\d+)/(\d+)\b")
ORDINAL_RE = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
RANGE_PREFIX_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(.*)$")
UNIT_TOKEN_RE = re.compile(r"^\d+[A-Z]$|^\d+[A-Z]{1,2}$|^[A-Z]{1,2}\d+$", re.I)
EXTRA_INFO_RE = re.compile(r"\s*\([A-Za-z]+\)\s*",re.IGNORECASE | re.VERBOSE,)
NUMERIC_RE = re.compile(r"^\d+$")
DECIMAL_DOT = re.compile(r"(?<=\d)\.(?=\d)")  # dot between digits
PROTECT = "⟐"  # any rare placeholder char

# ─────────────────────────────────────────────────────────────────────────────
# Property Use Type Dictionaries
# ─────────────────────────────────────────────────────────────────────────────

CONDO_USES = {550, 552, 554, 558, 555}
APT_USES   = {401, 402, 403, 404, 431}
MF_USES    = {520, 530}

USE_TO_HOUSING = {
    **{u: "condo" for u in CONDO_USES},
    **{u: "apt"   for u in APT_USES},
    **{u: "unit"  for u in MF_USES},
}

# ─────────────────────────────────────────────────────────────────────────────
# Dataclass for parsed addresses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class AddressParts:
    record_key: Optional[str] = None
    ParcelNumber: Optional[str] = None
    Recipient: Optional[str] = None

    # Primary address number (what usaddress sees)
    AddressNumber: Optional[str] = None

    # Optional range for things like "1308 1310 WILLIAM H TAFT RD"
    AddressNumberLow: Optional[str] = None
    AddressNumberHigh: Optional[str] = None

    AddressNumberPrefix: Optional[str] = None
    AddressNumberSuffix: Optional[str] = None
    StreetName: Optional[str] = None
    StreetNamePreDirectional: Optional[str] = None
    StreetNamePreModifier: Optional[str] = None
    StreetNamePreType: Optional[str] = None
    StreetNamePostDirectional: Optional[str] = None
    StreetNamePostModifier: Optional[str] = None
    StreetNamePostType: Optional[str] = None
    CornerOf: Optional[str] = None
    IntersectionSeparator: Optional[str] = None
    LandmarkName: Optional[str] = None
    USPSBoxGroupID: Optional[str] = None
    USPSBoxGroupType: Optional[str] = None
    USPSUSPSBoxID: Optional[str] = None
    USPSBoxType: Optional[str] = None
    BuildingName: Optional[str] = None
    OccupancyType: Optional[str] = None
    OccupancyIdentifier: Optional[str] = None
    SubaddressIdentifier: Optional[str] = None
    SubaddressType: Optional[str] = None
    PlaceName: Optional[str] = None
    StateName: Optional[str] = None
    AddressType: Optional[str] = None
    address_range_type: Optional[str] = None
    row_hash: Optional[str] = None
    first_seen_at: Optional[str] = (None,)
    last_seen_at: Optional[str] = (None,)
    updated_at: Optional[str] = (None,)
    update_type: Optional[str] = (None,)
    changed_fields: Optional[str] = (None,)
    parcelid_join: Optional[str] = None,
    amount_num: Optional[float] = None,
    total_rooms: Optional[int] = None,
    bedrooms: Optional[int] = None,
    full_baths: Optional[int] = None,
    half_baths: Optional[int] = None,
    geom: Optional[str] = None,



# ─────────────────────────────────────────────────────────────────────────────
# Pre-clean + tagging
# ─────────────────────────────────────────────────────────────────────────────

def _safe_int(x) -> Optional[int]:
    if x is None:
        return None

    try:
        if isinstance(x, (int,)):
            return x

        # strings like "$123,456.00", "123,456", "550.0"
        if isinstance(x, str):
            cleaned = x.strip().replace("$", "").replace(",", "")
            if cleaned == "":
                return None
            return int(float(cleaned))

        # numpy, floats, decimals
        return int(float(x))

    except (ValueError, TypeError, OverflowError):
        return None
    
def _preclean(addr: str) -> str:
    """
    Light, non-destructive cleanup before usaddress:
    - trim
    - collapse whitespace
    - remove simple parenthetical tags
    - normalize fractions  '915 1/2' -> '915.5'
    """
    if not isinstance(addr, str):
        return ""

    s = addr.strip()
    s = EXTRA_INFO_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s)
    s = FRACTION_RE.sub(_collapse_fraction, s)
    s = DECIMAL_DOT.sub(PROTECT, s)
    s =  re.sub(r"[^\w\s⟐\-/]", " ", s)
    s = s.replace(PROTECT, ".")  
    return s

def _move_leading_unit_token(addr: str, housing_type: str) -> str:
    parts = addr.split()
    if len(parts) < 4:
        return addr

    house, maybe_unit = parts[0], parts[1]
    if not house.isdigit():
        return addr

    if not UNIT_TOKEN_RE.match(maybe_unit):
        return addr

    # rewrite: "5757 1D CHEVIOT RD" -> "5757 CHEVIOT RD UNIT 1D"
    rest = " ".join(parts[2:])

    if housing_type in ('unit','condo'):
        return f"{house} {rest} UNIT {maybe_unit}"
        
    if housing_type == 'apt':
        return f"{house} {rest} APT {maybe_unit}"


def _detect_address_range(addr: str, housing_type: str):
    """
    Detects a leading numeric range like '1308 1310 WILLIAM H TAFT RD'.

    Returns:
        (low, high, addr_for_tagging)

    - low/high are strings or None
    - addr_for_tagging is what we send to usaddress, e.g. '1308 WILLIAM H TAFT RD'
    """
    if addr is not None:
        m = RANGE_PREFIX_RE.match(addr)
        if not m:
            m = HYPHEN_RE.match(addr)
            if not m:
                return None, None, addr, None

        low, high, rest = m.groups()

        low_i, high_i = int(low), int(high)
        
        diff = high_i - low_i

        # Case 2: plausible address range
        if 1 <= diff <= 200:
            if housing_type == 'apt':
                addr_for_tagging = f"{low} {rest} APT {high}"
                return low, None, addr_for_tagging, "apt"
            else:
                addr_for_tagging = f"{low} {rest}"
                return low, high, addr_for_tagging, "range"
        
        if diff <= 0:
            if housing_type in ('unit','condo'):
                addr_for_tagging = f"{low} {rest} UNIT {high}"
                return low, None, addr_for_tagging, "unit"
            if housing_type == 'apt':
                addr_for_tagging = f"{low} {rest} APT {high}"
                return low, None, addr_for_tagging, "apt"
        
        if diff > 200 and high_i <= 6000:  # heuristic: reasonable unit size
            if housing_type in ('unit','condo'):
                addr_for_tagging = f"{low} {rest} UNIT {high}"
                return low, None, addr_for_tagging, "unit"
            if housing_type in ('apt'):
                addr_for_tagging = f"{low} {rest} APT {high}"
                return low, None, addr_for_tagging, "apt"

        return None, None, addr, "unknown"
    
    return None, None, addr, "unknown"


def fix_alpha_address_number(parsed):
    if "AddressNumber" in parsed:
        if not re.search(r"\d", parsed["AddressNumber"]):
            # Move it into StreetName
            parsed["StreetName"] = (
                parsed.get("StreetName", "") + " " + parsed["AddressNumber"]
            ).strip()
            del parsed["AddressNumber"]
    return parsed

def parse_bbb(bbb) -> dict[str, int | None]:
    if pd.isna(bbb):
        parts = []
    else:
        parts = str(bbb).split("-")

    parts += [None] * 4

    return {
        "total_rooms": _safe_int(parts[0]),
        "bedrooms": _safe_int(parts[1]),
        "full_baths": _safe_int(parts[2]),
        "half_baths": _safe_int(parts[3]),
    }

def tag_address(
    row: pd.Series,
    addr_col: str,
    parcel_col: str,
) -> Tuple[Optional[AddressParts], List[str]]:
    """
    row         : one DataFrame row (Series)
    addr_col    : name of the address column in that row
    parcel_col  : name of the parcel-number column
    """
    issues: list[str] = []

    addr_raw = row[addr_col]

    if not isinstance(addr_raw, str) or not addr_raw.strip():
        issues.append("Empty or non-string input")
        return None, issues

    addr_clean = _preclean(addr_raw)
    parcel_id = row[parcel_col]

    use_code = _safe_int(row.get("use"))
    
    housing_type = USE_TO_HOUSING.get(use_code)  # "condo" | "apt" | "unit" | None

    digits= parcel_id.replace("-","")
    parcelid_join = f"0{digits[:11]}"

    bbb_dict = parse_bbb(row.get("bbb"))

    addr_clean = _move_leading_unit_token(addr_clean,housing_type)
    amount_num = _safe_int(row.get("amount"))

    # Detect space-separated number ranges like "1308 1310 WILLIAM H TAFT RD"
    low_num, high_num, addr_for_tagging, address_rng_type = _detect_address_range(
        addr_clean, housing_type
    )

    try:
        usparsed, _ = usaddress.tag(addr_for_tagging)
    except usaddress.RepeatedLabelError as err:
        issues.append(f"Repeated label: {err}")
        return None, issues
    except Exception as err:
        issues.append(str(err))
        return None, issues

    if (high_num is not None) and (int(high_num) - int(low_num) < 0):
        high_num = None

    usparsed = fix_alpha_address_number(usparsed)

    parts = AddressParts(
        record_key=None,
        ParcelNumber=parcel_id,
        Recipient=usparsed.get("Recipient"),
        AddressNumber=usparsed.get("AddressNumber"),
        # new range fields:
        AddressNumberLow=low_num,
        AddressNumberHigh=high_num,
        AddressNumberPrefix=usparsed.get("AddressNumberPrefix"),
        AddressNumberSuffix=usparsed.get("AddressNumberSuffix"),
        StreetName=usparsed.get("StreetName"),
        StreetNamePreDirectional=usparsed.get("StreetNamePreDirectional"),
        StreetNamePreModifier=usparsed.get("StreetNamePreModifier"),
        StreetNamePreType=usparsed.get("StreetNamePreType"),
        StreetNamePostDirectional=usparsed.get("StreetNamePostDirectional"),
        StreetNamePostModifier=usparsed.get("StreetNamePostModifier"),
        StreetNamePostType=usparsed.get("StreetNamePostType"),
        CornerOf=usparsed.get("CornerOf"),
        IntersectionSeparator=usparsed.get("IntersectionSeparator"),
        LandmarkName=usparsed.get("LandmarkName"),
        USPSBoxGroupID=usparsed.get("USPSBoxGroupID"),
        USPSBoxGroupType=usparsed.get("USPSBoxGroupType"),
        USPSUSPSBoxID=usparsed.get("USPSUSPSBoxID"),
        USPSBoxType=usparsed.get("USPSBoxType"),
        BuildingName=usparsed.get("BuildingName"),
        OccupancyType=usparsed.get("OccupancyType"),
        OccupancyIdentifier=usparsed.get("OccupancyIdentifier"),
        SubaddressIdentifier=usparsed.get("SubaddressIdentifier"),
        SubaddressType=usparsed.get("SubaddressType"),
        PlaceName=usparsed.get("PlaceName"),
        StateName=usparsed.get("StateName"),
        AddressType=usparsed.get("AddressType"),
        address_range_type=address_rng_type,
        row_hash=None,
        first_seen_at=None,
        last_seen_at=None,
        updated_at=None,
        update_type=None,
        changed_fields=None,
        parcelid_join=parcelid_join,
        amount_num=amount_num,
        total_rooms=bbb_dict.get("total_rooms"),
        bedrooms=bbb_dict.get("bedrooms"),
        full_baths=bbb_dict.get("full_baths"),
        half_baths=bbb_dict.get("half_baths"),
        geom=None,
    )
    
    return parts, issues


# ─────────────────────────────────────────────────────────────────────────────
# Normalization (USPS abbreviations, numeric house number, etc.)
# ─────────────────────────────────────────────────────────────────────────────


def normalize_address_parts(parts: AddressParts) -> AddressParts:
    data = asdict(parts)

    # Address number
    new_num = _coerce_address_number(parts.AddressNumber)
    if new_num != parts.AddressNumber:
        logger.debug(f"AddressNumber normalized: {parts.AddressNumber} → {new_num}")
    data["AddressNumber"] = new_num

    # Pre-direction
    if parts.StreetNamePreDirectional:
        raw = parts.StreetNamePreDirectional.upper().rstrip(".")
        normalized = direction_normalization_map.get(raw)
        if normalized != raw:
            logger.debug(f"PreDirectional normalized: {raw} → {normalized}")
        data["StreetNamePreDirectional"] = normalized
        # Pre-direction

    if parts.StreetName:
        raw = parts.StreetName.upper()
        data["StreetName"] = raw

    if parts.StreetNamePostDirectional:
        raw = parts.StreetNamePostDirectional.upper().rstrip(".")
        normalized = direction_normalization_map.get(raw)
        if normalized != raw:
            logger.debug(f"PostDirectional normalized: {raw} → {normalized}")
        data["StreetNamePostDirectional"] = normalized

    # Suffix
    if parts.StreetNamePostType:
        raw = parts.StreetNamePostType.upper().rstrip(".")
        normalized = street_suffix_normalization_map.get(raw)
        if normalized != raw:
            logger.debug(f"Suffix normalized: {raw} → {normalized}")
        data["StreetNamePostType"] = normalized

    # Unit
    if parts.OccupancyType:
        raw = parts.OccupancyType.upper().rstrip(".")
        normalized = secondary_unit_normalization_map.get(raw)
        if normalized != raw:
            logger.debug(f"UnitType normalized: {raw} → {normalized}")
        data["OccupancyType"] = normalized

    # City/State
    if parts.PlaceName and parts.PlaceName.upper() != parts.PlaceName:
        logger.debug(f"City uppercased: {parts.PlaceName} → {parts.PlaceName.upper()}")
        data["PlaceName"] = parts.PlaceName.upper()

    if parts.StateName and parts.StateName.upper() != parts.StateName:
        logger.debug(f"State uppercased: {parts.StateName} → {parts.StateName.upper()}")
        data["StateName"] = parts.StateName.upper()

    return AddressParts(**data)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _collapse_fraction(m: re.Match) -> str:
    whole, num, den = m.groups()
    value = int(whole) + int(num) / int(den)  # 915 + 1/2 → 915.5
    return f"{value:g}".rstrip(".")


def _coerce_address_number(value: Optional[str]) -> Optional[str]:
    """
    Return a strictly numeric house number, or the original value if we
    cant make a safe conversion. Handles 'one hundred twenty-three' → '123'.
    """
    if value is not None and HYPHEN_RE.match(value):
        value = HYPHEN_RE.sub(lambda m: m.group(1), value)

    if not value or NUMERIC_RE.match(value):
        return value  # already OK or empty

    try:
        numeric = w2n.word_to_num(value.lower())
        return str(numeric)
    except (ValueError, TypeError):
        return value
