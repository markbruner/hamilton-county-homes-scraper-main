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

import pandas as pd

# Logging
from hch_scraper.utils.logging_setup import logger

# Utilities for repairing missing data
from hch_scraper.repair.fetch_missing_data import patch_data, find_missing_rows

# Selenium driver setup and navigation helpers
from hch_scraper.driver_setup import init_driver
from hch_scraper.utils.io.navigation import safe_click

# Configuration constants
from hch_scraper.config.settings import XPATHS, URLS

# Data formatting helper
from hch_scraper.utils.data_extraction.form_helpers.data_formatting import clean_and_format_columns

# File I/O helper
from hch_scraper.utils.data_extraction.form_helpers.file_io import get_file_path


# -----------------------------------------------------------------------------
# Constants and Paths
# -----------------------------------------------------------------------------

# Base directory is two levels up from this file
BASE_DIR = Path(__file__).resolve().parents[2]

# Path to the raw homes CSV
homes_path = get_file_path(BASE_DIR, "raw", "All Homes.csv")

# Base URL for the auditor’s site
BASE_URL = URLS['base']

# Columns that must not be missing in the homes DataFrame
cols = [
    'total_rooms',
    'bedrooms',
    'full_baths',
    'half_baths',
    'conveyance_number',
    'deed_type',
    'acreage',
    'school_district'
]


# -----------------------------------------------------------------------------
# Main patching routine
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Log start
    logger.info("Starting patching process for homes with missing fields.")

    # 2. Read in existing CSV of all homes
    homes = pd.read_csv(homes_path)

    # 3. Launch Selenium WebDriver and navigate to the parcel search screen
    driver, wait = init_driver(BASE_URL)
    safe_click(wait, XPATHS["search"]["property_search"])

    # 4. Identify which rows have nulls in any of the required columns
    missing_ids, missing_dates = find_missing_rows(homes, cols)

    # 5. Prepare output file path
    output_path = homes_path.with_name('homes_all_patched.csv')

    # 6. Loop over each parcel with missing data
    for missing_id, transfer_date in zip(missing_ids, missing_dates):
        # a. Scrape the missing details for this parcel
        appraisal_table = patch_data(wait, driver, missing_id)

        # b. Build a boolean mask for the exact row to update
        mask = (
            (homes['parcel_number'] == missing_id) &
            (homes['transfer_date'] == transfer_date)
        )

        # c. Copy over the original address into the scraped table
        appraisal_table['address'] = homes.loc[mask, 'address'].values[0]

        # d. Ensure it’s a DataFrame (patch_data may return dict-like)
        appraisal_table = pd.DataFrame(appraisal_table)

        # e. Clean and standardize column formats (e.g., Transfer Date)
        appraisal_table = clean_and_format_columns(appraisal_table, ['Transfer Date'])

        # f. Write each patched value back into the homes DataFrame
        for col in cols:
            # Cast homes column to string to avoid type mismatches
            homes[col] = homes[col].astype(str)
            homes.loc[mask, col] = appraisal_table[col].values[0]

        # g. Save the incrementally updated CSV
        homes.to_csv(output_path, index=False)
        logger.info(f"Patched parcel {missing_id} and saved to {output_path}")

        # h. Randomized delay to reduce server load and avoid being blocked
        time.sleep(random.uniform(4, 8))

    # 7. Close the WebDriver when done
    driver.quit()
    logger.info("Patching process complete.")
