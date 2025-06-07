import os
import json
import pandas as pd
import requests

from dotenv import load_dotenv
import http.client, urllib.parse

import hch_scraper.utils.logging_setup  
from hch_scraper.config.settings import URLS
from hch_scraper.utils.logging_setup import logger

# Load environment variables once
load_dotenv()
API_KEY = os.getenv("API_KEY")

# Getting the API url.
BASE_API_URL = URLS['geocoding_api']

# Optional persistent cache file
CACHE_PATH = "data/processed/geocode_cache.json"

def load_cache_from_disk(filepath=CACHE_PATH):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}

def save_cache_to_disk(cache, filepath=CACHE_PATH):
    with open(filepath, "w") as f:
        json.dump(cache, f)

# In-memory cache (loaded from disk)
geocode_cache = load_cache_from_disk()

def get_geocodes(address: str, parcel_number: str) -> dict:
    """
    Geocode an address; cached by parcel.

    Returns keys:
      formatted_address, longitude, latitude, city, state
    """
    if parcel_number in geocode_cache:
        return geocode_cache[parcel_number]

    conn = http.client.HTTPConnection('api.positionstack.com')
    params = urllib.parse.urlencode({
        "access_key": API_KEY,
        "query":      address,
        "region":     "OH",     # ⇢ helps disambiguate
        "country":    "US",
        "limit":      1
    })


    try:
        conn.request('GET', '/v1/forward?{}'.format(params))
        resp = conn.getresponse()
        data = resp.read()
        print(data.decode('utf-8'))
        if data:
            hit   = data[0]
            city  = (hit.get("locality")
                     or hit.get("administrative_area")
                     or hit.get("county"))
            state = hit.get("region_code") or hit.get("region")
            geocode = {
                "formatted_address": hit.get("label"),
                "longitude": hit.get("longitude"),
                "latitude":  hit.get("latitude"),
                "city":  city.upper() if city else None,
                "state": state.upper() if state else None,
            }
        else:
            geocode = {
                "formatted_address": None,
                "longitude": None,
                "latitude": None,
                "city": None,
                "state": None,
            }
    except Exception as e:
        logger.warning(f"Geocoding error for parcel {parcel_number}: {e}")
        geocode = {
            "formatted_address": None,
            "longitude": None,
            "latitude": None,
            "city": None,
            "state": None,
        }

    geocode_cache[parcel_number] = geocode
    return geocode

def geocode_until_complete(final_df: pd.DataFrame, batchsize: int = 10) -> pd.DataFrame:
    logger.info(f"Starting geocoding loop on {final_df.shape[0]} rows")

    if "parcel_number" not in final_df.columns:
        final_df = final_df.rename(columns={"Parcel Number": "parcel_number"})

    stall_counter = 0          # detects when nothing changes
    while final_df["latitude"].isna().any() or final_df["longitude"].isna().any():
        before = final_df["latitude"].isna().sum()

        to_geocode = final_df[final_df["latitude"].isna() | final_df["longitude"].isna()]
        home_dict  = dict(zip(to_geocode["parcel_number"], to_geocode["new_address"]))
        logger.info(f"Remaining to geocode: {len(home_dict)} parcels.")

        keys = list(home_dict.keys())
        for i in range(0, len(keys), batchsize):
            batch_keys = keys[i : i + batchsize]
            for parcel_number in batch_keys:
                address = home_dict[parcel_number]
                try:
                    geo = get_geocodes(address, parcel_number)
                    sel = final_df["parcel_number"] == parcel_number

                    final_df.loc[sel, ["formatted_address",
                                       "longitude", "latitude",
                                       "city", "state"]] = [
                        geo["formatted_address"],
                        geo["longitude"],
                        geo["latitude"],
                        geo["city"],
                        geo["state"],
                    ]
                except Exception as e:
                    logger.warning(f"Failed to geocode parcel {parcel_number}: {e}")

        after = final_df["latitude"].isna().sum()
        if after == before:          # nothing changed this pass → break
            stall_counter += 1
            if stall_counter >= 2:
                logger.warning("Geocoding stalled; exiting loop.")
                break
        else:
            stall_counter = 0

    save_cache_to_disk(geocode_cache)
    logger.info("Geocoding loop completed")
    return final_df