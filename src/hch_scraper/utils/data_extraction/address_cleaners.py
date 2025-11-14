import re
import os
import pandas as pd
import numpy as np

import rapidfuzz
from rapidfuzz import process, fuzz
import difflib
import spacy
from spacy.lang.en import English
from spacy.util import compile_suffix_regex
from dataclasses import dataclass,asdict
from typing import Optional, Dict, Tuple

from hch_scraper.utils.data_extraction.form_helpers.file_io import get_file_path
from hch_scraper.config.mappings.street_types import street_type_map
from hch_scraper.config.settings import direction_map, home_type_map
from hch_scraper.config.mappings.secondary_units import spelled_out_numbers
from hch_scraper.services.geocoding import save_cache_to_disk, load_cache_from_disk

"""
Address Parsing and Enrichment Utility

This module provides functionality to extract structured address components (house number, street, apartment)
from raw address strings using spaCy, and enrich them with ZIP code and city information using Hamilton County's
centerline and ZIP code datasets.

Key Features:
- Parses raw addresses into structured components using NLP.
- Matches street names with fuzzy logic.
- Maps address ranges to ZIP codes and cities using centerline data.
- Provides an AddressEnricher class for convenient reuse.
"""

nlp = spacy.load("en_core_web_sm")
nlp = English()
suffixes = list(nlp.Defaults.suffixes)

# drop the “digit-unit” suffix pattern
suffixes = [s for s in suffixes if "(?<=[0-9])" not in s]
nlp.tokenizer.suffix_search = compile_suffix_regex(suffixes).search

# Words that spaCy typically tags as numbers but should be treated as part
# of the street name when parsing addresses.  This includes cardinal and
# ordinal forms so that streets like "THIRTY-SECOND" are not mistaken for
# house numbers.


# Street-name prefix expansion map
STREET_PREFIX_MAP = {
    # Saint / Sainte / Saints
    "St":      "Saint",
    "St.":     "Saint",
    "Ste":     "Sainte",
    "Ste.":    "Sainte",
    "Sts":     "Saints",
    "Sts.":    "Saints",

    # Spanish-language saints
    "San":     "San",
    "Santa":   "Santa",
    "Santo":   "Santo",
    "Santos":  "Santos",

    # Mount / Mountain
    "Mt":      "Mount",
    "Mt.":     "Mount",
    "Mtn":     "Mountain",
    "Mtn.":    "Mountain",

    # Fort
    "Ft":      "Fort",
    "Ft.":     "Fort",

    # Point
    "Pt":      "Point",
    "Pt.":     "Point",

    # Lake
    "Lk":      "Lake",
    "Lk.":     "Lake",

    # Peak / Park  (choose meaning at runtime if context matters)
    "Pk":      "Peak",
    "Pk.":     "Peak",

    # Port
    "Port":    "Port",
    "Prt":     "Port",
}

APT_HEAD_WORDS = {"#", "APT", "UNIT", "STE", "SUITE", "ROOM", "RM"}

# ❱ pre-compiled regexen (compiled once instead of every call)
HYPHEN_RE     = re.compile(r"\b(\d+)\s*-\s*(\d+)\b")
FRACTION_RE   = re.compile(r"\b(\d+)\s+(\d+)/(\d+)\b")
ORDINAL_RE    = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
APT_TAIL_RE = re.compile(r"(?:\s+|^)(?:\#\s*|(?:APT|UNIT|STE|SUITE|ROOM|RM)\s+)?([A-Z0-9]{1,6}(?:-[A-Z0-9]{1,4})?)\s*$",
    re.IGNORECASE | re.VERBOSE,
)
APT_LETTER_RE = re.compile(r"\b(?!(?:N|S|E|W|NE|NW|SE|SW))[a-zA-Z]{1,2}\b", re.IGNORECASE | re.VERBOSE)
APT_ALPHANUM_RE = re.compile(r"([a-zA-Z]{1,2}-?\d{1,4}|\d{1,4}-?[a-zA-Z]{1,2})", re.IGNORECASE | re.VERBOSE)
DIRECTION_RE = re.compile(r"\b\s*(?:N|S|E|W|NW|SW|NE|SE|SOUTH|NORTH|EAST|WEST|NORTHEAST|SOUTHEAST|NORTHWEST|SOUTHWEST)\s*\b", re.IGNORECASE)
EXTRA_INFO_RE = re.compile(r"\s*\([A-Za-z]+\)\s*",re.IGNORECASE | re.VERBOSE)


def build_interval_lookup(grouped: pd.core.groupby.GroupBy) -> dict[str, tuple[pd.IntervalIndex, np.ndarray, np.ndarray]]:
    """
    Pre-compute two IntervalIndexes (left & right) **per street**.

    Returns
    -------
    {
        "MAIN ST": (left_intv, left_zip, left_parity),
        ...
    }
    """
    lookups = {}

    for street, segs in grouped:
        street = street[0] if isinstance(street, tuple) else street
        left_intv   = _make_interval(segs["L_F_ADD"], segs["L_T_ADD"])
        right_intv  = _make_interval(segs["R_F_ADD"], segs["R_T_ADD"])

        left_parity  = (segs["L_F_ADD"].astype("Int64") & 1).to_numpy()
        right_parity = (segs["R_F_ADD"].astype("Int64") & 1).to_numpy()

        lookups[street] = (
            left_intv,
            segs["ZIPL"].to_numpy(),
            left_parity,
            right_intv,
            segs["ZIPR"].to_numpy(),
            right_parity,
        )

    return lookups

def _make_interval(start: pd.Series, end: pd.Series) -> pd.IntervalIndex:
    try:
        # cast to nullable Int so bitwise ops work and NAs are preserved
        s = start.astype("Int64")
        e = end.astype("Int64")

        lower = np.minimum(s, e)   # element-wise
        upper = np.maximum(s, e)
        return pd.IntervalIndex.from_arrays(lower, upper, closed="both")
    except ValueError:
        return None

def fuzzy_match_street_name(bad: str, valid_names: pd.Series, score_cut: float = 80) -> str:
    """
    Corrects misspelled street names.
    
    Args:
        bad (str): The street name that may not be correct.
        valid_names (pd.Series): A unique list of correct street names.
        score_cut (float) : A real number between 0 and 100 indicating the accuracy score cutoff.

    Returns:
        str: Either the original street name if cutoff below threshhold or the corrected street name.
 
    """
    cand, score, _ = process.extractOne(
        bad, valid_names, scorer=fuzz.token_set_ratio
    )
    return cand if cand and score >= score_cut else bad

@dataclass(slots=True)
class AddressParts:
    
    def __init__(self, normalize_case: bool = True):
        address = self.address

def _preclean(raw, addr: str):
    if not addr:
        return ""
    addr = addr.strip()
    addr = addr.sub(r"[^\w\s]", " ")
    addr = addr.sub(r"\s+"," ")
    addr = addr.lower()
    

def tag_address(address: str) -> AddressParts:
    if not isinstance(address, str) or not address.strip():
        return AddressParts()

    apt_tail_match = APT_TAIL_RE.search(address)
    tagged    = AddressParts()
    
    if apt_tail_match and _apt_is_alphanumeric(apt_tail_match.group(1)):
        tagged.apt_num = apt_tail_match.group(1).lstrip("#")
        address = address[:apt_tail_match.start()].rstrip()

    address = HYPHEN_RE.sub(lambda m: m.group(1), address)

    direction_match = DIRECTION_RE.search(address)
    if direction_match:
        direction = direction_match[0].strip()
        if direction in direction_map :
            tagged.st_dir = direction_map [direction]
        else:
            tagged.st_dir = direction
        address = address.replace(direction_match[0],' ')

    address = address.replace('-', '')
    address = FRACTION_RE.sub(_collapse_fraction, address)
    
    extra_info_match = EXTRA_INFO_RE.search(address)
    if extra_info_match:
        address = address.replace(extra_info_match[0].rstrip(),'')

    doc        = nlp(address)
    start_idx  = 0      

    # ── PRIMARY NUMBER (same as before) ───────────────────────────────
    first = next((t for t in doc if not t.is_space), None)
    if first and first.like_num and first.lower_ not in spelled_out_numbers:
        # keep the “don’t steal the street number if it’s ordinal” check
        if not _is_ordinal(first):
            tagged.st_num = first.text
            start_idx = first.i + 1
        else:
            start_idx = first.i          # ‘32nd’ will become part of street
    else:
        start_idx = 0
    # ── APARTMENT NUMBER (guarded by new helper) ─────────────────────
    tokens = list(doc)   
    is_apt, apt_val, consumed = _detect_apt(tokens, start_idx)

    if is_apt and tagged.apt_num is None:
        tagged.apt_num = apt_val
        start_idx += consumed

    # ── STREET & SUFFIX (ordinal tokens go in the “street” bucket) ───

    parts = []
    for tok in doc[start_idx:]:
        canon = _canonical_suffix(tok.text)
        if canon:
            tagged.st_suffix = canon
        elif tok.text in APT_HEAD_WORDS:
            break
        else:
            parts.append(tok.text)

    ALLOWED_PUNCT = "&"

    tagged.street_name =  " ".join(
        ch for ch in parts
            if ch.isalnum() or ch.isspace() or ch in ALLOWED_PUNCT
        ) or None
    return tagged

def _detect_apt(tokens: list[spacy.tokens.Token], idx: int) \
        -> tuple[bool, str | None, int]:
    """
    Examine tokens starting at **idx** to see whether they form an
    apartment / unit clause *immediately* after the house-number.

    Returns
    -------
    (is_apt?, apt_value_or_None, tokens_consumed)

    Handles
    -------
    #2              # 2            APT 2B            APT # 2B
    UNIT 4          SUITE 300-A    2B   (bare token)  5  (bare numeric)
    """
    if idx >= len(tokens):
        return False, None, 0

    tok = tokens[idx]

    if tok.text.startswith("#") and len(tok.text) > 1:
        return True, tok.text.lstrip("#"), 1
    
    if tok.text == "#" and idx + 1 < len(tokens):
        nxt = tokens[idx + 1]
        if _maybe_apt(nxt):
            return True, nxt.text, 2

    if tok.text.upper() in APT_HEAD_WORDS:
        j = idx + 1
        if j < len(tokens) and tokens[j].text == "#":   # skip optional '#'
            j += 1
        if j < len(tokens) and _maybe_apt(tokens[j]):
            return True, tokens[j].text.lstrip("#"), j - idx + 1

    if _maybe_apt(tok) and tok not in STREET_PREFIX_MAP:
        return True, tok.text, 1

    return False, None, 0

def _is_alphanumeric(token):
    """Check if the token text is alphanumeric."""
    return re.match("^([a-zA-Z]{1,2}-?\d{1,4}|\d{1,4}-?[a-zA-Z]{1,2})", token.text) is not None

def _apt_is_alphanumeric(text):
    """Check if the token text is alphanumeric."""
    return re.match("([a-zA-Z]{1,2}-?\d{1,4}|\d{1,4}-?[a-zA-Z]{1,2})", text) is not None

def _is_alpha(token):
    """Check if the token text is alpha"""
    return re.match("^(?!(?:N|S|E|W|NE|NW|SE|SW))[a-zA-Z]{1,2}$", token.text) is not None


def _is_ordinal(tok) -> bool:
    """True for '4th', '32ND', '101st', …"""
    return bool(ORDINAL_RE.fullmatch(tok.text))

def _maybe_apt(tok) -> bool:
    """Heuristic for apartment / unit IDs (excludes ordinals)."""
    return (
        not _is_ordinal(tok)
        and tok.lower_ not in spelled_out_numbers
        and (tok.like_num 
             or _is_alphanumeric(tok)
             or _is_alpha(tok))
    )

def _collapse_fraction(m: re.Match) -> str:
    whole, num, den = m.groups()
    value = int(whole) + int(num) / int(den)      # 915 + 1/2 → 915.5
    # stringify *once* so you don’t end up with 9150.5
    return f"{value:g}".rstrip(".")

_suffix_to_spellings = {}
for spelling, canon in street_type_map.items():
    _suffix_to_spellings.setdefault(canon, set()).add(spelling)

# Flat list of valid spellings for fuzzy match
_valid_spellings = [*street_type_map.keys()]

def _canonical_suffix(raw: str, cutoff: float = 0.90) -> str | None:
    """Return canonical suffix ('STREET', 'AVENUE', …) or None."""
    tok = raw.upper().rstrip(".")          # "Av." -> "AV"
    if tok in street_type_map:
        return street_type_map[tok]

# ------------------------------------------------------------------
#  ADDRESS ENRICHER – one-time loader you can reuse in callbacks etc.
# ------------------------------------------------------------------
class AddressEnricher:
    """
    Class for enriching raw address strings with ZIP code and city information using reference datasets.

    Attributes:
        _grouped (pd.DataFrameGroupBy): Grouped centerline data by canonical street name.
        _gold (np.ndarray): Unique canonical street names.
        _score_cut (int): Minimum fuzzy match score to accept a corrected street name.

    Methods:
        enrich(raw_address): Returns a dictionary with parsed and enriched address components.
    """
    def __init__(self,
                 centerline_path=get_file_path(".", 'raw/downloads', "Countywide_Street_Centerlines.csv"),
                 zipcode_path=get_file_path(".", 'raw/downloads', "Countywide_Zip_Codes.csv"),
                 all_real_estate_path=get_file_path(".","raw/home_sales","all_homes.csv"),
                 score_cut=80):
        
        #Load csv files
        center = pd.read_csv(centerline_path, low_memory=False)
        all_real_estate = pd.read_csv(all_real_estate_path, low_memory=False)
        address_parts = all_real_estate.set_index('parcel_number').to_dict(orient='index')
        CACHE_PATH = "C:/Users/markd/hamilton-county-homes-scraper-main/data/processed/address_cache.json"
        address_cache = load_cache_from_disk(CACHE_PATH)
        address_cache.update(address_parts)
        save_cache_to_disk(address_cache,CACHE_PATH)

        center['ZIPR'] = center['ZIPR'].replace(' ',np.nan).astype('Int64')
        center['ZIPL'] = center['ZIPL'].replace(' ',np.nan).astype('Int64')

        # group by street for fast range checks
        grouped = center[center["CLASS"].isin([2,3,4,5])].groupby(["STREET_NORM"])

        all_real_estate.amount = all_real_estate.amount.str.replace('$','').str.replace(',','').astype('Int64')
        all_real_estate['transfer_date'] = pd.to_datetime(all_real_estate.transfer_date)
        all_real_estate['day_of_week'] = all_real_estate['transfer_date'].dt.day_of_week
        all_real_estate['month_day'] = all_real_estate['transfer_date'].dt.day
        all_real_estate['month'] = all_real_estate['transfer_date'].dt.month
        all_real_estate['year'] = all_real_estate['transfer_date'].dt.year

        all_real_estate['home_type'] = all_real_estate['use'].astype('str').map(home_type_map)
        all_real_estate = pd.concat([all_real_estate,all_real_estate['bbb'].str.split('-',expand=True).rename(columns={0:'total_rooms',
                                                                1: 'bedrooms',
                                                                2: 'full_baths',
                                                                3: 'half_baths'
                                                            })], axis=1)
        
        all_real_estate['year_built'] = all_real_estate['year_built'].astype('Int64')
        all_real_estate['st_num'] = all_real_estate['st_num'].astype('float').round(0).astype('Int64')        
        lookups = build_interval_lookup(grouped=grouped)
        polygons = polygons.rename(columns={"AUDPTYID":'parcel_number'})
        polygons['parcel_number'] = polygons['parcel_number'].astype('str').str.strip()
        all_real_estate['parcel_number'] = all_real_estate['parcel_number'].str.replace('-','').str.strip()
        polygons = polygons.to_crs(epsg=3735) 
        polygons["centroid"] = polygons.geometry.centroid
        polygons["geometry"] = polygons.geometry
        # Compute centroids
        centroids_ll = polygons.set_geometry("centroid").to_crs(epsg=4326)
        polygons["lon"] = centroids_ll.geometry.x
        polygons["lat"] = centroids_ll.geometry.y

        merged_geo = all_real_estate.merge(polygons, on="parcel_number", how="left")
        return None

    # ---------- public --------------
    def enrich(self, raw_address: str) -> dict:
        """
        Enrich a raw address string by parsing components and attaching ZIP and city information.

        Args:
            raw_address (str): The raw, unstructured address string.

        Returns:
            dict: A dictionary with fields: st_num, apt_num, street, postal_code, street_corrected, city, state.
        """
        tags = tag_address(raw_address)          # your existing parser

        # nothing to do if we couldn't parse a street name
        if not tags["street_name"]:
            return {**tags, "postal_code": None, "street_corrected": None, "city": None}


# instantiate once so every downstream module can import & reuse it
address_enricher = AddressEnricher()

if os.environ.get("HCH_SCRAPER_SKIP_ENRICHER"):
    address_enricher = None
else:
    try:
        address_enricher = AddressEnricher()
    except Exception:
        address_enricher = None