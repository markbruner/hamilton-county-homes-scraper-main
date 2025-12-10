"""
fetch_missing_data.py

Provides utilities to re-query and patch missing property details
for the Hamilton County Auditor scraper when initial extraction fails.

Functions:
    extract_patched_property_details(driver, id, wait)
        Scrapes and cleans the appraisal table for a given parcel ID.

    patch_data(wait, driver, missing_id)
        Performs a lookup by parcel ID, extracts the patched details,
        then resets the search form for the next query.
"""

from typing import List, Tuple
import pandas as pd
import numpy as np

from hch_scraper.config.settings import XPATHS
from hch_scraper.utils.logging_setup import logger
from hch_scraper.io.downloads import scrape_table_by_xpath
from hch_scraper.io.navigation import safe_click
from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import (
    fill_form_field,
    get_text,
)
from hch_scraper.utils.data_extraction.table_extraction import transform_table


def find_missing_rows(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    """
    Identify rows where any of a set of required columns are missing.

    This function scans the DataFrame for nulls in any of the specified
    required_columns. It returns two lists:
      1. parcel_numbers: the parcel IDs for rows with missing data.
      2. transfer_dates: the transfer dates for those same rows.

    Args:
        df (pd.DataFrame): The full dataset containing at least the
            columns in required_columns plus 'parcel_number' and 'transfer_date'.

    Returns:
        Tuple[List[str], List[str]]:
            - parcel_numbers: list of values from 'parcel_number' where
              any required column is null.
            - transfer_dates: list of values from 'transfer_date' corresponding
              to those same rows.
    """
    # Filter rows where any of the required columns is null
    key_cols = [
        "ACREDEED",
        "SCHOOL_CODE_DIS",
        "MKTLND",
        "MKTIMP",
        "MKT_TOTAL_VAL",
        "ANNUAL_TAXES",
    ]

    mask = df[key_cols].isnull().any(axis=1)

    # Extract the parcel numbers and transfer dates for those rows
    parcel_numbers = df.loc[mask, "parcel_number"].to_list()
    transfer_dates = df.loc[mask, "transfer_date"].to_list()

    return parcel_numbers, transfer_dates


def extract_patched_property_details(driver, id, wait):
    """
    Scrape and return a cleaned appraisal DataFrame for a single parcel.

    This is used when the initial bulk scrape missed a parcel,
    so we navigate directly by parcel ID and pull the appraisal details.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        id (str): Parcel identifier to look up.
        wait (WebDriverWait): WebDriverWait for explicit waits.

    Returns:
        pd.DataFrame or None:
            - A DataFrame with:
                • cleaned and renamed appraisal columns
                • added 'parcel_id' and 'school_district' columns
            - None if scraping fails or the table is empty.
    """
    try:
        if id == np.nan:
            logger.warning(f"Parcel ID is {id}.")
            return None

        # 1. Scrape the appraisal table for this parcel
        appraisal_table = scrape_table_by_xpath(
            wait, XPATHS["view"]["appraisal_information"]
        )
        tax_table = scrape_table_by_xpath(wait, XPATHS["view"]["tax_summary"])

        # 2. Bail out if no data found
        if appraisal_table is None or appraisal_table.empty:
            logger.warning(f"Appraisal table is empty for parcel {id}.")
            return None

        if tax_table is None or tax_table.empty:
            logger.warning(f"Tax table is empty for parcel {id}.")
            return None

        # 3. Normalize the table structure
        appraisal_table = transform_table(appraisal_table)
        tax_table = transform_table(tax_table)

        # 4. Drop columns we don’t need
        appraisal_keep_cols = ["Conveyance Number", "Deed Number", "Acreage"]
        appraisal_drop_list = [
            c for c in appraisal_keep_cols if c not in appraisal_table.columns
        ]
        appraisal_table.drop(appraisal_drop_list, axis=1, inplace=True)

        appraisal_table["parcel_number"] = id
        appraisal_table["SCHOOL_CODE_DIS"] = get_text(
            driver, wait, XPATHS["property"]["school_district"]
        )
        appraisal_table["ANNUAL_TAXES"] = get_text(
            driver, wait, XPATHS["property"]["annual_tax"]
        )

        tax_keep_cols = [
            "Market Land Value",
            "Market Improvement Value",
            "Market Total Value",
        ]
        tax_drop_list = [c for c in tax_keep_cols if c not in tax_table.columns]
        tax_table.drop(tax_drop_list, axis=1, inplace=True)

        tax_table["parcel_number"] = id

        parcel_info = appraisal_table.merge(tax_table, on="parcel_number")

        # 5. Rename numeric count columns for clarity
        parcel_info.rename(
            {
                "Conveyance Number": "CONVEY_NO",
                "Deed Number": "DEEDNO",
                "Acreage": "ACREDEED",
                "Market Land Value": "MKTLND",
                "Market Improvement Value": "MKTIMP",
                "Market Total Value": "MKT_TOTAL_VAL",
            },
            axis=1,
            inplace=True,
        )

        return parcel_info

    except Exception as e:
        # Log with the problematic ID
        logger.error(
            f"Error extracting details for parcel {id if 'id' in locals() else 'unknown'}: {e}"
        )
        return None


def patch_data(wait, driver, missing_id):
    """
    Perform a targeted lookup for a missing parcel, extract its details,
    then navigate back to the search form.

    Steps:
      1. Click into the Parcel ID search field.
      2. Fill in the missing parcel number.
      3. Submit the search.
      4. Call extract_patched_property_details to get the DataFrame.
      5. Click "New Search" to reset the form.

    Args:
        wait (WebDriverWait): For explicit waits on page elements.
        driver (WebDriver): Selenium WebDriver instance.
        missing_id (str): Parcel ID that needs re-scraping.

    Returns:
        pd.DataFrame or None: The patched appraisal DataFrame, or None on failure.
    """
    # Focus the parcel ID input
    safe_click(wait, XPATHS["search"]["parcel_id"])

    # Enter the missing parcel number
    fill_form_field(wait, "parcel_number", missing_id)

    # Trigger the search
    safe_click(wait, XPATHS["search"]["parcel_id_search_button"])

    # Extract the table for this single parcel
    parcel_info = extract_patched_property_details(driver, missing_id, wait)

    # Reset the UI back to the main search form
    safe_click(wait, XPATHS["property"]["new_search"])

    return parcel_info
