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

# ─────────────────────────────────────────────────────────────────────────────
# Pre-compiled regexes
# ─────────────────────────────────────────────────────────────────────────────

HYPHEN_RE = re.compile(r"\b(\d+)\s*-\s*(\d+)\b")
FRACTION_RE = re.compile(r"\b(\d+)\s+(\d+)/(\d+)\b")
ORDINAL_RE = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)

EXTRA_INFO_RE = re.compile(
    r"\s*\([A-Za-z]+\)\s*",
    re.IGNORECASE | re.VERBOSE,
)

_NUMERIC_RE = re.compile(r"^\d+$")

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

HYPHEN_RE = re.compile(r"\b(\d+)\s*-\s*(\d+)\b")
FRACTION_RE = re.compile(r"\b(\d+)\s+(\d+)/(\d+)\b")
ORDINAL_RE = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
RANGE_PREFIX_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(.*)$")

EXTRA_INFO_RE = re.compile(
    r"\s*\([A-Za-z]+\)\s*",
    re.IGNORECASE | re.VERBOSE,
)

_NUMERIC_RE = re.compile(r"^\d+$")

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


EMPTY_PARSE = AddressParts()  # optional convenience

# ─────────────────────────────────────────────────────────────────────────────
# Pre-clean + tagging
# ─────────────────────────────────────────────────────────────────────────────


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
    return s


def _detect_address_range(addr: str):
    """
    Detects a leading numeric range like '1308 1310 WILLIAM H TAFT RD'.

    Returns:
        (low, high, addr_for_tagging)

    - low/high are strings or None
    - addr_for_tagging is what we send to usaddress, e.g. '1308 WILLIAM H TAFT RD'
    """
    m = RANGE_PREFIX_RE.match(addr)
    if not m:
        print(m)
        return None, None, addr, None

    low, high, rest = m.groups()

    low_i, high_i = int(low), int(high)

    diff = abs(high_i - low_i)
    # Case 2: plausible address range
    if diff <= 200:
        addr_for_tagging = f"{low} {rest}"
        return low, high, addr_for_tagging, "range"

    if diff > 200 and high_i <= 6000:  # heuristic: reasonable unit size
        addr_for_tagging = f"{low} {rest} UNIT {high}"
        return low, None, addr_for_tagging, "unit"

    elif diff > 200:
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

    # Detect space-separated number ranges like "1308 1310 WILLIAM H TAFT RD"
    low_num, high_num, addr_for_tagging, address_rng_type = _detect_address_range(
        addr_clean
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

    if not value or _NUMERIC_RE.match(value):
        return value  # already OK or empty

    try:
        numeric = w2n.word_to_num(value.lower())
        return str(numeric)
    except (ValueError, TypeError):
        return value
