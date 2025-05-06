import os
import json
import requests

from dotenv import load_dotenv

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
    Geocode an address using the parcel number as cache key.

    Returns a dict with: formatted_address, longitude, latitude.
    """
    if parcel_number in geocode_cache:
        logger.info(f"Cache hit for parcel {parcel_number}")
        return geocode_cache[parcel_number]

    logger.info(f"Geocoding parcel {parcel_number}: {address}")
    params = {
        'access_key': API_KEY,
        'query': address,
        'limit': 1
    }

    try:
        response = requests.get(BASE_API_URL, params=params)
        response.raise_for_status()
        result = response.json()
        data = result.get('data', [])
        if isinstance(data, list) and data:
            location = data[0]
            geocode = {
                'formatted_address': location.get('name'),
                'longitude': location.get('longitude'),
                'latitude': location.get('latitude')
            }
        else:
            geocode = {'formatted_address': None, 'longitude': None, 'latitude': None}
    except Exception as e:
        logger.warning(f"Geocoding error for parcel {parcel_number}: {e}")
        geocode = {'formatted_address': None, 'longitude': None, 'latitude': None}

    geocode_cache[parcel_number] = geocode
    return geocode

def geocode_until_complete(final_df, batchsize=10):
    logger.info("Starting geocoding loop...")

    while final_df['latitude'].isna().sum() > 0 or final_df['longitude'].isna().sum() > 0:
        to_geocode_df = final_df[final_df['latitude'].isna() | final_df['longitude'].isna()]
        home_dict = dict(zip(to_geocode_df['parcel_number'], to_geocode_df['new_address']))

        logger.info(f"Remaining to geocode: {len(home_dict)} parcels.")

        keys = list(home_dict.keys())
        for i in range(0, len(keys), batchsize):
            batch_keys = keys[i:i + batchsize]
            batch = {k: home_dict[k] for k in batch_keys}

            for parcel_number, address in batch.items():
                try:
                    geocodes = get_geocodes(address, parcel_number)
                    final_df.loc[final_df['parcel_number'] == parcel_number, 'formatted_address'] = geocodes['formatted_address']
                    final_df.loc[final_df['parcel_number'] == parcel_number, 'longitude'] = geocodes['longitude']
                    final_df.loc[final_df['parcel_number'] == parcel_number, 'latitude'] = geocodes['latitude']
                except Exception as e:
                    logger.warning(f"Failed to geocode parcel {parcel_number} ({address}): {e}")

    save_cache_to_disk(geocode_cache)
    logger.info("✅ All geocoding completed!")
    return final_df