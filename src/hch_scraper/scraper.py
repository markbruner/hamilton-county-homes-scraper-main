# hch_scraper: Detailed Documentation and Enhanced Docstrings
"""
This module contains functions to scrape property search results and detailed property data
from the Hamilton County Auditor website using Selenium and Pandas.

It supports:
- Downloading search result CSV files
- Scraping and transforming summary tables across paginated results
- Extracting detailed appraisal and property information
- Combining summary and detail data into Python data structures

Modules:
- download_search_results_csv: Trigger CSV download via Selenium
- extract_property_details: Scrape and transform detailed appraisal tables
- scrape_results_page: Extract the main results table
- scrape_summary_pages: Iterate and collect paginated summary tables
- scrape_detail_pages: Iterate and collect detailed property pages
- get_csv_data: Wait for CSV download, read, and cleanup
- scrape_data: Aggregate summary and detail scraping routines

Configuration, logging, and XPATH settings are imported from hch_scraper utilities.
"""
import glob, os, time, random, re, math
import pandas as pd
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

# Logging setup
from hch_scraper.utils.logging_setup import logger

# Application settings (XPATH definitions)
from hch_scraper.config.settings import XPATHS, data_storage

# Helpers for text extraction, table scraping, and navigation
from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import get_text
from hch_scraper.utils.data_extraction.table_extraction import (
    scrape_table_by_xpath,
    transform_table,
    find_click_row
)
from hch_scraper.utils.io.navigation import safe_click, next_navigation
from hch_scraper.utils.data_extraction.form_helpers.file_io import get_file_path


def download_search_results_csv(wait) -> None:
    """
    Clicks the CSV download link on the search results page.

    Args:
    - wait: WebDriverWait instance for Selenium explicit waits

    Side effects:
    - Initiates the browser download of a CSV file containing search results
    """
    safe_click(wait, XPATHS["results"]["download_csv"])


def extract_property_details(driver, wait) -> pd.DataFrame:
    """
    Extracts and processes detailed property information from a single property page.

    Retrieves the parcel ID, appraisal data table, and additional fields like school district.
    Transforms and cleans the appraisal table for downstream analysis.

    Args:
    - driver: Selenium WebDriver instance
    - wait: WebDriverWait instance for explicit waits

    Returns:
    - A pandas DataFrame with cleaned appraisal data and additional columns:
      ['parcel_id', 'Bedrooms', 'Full Baths', 'Half Baths', 'school_district']
    - None if any critical extraction step fails
    """
    try:
        # Fetch the raw parcel ID text and split lines
        raw_text = get_text(driver, wait, XPATHS["property"]["parcel_id"], retries=1)
        parts = raw_text.split("\n")
        # Validate that a second line exists and is non-empty
        if len(parts) < 2 or not parts[1].strip():
            logger.warning(f"Unexpected parcel_id format: {raw_text}")
            return None
        parcel_id = parts[1].strip()

        # Scrape the appraisal information table via XPath
        appraisal_table = scrape_table_by_xpath(wait, XPATHS["view"]["appraisal_information"])
        if appraisal_table is None or appraisal_table.empty:
            logger.warning(f"Empty appraisal table for parcel {parcel_id}")
            return None
        # Normalize and clean the table
        df = transform_table(appraisal_table)
        columns_to_drop = ["Year Built", "Deed Number", "# of Parcels Sold"]
        df = df.drop([c for c in columns_to_drop if c in df.columns], axis=1)
        df.rename(columns={
            "# Bedrooms": "Bedrooms",
            "# Full Bathrooms": "Full Baths",
            "# Half Bathrooms": "Half Baths"
        }, inplace=True)

        # Attach metadata columns
        df["parcel_id"] = parcel_id
        df["school_district"] = get_text(driver, wait, XPATHS["property"]["school_district"], retries=1)
        return df

    except Exception as e:
        logger.error(f"Error extracting details for {parcel_id if 'parcel_id' in locals() else 'unknown'}: {e}")
        return None


def scrape_results_page(wait) -> pd.DataFrame:
    """
    Retrieves the primary search results table from the current page.

    Args:
    - wait: WebDriverWait instance

    Returns:
    - pandas DataFrame representing the results table
    - Empty DataFrame if scraping fails
    """
    try:
        return scrape_table_by_xpath(wait, XPATHS["results"]["results_table"])
    except Exception as e:
        logger.error(f"Error scraping results page: {e}")
        return pd.DataFrame()


def scrape_summary_pages(driver, wait) -> list:
    """
    Iterates through paginated search result pages and collects summary tables.

    Determines the number of pages by querying DataTables, counting pagination links,
    or parsing status text. Defaults to 1 page if detection fails.

    Args:
    - driver: Selenium WebDriver
    - wait: WebDriverWait instance

    Returns:
    - List of DataFrames, one per page
    """
    # Determine total page count
    num_pages = (
        _dt_num_pages(driver)
        or _pagination_li_count(driver)
        or _pages_from_status_text(driver, wait)
        or 1
    )
    if num_pages == 1:
        logger.warning("Could not determine pages; defaulting to 1.")

    pages = []
    for idx in range(num_pages):
        logger.info(f"Scraping summary page {idx+1}/{num_pages}")
        table = scrape_table_by_xpath(wait, XPATHS["results"]["results_table"])
        if table is not None and not table.empty:
            pages.append(table)
        else:
            logger.warning(f"No data on page {idx+1}; aborting.")
            break
        # Navigate to next page if needed
        if idx + 1 < num_pages:
            time.sleep(random.uniform(1, 4))
            if not next_navigation(driver, wait, XPATHS["results"]["next_page_button"]):
                logger.warning("Failed to click next page; stopping.")
                break
    return pages


def _dt_num_pages(driver) -> int:
    """
    Uses DataTables JS API to retrieve total page count directly.

    Returns:
    - Integer page count, or None if unavailable
    """
    try:
        return driver.execute_script("""
            const $ = window.jQuery;
            if (!$ || !$.fn.dataTable) return null;
            const dt = $('#resultsTable').DataTable();
            return dt.page.info().pages;
        """
        )
    except Exception:
        return None


def _pagination_li_count(driver) -> int:
    """
    Counts <li> pagination buttons for Bootstrap-style pagination.

    Returns:
    - Number of page links, or None if not found
    """
    try:
        items = driver.find_elements(
            By.CSS_SELECTOR,
            "ul.pagination li.paginate_button:not(.next):not(.previous)"
        )
        return len(items) or None
    except Exception:
        return None


def _pages_from_status_text(driver, wait) -> int:
    """
    Parses status text like 'Showing 1 to 10 of 121 entries' to compute page count.

    Returns:
    - math.ceil(total_rows / rows_per_page) or None
    """
    try:
        status = wait.until(
            EC.presence_of_element_located((
                By.XPATH,
                XPATHS["results"]["search_results_number"]
            ))
        ).text
        match = re.search(r"to\s+(\d+)\s+of\s+([\d,]+)", status)
        if not match:
            return None
        per_page = int(match.group(1).replace(",", ""))
        total = int(match.group(2).replace(",", ""))
        return math.ceil(total / per_page)
    except Exception:
        return None


def scrape_detail_pages(driver, wait, num_properties: int = 10) -> list:
    """
    Navigates into each property detail page and collects appraisal DataFrames.

    Args:
    - driver: Selenium WebDriver
    - wait: WebDriverWait instance
    - num_properties: Max properties to scrape

    Returns:
    - List of pandas DataFrames for each property's appraisal data
    """
    results = []
    try:
        # Click the first result in the summary table
        safe_click(wait, XPATHS["results"]["first_results_table_page"])
        find_click_row(driver, wait, XPATHS["results"]["first_row_results_table"])
    except Exception as e:
        logger.warning(f"Failed to initialize detail scraping: {e}")
        return results

    for idx in range(num_properties):
        logger.info(f"Scraping detail {idx+1}/{num_properties}")
        df = extract_property_details(driver, wait)
        if df is not None:
            results.append(df)
        time.sleep(random.uniform(5, 8))
        # Move to next detail page
        if not next_navigation(driver, wait, XPATHS["property"]["next_property"]):
            break
    return results

def get_csv_data(wait, max_wait=30) -> pd.DataFrame:
    """
    Clicks the “Download CSV” link, waits for a non-empty CSV to appear,
    loads it into a DataFrame, then deletes *all* search_results*.csv files.

    Args
    ----
    wait : selenium.webdriver.support.ui.WebDriverWait
    max_wait : int
        Seconds to wait for a fresh CSV before giving up.

    Returns
    -------
    pd.DataFrame
    """
    download_dir = Path(data_storage["raw"]).resolve()     # adjust if different
    pattern      = download_dir / "search_results*.csv"

    # Clean slate
    _purge_existing_csvs(pattern)

    # Trigger download
    download_search_results_csv(wait)
    start = time.time()

    # Poll for a *new* CSV (incl.  “search_results(1).csv” fallback)
    csv_path = None
    while time.time() - start < max_wait:
        matches = glob.glob(str(pattern))
        if matches:
            # Pick newest and make sure it's non-empty
            newest = max(matches, key=os.path.getmtime)
            if os.path.getsize(newest) > 0:
                csv_path = newest
                # extra 1-sec sleep to ensure browser flush
                time.sleep(1)
                break
        time.sleep(0.5)

    if not csv_path:
        logger.error("CSV download timed out; no file found.")
        return pd.DataFrame()          # or raise, depending on your policy

    # Read
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        logger.error(f"Failed to read CSV {csv_path}: {e}")
        return pd.DataFrame()

    if df.empty:
        logger.warning(f"Downloaded CSV is empty: {csv_path}")

    # Clean up *all* matching CSVs
    _purge_existing_csvs(pattern)

    return df

def _purge_existing_csvs(pattern):
    # Removes any .csv files that would keep the scraper from working properly
    for f in glob.glob(str(pattern)):
        try:
            os.unlink(f)
            logger.debug(f"Removed stale file: {f}")
        except Exception as e:
            logger.warning(f"Could not delete {f}: {e}")


def scrape_data(driver, wait, num_properties_to_scrape: int) -> dict:
    """
    Orchestrates the full scraping workflow: summary + detail pages.

    Args:
    - driver: Selenium WebDriver
    - wait: WebDriverWait instance
    - num_properties_to_scrape: Number of detail pages to collect

    Returns:
    - Dictionary with keys 'summary' (list of DataFrames) and 'details' (list of DataFrames)
    """
    summary = scrape_summary_pages(driver, wait)
    details = scrape_detail_pages(driver, wait, num_properties_to_scrape)
    return {"summary": summary, "details": details}
