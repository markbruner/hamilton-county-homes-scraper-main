import re
import os
import pandas as pd
import numpy as np

import rapidfuzz
from rapidfuzz import process, fuzz
import difflib
import spacy

from hch_scraper.utils.data_extraction.form_helpers.file_io import get_file_path

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

# Words that spaCy typically tags as numbers but should be treated as part
# of the street name when parsing addresses.  This includes cardinal and
# ordinal forms so that streets like "THIRTY-SECOND" are not mistaken for
# house numbers.
SPELLED_OUT_NUMBERS = {
    # cardinal numbers
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
    "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    # ordinal numbers
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
    "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
    "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
    "nineteenth", "twentieth", "thirtieth", "fortieth", "fiftieth",
    "sixtieth", "seventieth", "eightieth", "ninetieth",
}

def parse_house_number(st_num_str):
    """
    Extracts the leading integer portion of a street number string.

    Args:
        st_num_str (str): A string representing a street number, such as '123A' or '4917-'.

    Returns:
        int or None: The integer prefix if found; otherwise, None.
    """
    if not st_num_str or not isinstance(st_num_str, str):
        return None
    # Match one or more digits at the start
    m = re.match(r"\s*(\d+)", st_num_str)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None

def add_zip_code(df: pd.DataFrame,
                 centerline_path: str = get_file_path(".", 'raw', "Countywide_Street_Centerlines.csv"),
                 address_col: str = "Address") -> pd.DataFrame:
    """
    Adds ZIP code information to a DataFrame based on address matching with centerline data.

    Args:
        df (pd.DataFrame): The DataFrame containing raw address data.
        centerline_path (str): File path to the Countywide_Street_Centerlines CSV.
        address_col (str): Column name in the DataFrame that contains full street addresses.

    Returns:
        pd.DataFrame: A copy of the input DataFrame with added 'postal_code' and corrected 'address' columns.

    Raises:
        ValueError: If required columns are missing from the centerline file.
    """
    # --- load & prepare centerline reference ------------------------
    center = pd.read_csv(centerline_path, low_memory=False)
    for col in ["NAME", "L_F_ADD", "L_T_ADD", "R_F_ADD",
                "R_T_ADD", "ZIPL", "ZIPR", "zip_code", "city"]:
        if col not in center.columns:
            raise ValueError(f"Centerline CSV missing expected column '{col}'")

    center["CANON"] = center["NAME,.  "]
    gold = center["CANON"].unique()

    # group by street for fast range checks
    grouped = center.groupby("CANON")

    df = df.copy()
    df["postal_code"] = df[address_col].apply(lambda a: _zip_for_row(a, grouped, gold))
    df["address"] = df[address_col].apply(
        lambda a: fuzzy_match_street_name(a, gold)
    )
    return df

def _zip_for_row(address: str, grouped: pd.core.groupby.generic.DataFrameGroupBy, gold) -> str:
    """Return the ZIP code for a raw address string using centerline ranges."""
    tags = tag_address(address)
    street = tags.get("street")
    if not street:
        return None

    if street not in grouped.groups:
        street = fuzzy_match_street_name(street, gold)
    if street not in grouped.groups:
        return None

    hnum = parse_house_number(tags.get("st_num"))
    if hnum is None:
        return None

    segs = grouped.get_group(street)
    seg = segs.loc[
        ((segs.L_F_ADD <= hnum) & (hnum <= segs.L_T_ADD)) |
        ((segs.R_F_ADD <= hnum) & (hnum <= segs.R_T_ADD))
    ]
    if seg.empty:
        return None

    seg = seg.iloc[0]
    if hnum % 2 == 0:
        return seg.ZIPL if seg.L_F_ADD % 2 == 0 else seg.ZIPR
    return seg.ZIPR if seg.R_F_ADD % 2 == 1 else seg.ZIPL

def fuzzy_match_street_name(bad, valid_names, score_cut=80):
    cand, score, _ = process.extractOne(
        bad, valid_names, scorer=fuzz.token_set_ratio
    )
    return cand if cand and score >= score_cut else bad

def correct_street_name_fuzzy(street_name, valid_names, cutoff=0.8):
    matches = difflib.get_close_matches(street_name, valid_names, n=1, cutoff=cutoff)
    return matches[0] if matches else street_name

def tag_address(address: str) -> dict:
    """Parse an address string into components.

    This helper attempts to extract a house number, an optional apartment
    identifier and the street name.  Tokens that spaCy marks as ``NUM`` but
    appear in ``SPELLED_OUT_NUMBERS`` are treated as normal words so that
    streets like "THIRTY-SECOND" are handled correctly.
    """
    if not isinstance(address, str) or not address.strip():
        return {"st_num": None, "apt_num": None, "street": None}
    
    doc = list(nlp(address))
    tagged = {"st_num": None, "apt_num": None, "street": None}

    start_idx = 0

    if doc and doc[0].pos_ == "NUM" and doc[0].text.lower() not in SPELLED_OUT_NUMBERS:
        tagged["st_num"] = doc[0].text
        start_idx = 1

    if len(doc) > start_idx:
        tok = doc[start_idx]
        if _is_alphanumeric(tok) and tok.text.lower() not in SPELLED_OUT_NUMBERS:
            tagged["apt_num"] = tok.text
            start_idx += 1
        elif tok.pos_ == "NUM" and tok.text.lower() not in SPELLED_OUT_NUMBERS:
            tagged["apt_num"] = tok.text
            start_idx += 1

    if len(doc) > start_idx:
        tagged["street"] = " ".join(t.text for t in doc[start_idx:])

    return tagged

def _is_alphanumeric(token):
    """Check if the token text is alphanumeric."""
    return re.match("^(?=.*[0-9])(?=.*[a-zA-Z])[a-zA-Z0-9]+$", token.text) is not None

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
                 centerline_path=get_file_path(".", 'raw', "Countywide_Street_Centerlines.csv"),
                 zipcode_path=get_file_path(".", 'raw', "Countywide_Zip_Codes.csv"),
                 score_cut=80):
        
        #Load csv files
        center = pd.read_csv(centerline_path, low_memory=False)
        zip_df = pd.read_csv(zipcode_path, low_memory=False)

        #Prepare zip to city mapping
        zip_map = (
            zip_df[["ZIPCODE", "USPSCITY"]]
            .dropna(subset=["ZIPCODE", "USPSCITY"])
            .drop_duplicates("ZIPCODE")
            .rename(columns={"ZIPCODE": "zip_code", "USPSCITY": "city"})
        )
        center.loc[center["ZIPL"]==' ',"ZIPL"] = 0
        center.loc[center["ZIPR"]==' ',"ZIPR"] = 0
        # In centerlines, pick one ZIP per segment
        center["zip_code"] = center["ZIPL"].fillna(center["ZIPR"]).fillna(0).astype(int)

        # 4. Merge (no duplicates in centerlines)
        center = center.merge(zip_map, on="zip_code", how="left")

        needed = ["NAME", "L_F_ADD", "L_T_ADD",
                  "R_F_ADD", "R_T_ADD", "ZIPL", "ZIPR", "zip_code", "city"]
        missing = [c for c in needed if c not in center.columns]
        if missing:
            raise ValueError(f"Centerline CSV missing {missing}")

        center["CANON"] = center["NAME"]
        self._grouped  = center.groupby("CANON")
        self._gold     = center["CANON"].unique()
        self._score_cut = score_cut

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
        if not tags["street"]:
            return {**tags, "postal_code": None, "street_corrected": None, "city": None}

        canon_street = tags["street"]

        if canon_street not in self._grouped.groups:
            canon_street = fuzzy_match_street_name(
                canon_street, self._gold, score_cut=self._score_cut
            )
        # Still None?  Return tags unchanged
        if canon_street is None or canon_street not in self._grouped.groups:
            return {**tags, "postal_code": None, "street_corrected": None, "city": None}

        # ZIP via range logic --------------------------------------
        hnum = parse_house_number(tags.get("st_num"))
        zip_code = None
        city = None
        segs = self._grouped.get_group(canon_street)
        if hnum is not None:
            seg = segs.loc[
                ((segs.L_F_ADD <= hnum) & (hnum <= segs.L_T_ADD)) |
                ((segs.R_F_ADD <= hnum) & (hnum <= segs.R_T_ADD))
            ]
            if not seg.empty:
                seg = seg.iloc[0]
                city = seg.city
                if hnum % 2 == 0:
                    zip_code = seg.ZIPL if seg.L_F_ADD % 2 == 0 else seg.ZIPR
                else:
                    zip_code = seg.ZIPR if seg.R_F_ADD % 2 == 1 else seg.ZIPL
        else:
            # When no house number is provided, fall back to any unique
            # city/ZIP listed for the street in the centerlines dataset.
            cities = segs.city.dropna().unique()
            if len(cities) == 1:
                city = cities[0]
            zips = pd.concat([segs.ZIPL, segs.ZIPR]).dropna().unique()
            if len(zips) == 1:
                zip_code = zips[0]

        return {
            **tags,
            "postal_code": zip_code,
            "street_corrected": canon_street,
            "city": city,
            "state":"Ohio",
        }


# instantiate once so every downstream module can import & reuse it
# address_enricher = AddressEnricher()

if os.environ.get("HCH_SCRAPER_SKIP_ENRICHER"):
    address_enricher = None
else:
    try:
        address_enricher = AddressEnricher()
    except Exception:
        address_enricher = None