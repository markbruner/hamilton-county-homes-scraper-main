import re
import pandas as pd
import numpy as np

import rapidfuzz
from rapidfuzz import process, fuzz
import difflib
import spacy

from hch_scraper.config.mappings.street_map import street_type_map
from hch_scraper.config.mappings.direction_map import direction_map
from hch_scraper.utils.data_extraction.form_helpers.file_io import get_file_path

nlp = spacy.load("en_core_web_sm")


def _zip_for_row(address: str, grouped: pd.core.groupby.generic.DataFrameGroupBy, gold) -> str:
    """Return the ZIP code for a raw address string using centerline ranges."""
    tags = tag_address(address)
    street = tags.get("street")
    if not street:
        return None

    if street not in grouped.groups:
        street = _closest_name(street, gold)
    if street not in grouped.groups:
        return None

    hnum = int(tags["st_num"]) if tags.get("st_num") else None
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

def _closest_name(bad, valid_names, score_cut=80):
    cand, score, _ = process.extractOne(
        bad, valid_names, scorer=fuzz.token_set_ratio
    )
    return cand if cand and score >= score_cut else bad

def add_zip_code(df: pd.DataFrame,
                 centerline_path: str = get_file_path(".", 'raw', "Countywide_Street_Centerlines.csv"),
                 address_col: str = "Address") -> pd.DataFrame:
    """
    Return a copy of df with a new 'ZIP' column.
    Requires df[address_col] to contain full street addresses as scraped.
    """
    # --- load & prepare centerline reference ------------------------
    center = pd.read_csv(centerline_path, low_memory=False)
    for col in ["STRLABEL", "L_F_ADD", "L_T_ADD", "R_F_ADD",
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
        lambda a: _closest_name(a, gold)
    )
    return df

def is_alphanumeric(token):
    """Check if the token text is alphanumeric."""
    return re.match("^(?=.*[0-9])(?=.*[a-zA-Z])[a-zA-Z0-9]+$", token.text) is not None

def correct_street_name_fuzzy(street_name, valid_names, cutoff=0.8):
    matches = difflib.get_close_matches(street_name, valid_names, n=1, cutoff=cutoff)
    return matches[0] if matches else street_name

def tag_address(address):
    """
    Tag the components of the address using the defined pattern.
    Returns a dictionary with the components tagged.
    """
    if not isinstance(address, str) or not address.strip():
        return {"st_num": None, "apt_num": None, "street": None}
    # List of spelled-out numbers to exclude from being tagged as 'NUM'
    spelled_out_numbers = {
        "zero", "one", "two", "three", "four", "five", "six", "seven", 
        "eight", "nine", "ten", "eleven", "twelve", "thirteen", 
        "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", 
        "nineteen", "twenty"
    }    
    # Initialize the spaCy model and Matcher
    doc = nlp(address)
    tagged_components = {"st_num": None, "apt_num": None, "street": None}

    # Loop through the tokens to find matches based on conditions
    for i, token in enumerate(doc):
        if i == 0 and token.pos_ == "NUM" and token.text.lower() not in spelled_out_numbers:
            tagged_components["st_num"] = token.text
        elif i == 1 and is_alphanumeric(token) and token.text.lower() not in spelled_out_numbers:
            tagged_components["apt_num"] = token.text
        elif i == 1 and token.pos_=="NUM"and token.text.lower() not in spelled_out_numbers:
            tagged_components["apt_num"] = token.text
        elif i > 0:
            # Concatenate the remaining tokens as the street name
            tagged_components["street"] = " ".join([tok.text for tok in doc[i:]])
            break
    return tagged_components

# ------------------------------------------------------------------
#  ADDRESS ENRICHER – one-time loader you can reuse in callbacks etc.
# ------------------------------------------------------------------
class AddressEnricher:
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

        needed = ["STRLABEL", "L_F_ADD", "L_T_ADD",
                  "R_F_ADD", "R_T_ADD", "ZIPL", "ZIPR", "zip_code", "city"]
        missing = [c for c in needed if c not in center.columns]
        if missing:
            raise ValueError(f"Centerline CSV missing {missing}")

        center["CANON"] = center["STRLABEL"]
        self._grouped  = center.groupby("CANON")
        self._gold     = center["CANON"].unique()
        self._score_cut = score_cut

    # ---------- public --------------
    def enrich(self, raw_address: str) -> dict:
        """
        Split the raw string, correct the street name, attach ZIP,
        and return everything in one dict.
        """
        tags = tag_address(raw_address)          # your existing parser

        # nothing to do if we couldn't parse a street name
        if not tags["street"]:
            return {**tags, "postal_code": None, "street_corrected": None, "city": None}

        canon_street = tags["street"]

        if canon_street not in self._grouped.groups:
            canon_street = _closest_name(
                canon_street, self._gold, score_cut=self._score_cut
            )
        # Still None?  Return tags unchanged
        if canon_street is None or canon_street not in self._grouped.groups:
            return {**tags, "postal_code": None, "street_corrected": None, "city": None}

        # ZIP via range logic --------------------------------------
        hnum = int(tags["st_num"]) if tags["st_num"] else None
        zip_code = None
        city = None
        if hnum is not None:
            segs = self._grouped.get_group(canon_street)
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

        return {
            **tags,
            "postal_code": zip_code,
            "street_corrected": canon_street,
            "city": city,
            "state":"Ohio",
        }


# instantiate once so every downstream module can import & reuse it
address_enricher = AddressEnricher()