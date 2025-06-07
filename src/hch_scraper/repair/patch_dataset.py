import time
import random

import pandas as pd

import hch_scraper.utils.logging_setup
from hch_scraper.utils.logging_setup import logger
from hch_scraper.repair.identify_missing import find_missing_rows
from hch_scraper.repair.fetch_missing_data import patch_data
from hch_scraper.driver_setup import init_driver
from hch_scraper.utils.io.navigation import safe_click
from hch_scraper.config.settings import  XPATHS, URLS
from hch_scraper.utils.data_extraction.form_helpers.data_formatting import clean_and_format_columns
from hch_scraper.utils.data_extraction.form_helpers.file_io import get_file_path
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
homes_path = get_file_path(BASE_DIR, "raw", "All Homes.csv")

BASE_URL = URLS['base']

homes = pd.read_csv(homes_path)

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

if __name__ == "__main__":
    logger.info(f"Starting patching process.")

    driver, wait = init_driver(BASE_URL)
    safe_click(wait,XPATHS["search"]["property_search"])
    
    missing_ids, missing_dates = find_missing_rows(homes, cols)

    output_path = homes_path.with_name('homes_all_patched.csv')

    for missing_id, date in zip(missing_ids, missing_dates):
        appraisal_table = patch_data(wait, driver, missing_id)
        mask = (homes['parcel_number'] == missing_id) & (homes['transfer_date'] == date)
        appraisal_table['address'] = homes.loc[mask, 'address'].values[0]
        appraisal_table = pd.DataFrame(appraisal_table)

        appraisal_table = clean_and_format_columns(appraisal_table, ['Transfer Date'])
    
        for col in cols:
            homes[col] = homes[col].astype(str)
            homes.loc[mask, col] = appraisal_table[col].values[0]
        homes.to_csv(output_path)
        time.sleep(random.uniform(4, 8))







