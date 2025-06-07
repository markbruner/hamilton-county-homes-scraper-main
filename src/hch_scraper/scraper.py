import time
import random 
import pandas as pd
import math
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

import hch_scraper.utils.logging_setup  
from hch_scraper.utils.logging_setup import logger
from hch_scraper.config.settings import XPATHS
from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import get_text
from hch_scraper.utils.data_extraction.table_extraction import scrape_table_by_xpath, transform_table, find_click_row
from hch_scraper.utils.io.navigation import safe_click, next_navigation

def _dt_num_pages(driver):
    """
    Ask DataTables directly.  Returns an int or None.
    """
    try:
        return driver.execute_script("""
            const $ = window.jQuery;
            if (!$ || !$.fn.dataTable) return null;
            const dt = $('#resultsTable').DataTable();        // adjust selector!
            return dt ? dt.page.info().pages : null;
        """)
    except Exception:
        return None


def _pagination_li_count(driver):
    """
    Count <li class="paginate_button"> elements in the pagination bar.
    Works when Bootstrap pagination is used.
    """
    try:
        lis = driver.find_elements(By.CSS_SELECTOR,
                                   "ul.pagination li.paginate_button:not(.next):not(.previous)")
        return len(lis) or None
    except Exception:
        return None


def _pages_from_status_text(driver, wait):
    """
    Parse something like 'Showing 1 to 10 of 121 entries' → ceil(121/10) = 13.
    """
    try:
        text = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, XPATHS["results"]["search_results_number"])
            )
        ).text
        # Pull the two numbers we need: '10' (rows per page) and '121' (total)
        m = re.search(r"to\s+(\d+)\s+of\s+([\d,]+)", text)
        if not m:
            return None
        rows_per_page = int(m.group(1).replace(",", ""))
        total_rows    = int(m.group(2).replace(",", ""))
        return math.ceil(total_rows / rows_per_page)
    except Exception:
        return None

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
        parcel_text = get_text(driver, wait, XPATHS["property"]["parcel_id"],retries=1)
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
        appraisal_table["school_district"] = get_text(driver, wait, XPATHS["property"]["school_district"],retries=1)

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
    Scrapes paginated search-results tables and returns a list of DataFrames.
    """
    # 1 Work out how many pages really exist
    num_pages = (_dt_num_pages(driver)
                 or _pagination_li_count(driver)
                 or _pages_from_status_text(driver, wait)
                 or 1)

    if num_pages == 1:
        logger.warning("Could not determine number of pages, defaulting to 1.")

    all_data = []
    for i in range(num_pages):
        logger.info(f"Scraping summary page {i + 1} of {num_pages} …")

        table = scrape_table_by_xpath(wait, XPATHS["results"]["results_table"])
        if table is not None and not table.empty:
            all_data.append(table)
        else:
            logger.warning(f"No data found on page {i + 1}; stopping early.")
            break

        # advance to next page unless we're on the last one
        if i + 1 < num_pages:
            if not next_navigation(driver, wait, XPATHS["results"]["next_page_button"]):
                logger.warning("Next-page click failed early.  Stopping.")
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