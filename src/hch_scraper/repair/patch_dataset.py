"""
Patch Missing Home Records Script

This script reads a master CSV of home parcel data, identifies rows
with missing key fields, and “patches” them by re-scraping the auditor’s
site for the missing details. The updated fields are merged back into
the DataFrame and written out to a new CSV.

Workflow:
1. Load the existing homes CSV.
2. Identify parcels with any nulls in the specified columns.
3. Launch Selenium and navigate to the property search screen.
4. For each missing parcel:
   a. Re-fetch the record via `patch_data`.
   b. Merge the returned table into the master DataFrame.
   c. Clean & format the new data.
   d. Save progress incrementally to a new CSV.
   e. Throttle requests with a random sleep.
"""

import time
import random
from pathlib import Path
import re

import pandas as pd
import numpy as np
import geopandas as gpd

# Logging
from hch_scraper.utils.logging_setup import logger

# Geocoding
from hch_scraper.geocoding import geocode_until_complete

# Utilities for repairing missing data
from hch_scraper.repair.fetch_missing_data import patch_data, find_missing_rows

# Selenium driver setup and navigation helpers
from hch_scraper.driver_setup import init_driver
from hch_scraper.utils.io.navigation import safe_click

# Configuration constants
from hch_scraper.config.settings import XPATHS, URLS
from hch_scraper.config.mappings import street_type_map

# Data formatting helper
from hch_scraper.utils.data_extraction.form_helpers.data_formatting import clean_and_format_columns
from hch_scraper.utils.data_extraction.address_cleaners import tag_address, add_zip_code

# File I/O helper
from hch_scraper.utils.data_extraction.form_helpers.file_io import get_file_path


# -----------------------------------------------------------------------------
# Constants and Paths
# -----------------------------------------------------------------------------

# Base directory is two levels up from this file
BASE_DIR = Path(__file__).resolve().parents[3]

# Paths to the raw homes and polygon CSVs
homes_path = get_file_path(BASE_DIR, "raw/home_sales", "homes_01012003_12312003.csv")
zipcode_path=get_file_path(BASE_DIR, 'raw/downloads', "Countywide_Zip_Codes.csv")
polygon_geojson_path = get_file_path(BASE_DIR, "raw/downloads", "Hamilton_County_Parcel_Polygons.geojson")

# Base URL for the auditor’s site
BASE_URL = URLS['base']

# -----------------------------------------------------------------------------
# Main patching routine
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Log start
    logger.info("Starting patching process for homes with missing fields.")

    # 2. Read in existing CSV of all homes and polygons
    homes = pd.read_csv(homes_path)
    homes['parcel_number'] = homes['parcel_number'].str.replace('-','').str.strip()
    zipcodes = pd.read_csv(zipcode_path)

    polygons = gpd.read_file(polygon_geojson_path)
    polygons = polygons.to_crs(epsg=3735) 
    polygons["centroid"] = polygons.geometry.centroid
    polygons["geometry"] = polygons.geometry
    # Compute centroids
    centroids_ll = polygons.set_geometry("centroid").to_crs(epsg=4326)
    polygons["lon"] = centroids_ll.geometry.x
    polygons["lat"] = centroids_ll.geometry.y


    keep_cols = [
        "AUDPTYID",        # parcel key (will rename to parcel_number)
        "CONVEY_NO",       # conveyance number
        "DEEDNO",          # deed identifier
        "ACREDEED",        # acreage
        "SCHOOL_CODE_DIS", # school district code/description
        "MKTLND",          # market land value
        "MKTIMP",          # market improvement value
        "MKT_TOTAL_VAL",   # total market value
        "ANNUAL_TAXES",    # annual taxes
        "FRONT_FOOTAGE",   # frontage length
        "SHAPEAREA",       # parcel area
        "SHAPELEN",        # parcel perimeter/length
        "geometry",
        "centroid",
        "lon",
        "lat",
    ]

    polygons = polygons[keep_cols].rename(columns={"AUDPTYID":'parcel_number'})
    polygons['parcel_number'] = polygons['parcel_number'].astype('str').str.strip()
    merged = homes.merge(polygons, on="parcel_number", how="left")

    # Storing the merged columns in order to remove the columns created from geocoding longitude and latitude.
    final_cols = merged.columns.to_list()


    logger.info("Beginning replacing of the street type (i.e. dr, rd, way, etc...) with the new mapping.")    
    pattern = r'\b(' + '|'.join(map(re.escape, street_type_map.keys())) + r')\b'
    merged['address'] = merged['address'].str.replace(
                            pattern,
                            lambda m: street_type_map[m.group(0)],
                            regex=True
                        )
    
        # Address processing
    logger.info("Processing address columns for geocoding.")
    address_parts = [
    {**tag_address(address), 'parcel_number': parcel}
    for parcel, address in zip(merged.parcel_number, merged.address)
    ]

    address_df = pd.DataFrame.from_dict(address_parts)
    address_df = address_df.drop_duplicates().dropna()
    merged = merged.merge(address_df, on='parcel_number',how='left')

    merged = add_zip_code(merged)

    merged['postal_code'] = merged['postal_code'].astype('str')
    zipcodes['ZIPCODE'] = zipcodes['ZIPCODE'].astype('str')

    merged = (merged.merge(zipcodes[['ZIPCODE','USPSCITY', 'state']], left_on='postal_code', right_on='ZIPCODE', how='left')
              .rename(columns={'USPSCITY':'city'}))

    merged["new_address"] = (
        merged["st_num"]
        .str.cat(merged["street"], sep=" ")
        .str.cat(merged["city"], sep=" ", na_rep="Cincinnati")
        .str.cat(merged["state"], sep=", ", na_rep="Ohio")
        .str.cat(merged["postal_code"], sep=" ")
        # collapse any accidental doubled spaces
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    final_cols.append('city')    
    final_cols.append('state')
    final_cols.append('postal_code')
    merged = merged[~merged['parcel_number'].isna()]

    merged = geocode_until_complete(merged)
    merged = merged[final_cols]

    # 3. Launch Selenium WebDriver and navigate to the parcel search screen
    driver, wait = init_driver(BASE_URL)
    safe_click(wait, XPATHS["search"]["property_search"])

    # 4. Identify which rows have nulls in any of the required columns
    missing_ids, missing_dates = find_missing_rows(merged)

    # 5. Prepare output file path
    output_path = homes_path.with_name('homes_all_patched.csv')

    # 6. Loop over each parcel with missing data
    for missing_id, transfer_date in zip(missing_ids, missing_dates):
        # Scrape the missing details for this parcel
        property_info_table = patch_data(wait, driver, missing_id)

        # Build a boolean mask for the exact row to update
        mask = (
            (merged['parcel_number'] == missing_id) &
            (merged['transfer_date'] == transfer_date)
        )

        # Ensure it’s a DataFrame (patch_data may return dict-like)
        property_info_table = pd.DataFrame(property_info_table)

        # Save the incrementally updated CSV
        merged.to_csv(output_path, index=False)
        logger.info(f"Patched parcel {missing_id} and saved to {output_path}")

        # Randomized delay to reduce server load and avoid being blocked
        time.sleep(random.uniform(4, 8))

    # 7. Close the WebDriver when done
    driver.quit()
    logger.info("Patching process complete.")
