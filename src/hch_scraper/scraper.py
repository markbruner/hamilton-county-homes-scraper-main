import time
import random 
import pandas as pd

import hch_scraper.utils.logging_setup  
from hch_scraper.utils.logging_setup import logger
from hch_scraper.config.settings import XPATHS
from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import get_text
from hch_scraper.utils.data_extraction.table_extraction import scrape_table_by_xpath, transform_table, find_click_row
from hch_scraper.utils.io.navigation import safe_click, next_navigation

def extract_property_details(driver, wait):
    """
    Extracts detailed property information, including appraisal, tax, and transfer data.

    Parameters:
    - wait (WebDriverWait): Selenium WebDriverWait instance for handling explicit waits.

    Returns:
    - pd.DataFrame: DataFrame containing property details, or None if an error occurs.
    """
    try:
        # Retrieve and process the parcel ID
        parcel_text = get_text(driver, wait, XPATHS["property"]["parcel_id"])
        parcel_parts = parcel_text.split("\n")
        if len(parcel_parts) < 2 or not parcel_parts[1].strip():
            logger.warning(f"Unexpected format for parcel_id: {parcel_text}")
            return None
        parcel_id = parcel_parts[1].strip()

        # Scrape and transform the appraisal table
        appraisal_table = scrape_table_by_xpath(wait, XPATHS["view"]["appraisal_information"])

        if appraisal_table is None or appraisal_table.empty:
            logger.warning(f"Appraisal table is empty for parcel {parcel_id}.")
            return None
        appraisal_table = transform_table(appraisal_table)
        # Drop unwanted columns
        columns_to_drop = ["Year Built", "Deed Number", "# of Parcels Sold"]
        appraisal_table = appraisal_table.drop(
            [col for col in columns_to_drop if col in appraisal_table.columns], axis=1
        )

        # Rename columns
        appraisal_table.rename(
            columns={
                "# Bedrooms": "Bedrooms",
                "# Full Bathrooms": "Full Baths",
                "# Half Bathrooms": "Half Baths"
            }, inplace=True
        )

        # Add additional property details
        appraisal_table["parcel_id"] = parcel_id
        appraisal_table["school_district"] = get_text(driver, wait, XPATHS["property"]["school_district"])
        appraisal_table["owner_address"] = get_text(driver, wait, XPATHS["property"]["owner"])

        return appraisal_table

    except Exception as e:
        logger.error(f"Error extracting details for parcel {parcel_id if 'parcel_id' in locals() else 'unknown'}: {e}")
        return None

    
def scrape_results_page(wait):
    """Scrapes the results page for the main table."""
    try:
        table = scrape_table_by_xpath(wait, XPATHS["results"]["results_table"])
        return table
    except Exception as e:
        logger.error(f"Error scraping results page: {e}")
        return pd.DataFrame()

def scrape_summary_pages(driver, wait):
    """
    Scrapes paginated search results (summary tables) and returns a list of DataFrames.
    """
    all_data = []
    try:
        num_pages = pd.to_numeric(get_text(driver, wait, XPATHS["results"]["number_pages"]))
    except Exception as e:
        logger.warning(f"Could not determine number of pages. Defaulting to 1. Error: {e}")
        num_pages = 1

    for i in range(num_pages):
        logger.info(f"Scraping summary page {i+1} of {num_pages}...")
        table = scrape_table_by_xpath(wait, XPATHS["results"]["results_table"])

        if table is not None and not table.empty:
            all_data.append(table)
        else:
            logger.warning(f"No data found on page {i+1}.")
            break

        if not next_navigation(driver, wait, XPATHS["results"]["next_page_button"]):
            break

    return all_data

def scrape_detail_pages(driver, wait, num_properties=10):
    """
    Scrapes detailed property pages. Starts from the first property result and pages through.
    """
    appraisal_data = []

    try:
        safe_click(wait, XPATHS["results"]["first_results_table_page"])
        find_click_row(driver, wait, XPATHS["results"]["first_row_results_table"])
    except Exception as e:
        logger.warning(f"Could not start detail scrape: {e}")
        return appraisal_data

    for i in range(num_properties):
        logger.info(f"Scraping property detail {i+1} of {num_properties}...")
        table = extract_property_details(driver, wait)
        if table is not None:
            appraisal_data.append(table)
        else:
            logger.info("No property details found.")

        time.sleep(random.uniform(5, 8))

        if not next_navigation(driver, wait, XPATHS["property"]["next_property"]):
            break

    return appraisal_data

def scrape_data(driver, wait, num_properties_to_scrape):
    summary_data = scrape_summary_pages(driver, wait)
    detail_data = scrape_detail_pages(driver, wait, num_properties_to_scrape)
    return {
        "summary": summary_data,
        "details": detail_data
    }

