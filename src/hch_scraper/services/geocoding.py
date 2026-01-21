"""
Geocoding Utility for Address Enrichment

This module geocodes address strings using the PositionStack API and caches
results by parcel number to avoid redundant API calls. It supports batch
processing and saves a persistent cache to disk for reuse across runs.

Features:
- Uses `.env` file to load API key
- Supports JSON-based caching
- Robust error handling
- Designed for integration into a home sales scraping pipeline
"""

import os
import json
import pandas as pd
import http.client
import urllib.parse

from dotenv import load_dotenv

from hch_scraper.config.settings import URLS
from hch_scraper.utils.logging_setup import logger

# Load environment variables
load_dotenv()
API_KEY = os.getenv("API_KEY")

# API endpoint and cache location
BASE_API_URL = URLS["geocoding_api"]
CACHE_PATH = "data/processed/geocode_cache.json"


# Load cache from disk if it exists
def load_cache_from_disk(filepath=CACHE_PATH) -> dict:
    """
    Load previously saved geocoding results from a JSON file.

    Args:
        filepath (str): Path to the cache JSON file.

    Returns:
        dict: Dictionary mapping parcel numbers to geocoding results.
    """
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}


# Save updated cache to disk
def save_cache_to_disk(cache: dict, filepath=CACHE_PATH):
    """
    Save geocoding cache to disk as a JSON file.

    Args:
        cache (dict): Dictionary containing geocoded parcel data.
        filepath (str): File path to save the cache.
    """
    cache_dir = os.path.dirname(filepath)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(cache, f)


# In-memory cache
geocode_cache = load_cache_from_disk()


def get_geocodes(address: str, parcel_number: str) -> dict:
    """
    Geocode a given address using the PositionStack API, with caching.

    Args:
        address (str): The street address to geocode.
        parcel_number (str): Unique parcel number used as cache key.

    Returns:
        dict: Dictionary of geocoding results (lat/lon, ZIP, confidence, etc.)
    """
    if not API_KEY:
        raise ValueError("Missing API_KEY environment variable for geocoding.")

    if parcel_number in geocode_cache:
        return geocode_cache[parcel_number]

    conn = http.client.HTTPConnection("api.positionstack.com")
    params = urllib.parse.urlencode(
        {
            "access_key": API_KEY,
            "query": address,
            "region": "Ohio",
            "country": "US",
            "limit": 1,
        }
    )

    try:
        conn.request("GET", f"/v1/forward?{params}")
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        logger.debug(data.decode("utf-8"))
        data = json.loads(data.decode("utf-8"))

        if data.get("data"):
            hit = data["data"][0]
            city = (
                hit.get("locality")
                or hit.get("administrative_area")
                or hit.get("county")
            )
            state = hit.get("region_code") or hit.get("region")
            geocode = {
                "formatted_address": f"{hit.get('name')}, {city}, {state} {hit.get('postal_code')}",
                "longitude": hit.get("longitude"),
                "latitude": hit.get("latitude"),
                "house_num": hit.get("house_num"),
                "street_name": hit.get("street"),
                "api_city": city.upper() if city else None,
                "county": hit.get("county"),
                "api_state": state.upper() if state else None,
                "api_postal_code": hit.get("postal_code"),
                "confidence": hit.get("confidence"),
            }
        else:
            geocode = {
                k: None
                for k in [
                    "formatted_address",
                    "longitude",
                    "latitude",
                    "house_num",
                    "street_name",
                    "api_city",
                    "county",
                    "api_state",
                    "api_postal_code",
                    "confidence",
                ]
            }
    except Exception as e:
        logger.warning(f"Geocoding error for parcel {parcel_number}: {e}")
        geocode = {
            k: None
            for k in [
                "formatted_address",
                "longitude",
                "latitude",
                "house_num",
                "street_name",
                "api_city",
                "county",
                "api_state",
                "api_postal_code",
                "confidence",
            ]
        }

    # Save result to in-memory cache
    geocode_cache[parcel_number] = geocode
    return geocode


def geocode_until_complete(df: pd.DataFrame, batchsize: int = 10) -> pd.DataFrame:
    """
    Iteratively geocode rows in the DataFrame that lack latitude/longitude,
    using PositionStack and a persistent cache.

    Args:
        df (pd.DataFrame): The DataFrame containing 'parcel_number' and 'new_address'.
        batchsize (int): Number of parcels to geocode in each batch.

    Returns:
        pd.DataFrame: The enriched DataFrame with geocoded columns filled in.
    """
    logger.info(f"Starting geocoding loop on {df.shape[0]} rows")

    stall_counter = 0
    while df["lat"].isna().any() or df["lon"].isna().any():
        before = df["lat"].isna().sum()
        to_geocode = df[df["lat"].isna() | df["lon"].isna()]
        home_dict = dict(zip(to_geocode["parcel_number"], to_geocode["new_address"]))
        logger.info(f"Remaining to geocode: {len(home_dict)} parcels.")

        keys = list(home_dict.keys())
        for i in range(0, len(keys), batchsize):
            batch_keys = keys[i : i + batchsize]
            for parcel_number in batch_keys:
                address = home_dict[parcel_number]
                try:
                    geo = get_geocodes(address, parcel_number)
                    sel = df["parcel_number"] == parcel_number
                    cols = [
                        "formatted_address",
                        "lon",
                        "lat",
                        "house_num",
                        "street_name",
                        "api_city",
                        "county",
                        "api_state",
                        "api_postal_code",
                        "confidence",
                    ]
                    df.loc[sel, cols] = [geo[col] for col in cols]
                except Exception as e:
                    logger.warning(f"Failed to geocode parcel {parcel_number}: {e}")

        after = df["lat"].isna().sum()
        if after == before:
            stall_counter += 1
            if stall_counter >= 2:
                logger.warning("Geocoding stalled; exiting loop.")
                break
        else:
            stall_counter = 0

    save_cache_to_disk(geocode_cache)
    logger.info("Geocoding loop completed")
    return df
