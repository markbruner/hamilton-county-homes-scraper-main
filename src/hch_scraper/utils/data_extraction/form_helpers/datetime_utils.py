import re
import time
import pandas as pd
from datetime import datetime, date
from typing import List, Tuple, Any, Union, Optional
from dataclasses import dataclass

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from hch_scraper.utils.logging_setup import logger
from hch_scraper.config.settings import XPATHS


@dataclass
class ModifiedDates:
    updated_dates: List[Tuple[datetime, datetime]]
    modified: bool


@dataclass
class CheckReset:
    reset_needed: bool
    modified: bool
    dates: List[Tuple[datetime, datetime]]
    total_entries: Optional[int]


def update_date_range_and_append(
    dates: List[Tuple[datetime, datetime]],
    old_date: datetime,
    new_date: datetime,
    additional_slice: Tuple[datetime, datetime],
) -> ModifiedDates:
    """
    Replaces a specific end date in a date range with a new date and adds a new time slice immediately after it.

    Args:
        dates (List[Tuple[datetime, datetime]]): A list of date ranges as (start, end) tuples.
        old_date (datetime): The end date to replace in one of the tuples.
        new_date (datetime): The new end date to use as a replacement.
        additional_slice (Tuple[datetime, datetime]): A new date range to insert after the modified one.

    Returns:
        ModifiedDates: A dataclass containing the updated list of date ranges and a boolean indicating whether a change was made.

    Raises:
        ValueError: If `dates` is not a list of (start, end) tuples.
        ValueError: If `additional_slice` is not a (start, end) tuple.
    """
    # Validate inputs
    if not isinstance(dates, list) or not all(
        isinstance(d, tuple) and len(d) == 2 for d in dates
    ):
        logger.error(
            f"Dates must be a list of tuples with start and end dates. The dates in the list are: {dates}"
        )
        raise ValueError("Dates must be a list of tuples with start and end dates.")
    if not isinstance(additional_slice, tuple) or len(additional_slice) != 2:
        logger.error("Additional slice must be a tuple with two elements (start, end).")
        raise ValueError("Invalid additional slice format")

    old_date = _ensure_datetime(old_date, "old date")
    new_date = _ensure_datetime(new_date, "new date")

    updated_dates = dates.copy()
    modified = False

    # Iterate through the date ranges to find and replace old_date
    for i, (start, end) in enumerate(updated_dates):
        start = _ensure_datetime(start, "start date")
        end = _ensure_datetime(end, "end date")

        if end == old_date:
            # Replace the end date with the new date
            start = _format_date_string(start)
            new_date = _format_date_string(new_date)
            updated_dates[i] = (start, new_date)
            # Insert the additional time slice
            additional_slice_str = (
                additional_slice[0].strftime("%m/%d/%Y"),
                additional_slice[1].strftime("%m/%d/%Y"),
            )
            updated_dates.insert(i + 1, additional_slice_str)

            modified = True
            logger.info(
                f"Replaced {old_date} with {new_date} and added new slice {additional_slice_str}."
            )
            break

    if not modified:
        logger.warning(
            f"Old date {old_date} not found in any date range. No modifications made."
        )

    return ModifiedDates(updated_dates=updated_dates, modified=modified)


def _format_date_string(dt: Union[date, datetime]) -> str:
    if not isinstance(dt, (datetime, date)):
        raise ValueError(f"Expected a datetime or date object, got {type(dt).__name__}")
    return dt.strftime("%m/%d/%Y")


def check_reset_needed(
    driver: object,
    wait: object,
    start: str,
    end: str,
    dates: List[Tuple[datetime, datetime]],
    max_attempts: int = 3,
    retry_delay_seconds: float = 1.5,
) -> CheckReset:
    """
    Checks if the search needs to be reset due to 1000 entries and updates the time slice.

    Args:
    - driver: Selenium WebDriver instance.
    - wait: WebDriverWait instance for handling explicit waits.
    - start (str): Start date of the current search range.
    - end (str): End date of the current search range.
    - dates (list): List of date ranges to modify if resetting is needed.

    Returns:
    - CheckReset: A dataclass containing if a reset is needed, if the list of dates as tuples were modified, the range of date tuples, and the number of search results.

    Raises:
    - ValueError: If 'total_entries' failed to be extracted.
    """
    start_dt = _ensure_datetime(start, "start date")
    end_dt = _ensure_datetime(end, "end date")

    total_entries = None
    for attempt in range(1, max_attempts + 1):
        try:
            total_entries = _extract_total_entries_once(driver, wait)
        except Exception as e:
            raise ValueError(f"Failed to extract number of entries: {e}")

        if total_entries is not None:
            break

        if attempt < max_attempts:
            logger.info(
                "Could not determine result count for %s to %s on attempt %s/%s. Retrying in %.1fs.",
                start,
                end,
                attempt,
                max_attempts,
                retry_delay_seconds,
            )
            time.sleep(retry_delay_seconds)

    if total_entries is None:
        logger.warning(
            "Could not determine total search result entries for %s to %s. "
            "Continuing without date-range split for this iteration.",
            start,
            end,
        )
        return CheckReset(
            reset_needed=False,
            modified=False,
            dates=dates,
            total_entries=None,
        )

    if total_entries >= 1000:
        logger.info(
            f"Entries = {total_entries} for {start} to {end}. Splitting dates further since the entries are greater than or equal to the threshold of 1000."
        )

        # Calculating the midpoint of the start and end date
        midpoint = start_dt + (end_dt - start_dt) / 2

        # Creating the new time slice
        new_slice = (midpoint, end_dt)

        # Updating the list of dates
        updated_dates = update_date_range_and_append(dates, end_dt, midpoint, new_slice)

        return CheckReset(
            reset_needed=True,
            modified=updated_dates.modified,
            dates=updated_dates.updated_dates,
            total_entries=total_entries,
        )

    if total_entries < 1:
        logger.warning(
            f"Search parameters between {start_dt} and {end_dt} yielded no results. Moving to next date range."
        )
        updated_dates = dates.copy()
        current = (_format_date_string(start_dt), _format_date_string(end_dt))
        if updated_dates and updated_dates[0] == current:
            updated_dates.pop(0)
        return CheckReset(
            reset_needed=True,
            modified=False,
            dates=updated_dates,
            total_entries=total_entries,
        )

    return CheckReset(
        reset_needed=False, modified=False, dates=dates, total_entries=total_entries
    )


def _ensure_datetime(value: Any, description: str = "date") -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return pd.to_datetime(value)
    except Exception as e:
        logger.error(f"Invalid {description}: {value}. Error: {e}")
        raise ValueError(f"Invalid {description}: {value}")


def _get_dt_record_count(driver):
    """
    Return the total row count reported by DataTables, or None if
    jQuery/DataTables isn’t present yet.
    """
    try:
        return driver.execute_script(
            """
            const $ = window.jQuery;
            if (!$ || !$.fn.dataTable) return null;

            // Adjust '#resultsTable' if your table uses a different id
            const table = $('#resultsTable').DataTable();
            return table ? table.page.info().recordsDisplay : null;
        """
        )
    except Exception:
        return None


def _extract_total_entries_once(driver, wait) -> Optional[int]:
    # A) ask DataTables directly
    total_entries = _get_dt_record_count(driver)
    if total_entries is not None:
        return total_entries

    # B) fall back to parsing the status string
    try:
        elem = wait.until(
            EC.presence_of_element_located((By.XPATH, XPATHS["results"]["search_results_number"]))
        )
        raw_text = elem.text
        m = re.search(r"of\s+([\d,]+)\s+entries", raw_text, re.I)
        if m:
            return int(m.group(1).replace(",", ""))
        nums = re.findall(r"\d+", raw_text)
        return int(max(nums)) if nums else None
    except Exception:
        return None
