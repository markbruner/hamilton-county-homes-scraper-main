import re
import pandas as pd
from datetime import timedelta, datetime

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

import hch_scraper.utils.logging_setup 
from hch_scraper.utils.logging_setup import logger
from hch_scraper.config.settings import XPATHS
from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import get_text, safe_quit

# datetime_utils.py  (new code – place after imports)
def _get_dt_record_count(driver):
    """
    Return the total row count reported by DataTables, or None if
    jQuery/DataTables isn’t present yet.
    """
    try:
        return driver.execute_script("""
            const $ = window.jQuery;
            if (!$ || !$.fn.dataTable) return null;

            // Adjust '#resultsTable' if your table uses a different id
            const table = $('#resultsTable').DataTable();
            return table ? table.page.info().recordsDisplay : null;
        """)
    except Exception:
        return None


def safe_to_datetime(date, description="date"):
    try:
        return pd.to_datetime(date)
    except Exception as e:
        logger.error(f"Invalid {description}: {date}. Error: {e}")
        raise

def str_format_date(date):
    """
    Converts a datetime object into a string in the format MM/DD/YYYY.

    Parameters:
    - date (datetime): The datetime object to format.

    Returns:
    - str: The formatted date string.
    
    Raises:
    - ValueError: If the input is not a valid datetime object.
    """
    if not isinstance(date, datetime):
        raise ValueError(f"Input must be a datetime object, but got {type(date).__name__}.")
    
    return f"{date:%m/%d/%Y}"

def split_replace_add_time_slice(dates, old_date, new_date, additional_slice):
    """
    Replaces a specific end date in a date range and adds a new time slice after it.

    Parameters:
    - dates (list of tuples): List of date ranges as (start, end) tuples.
    - old_date (str): The end date to replace.
    - new_date (str): The new end date to replace `old_date` with.
    - additional_slice (tuple): A new time slice to add after the modified date range.

    Returns:
    - list of tuples: The modified list of date ranges.
    """
    # Validate inputs
    if not isinstance(dates, list) or not all(isinstance(d, tuple) and len(d) == 2 for d in dates):
        logger.error(f"Dates must be a list of tuples with start and end dates. The dates in the list are: {dates}")
        raise ValueError("Invalid dates format")
    if not isinstance(additional_slice, tuple) or len(additional_slice) != 2:
        logger.error("Additional slice must be a tuple with two elements (start, end).")
        raise ValueError("Invalid additional slice format")
    
    old_date = safe_to_datetime(old_date,"old date")
    new_date = safe_to_datetime(new_date, "new date")

    updated_dates = dates.copy()
    modified = False

    # Iterate through the date ranges to find and replace old_date
    for i, (start, end) in enumerate(updated_dates):
        start = safe_to_datetime(start, "start date")
        end = safe_to_datetime(end, "end date")

        if end == old_date:
            # Replace the end date with the new date
            start = str_format_date(start)
            new_date = str_format_date(new_date)
            updated_dates[i] = (start, new_date)
            # Insert the additional time slice
            updated_dates.insert(i + 1, additional_slice)
            modified = True
            logger.info(f"Replaced {old_date} with {new_date} and added new slice {additional_slice}.")
            break

    if not modified:
        logger.warning(f"Old date {old_date} not found in any date range. No modifications made.")

    return updated_dates, modified


def check_reset_needed(driver, wait, start, end, dates):
    """
    Checks if the search needs to be reset due to 1000 entries and updates the time slice.

    Parameters:
    - driver: Selenium WebDriver instance.
    - wait: WebDriverWait instance for handling explicit waits.
    - start (str): Start date of the current search range.
    - end (str): End date of the current search range.
    - dates (list): List of date ranges to modify if resetting is needed.

    Returns:
    - reset_needed (bool): Whether the search was reset.
    - updated_dates (list): Updated list of date ranges.
    - total_entries (int): Number of entries in the current search.
    """
    start_dt = safe_to_datetime(start, "start date")
    end_dt = safe_to_datetime(end, "end date")

    try:
        # A) ask DataTables directly
        total_entries = _get_dt_record_count(driver)

        # B) fall back to parsing the status string
        if total_entries is None:
            try:
                elem = wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, XPATHS["results"]["search_results_number"])
                    )
                )
                raw_text = elem.text                      # "Showing 1 to 10 of 121 entries"
                # robust regex: look for "of <number> entries"
                m = re.search(r"of\s+([\d,]+)\s+entries", raw_text, re.I)
                if m:
                    total_entries = int(m.group(1).replace(",", ""))
                else:
                    # last-ditch: take the largest number in the string
                    nums = re.findall(r"\d+", raw_text)
                    total_entries = int(max(nums)) if nums else None
            except Exception:
                total_entries = None

    except Exception as e:
        raise ValueError(f"Failed to extract number of entries: {e}")   

    if total_entries >= 1000:
        logger.info(f"Entries = {total_entries} for {start} to {end}. Splitting dates further since the entries are greater than or equal to the threshold of 1000.")

        # Calculating the midpoint of the start and end date
        midpoint = start_dt + (end_dt - start_dt) / 2
        midpoint_str = f"{midpoint:%m/%d/%Y}"

        # Creating the new time slice
        new_slice = (
            f"{midpoint + timedelta(days=1):%m/%d/%Y}"
            ,f"{end_dt:%m/%d/%Y}"
            )
        
        # Updating the list of dates        
        updated_dates, modified = split_replace_add_time_slice(
            dates, f"{end_dt:%m/%d/%Y}", midpoint_str, new_slice
            )
        return True, modified, updated_dates, total_entries
    
    if total_entries < 1:
        logger.warning(f"Search parameters between {start_dt} and {end_dt} yielded no results. Moving to next date range.")
        safe_quit(driver)
        return False, False, dates, total_entries

    return False, False, dates, total_entries
