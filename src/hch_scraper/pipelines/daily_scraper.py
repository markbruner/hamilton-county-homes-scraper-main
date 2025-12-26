"""
Main scraping pipeline for Hamilton County Auditor data.

This script allows a user to scrape parcel data from the Hamilton County Auditor’s website
over a specified date range. It handles date input, WebDriver setup, site navigation, data extraction,
and CSV output, including logic to manage pagination and robot.txt checks.

Modules:
    - logging_setup: Handles logging configuration.
    - settings: Contains constants such as URLs.
    - driver_setup: Initializes the Selenium WebDriver.
    - scraper: Retrieves tabular data from the results.
    - form_helpers: Handles web form interaction, formatting, and retry logic.

To run:
    $ python -m src.hch_scraper.main
"""

import time
import os
import pandas as pd
from datetime import datetime, date, timedelta
from typing import List, Tuple
from dataclasses import dataclass, asdict
from dotenv import load_dotenv
import numpy as np
from supabase import create_client, Client
import zoneinfo
import argparse

from hch_scraper.utils.logging_setup import logger
from hch_scraper.config.settings import URLS
from hch_scraper.drivers.webdrivers import init_driver
from hch_scraper.io.downloads import get_csv_data

from hch_scraper.io.navigation import initialize_search, check_allowed_webscraping
from hch_scraper.utils.data_extraction.address_cleaners import (
    normalize_address_parts,
    tag_address,
)
from hch_scraper.io.ingestion import upsert_sales_raw
from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import safe_quit

from hch_scraper.utils.data_extraction.form_helpers.datetime_utils import (
    check_reset_needed,
)


@dataclass
class Dates:
    """
    Represents the user input date range.

    Args:
        start_date (date): The user-specified start date.
        end_date (date): The user-specified end date.
    """

    start_date: date
    end_date: date


@dataclass
class ScrapeRequest:
    """
    Represents a single scrape request input.

    Args:
        start (str): Start date in MM/DD/YYYY format.
        end (str): End date in MM/DD/YYYY format.
        ranges (List[Tuple[str, str]]): The list of date ranges to scrape.
    """

    start: str
    end: str
    ranges: List[Tuple[str, str]]


@dataclass
class ScraperResult:
    """
    Represents the output from scraping a single year.

    Args:
        data (pd.DataFrame): Combined scraped data.
        remaining_ranges (List[Tuple[str, str]]): Remaining ranges after scraping.
        final_start (str): Final formatted start date.
        final_end (str): Final formatted end date.
        year (int): The year the data corresponds to.
    """

    data: pd.DataFrame
    remaining_ranges: List[Tuple[str, str]]
    final_start: str
    final_end: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hamilton County sales scraper")

    parser.add_argument(
        "--min_days_ago",
        type=int,
        required=True,
        help="Most recent day to scrape (e.g. 1 = yesterday)",
    )

    parser.add_argument(
        "--max_days_ago",
        type=int,
        required=True,
        help="Oldest day to scrape (e.g. 3 = three days ago)",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.min_days_ago >= args.max_days_ago:
        raise ValueError(
            f"min_days_ago ({args.min_days_ago}) must be < max_days_ago ({args.max_days_ago})"
        )

    if args.min_days_ago < 0 or args.max_days_ago < 0:
        raise ValueError("min_days_ago and max_days_ago must be >= 0")

    MAX_BACKFILL_DAYS = 730  # 2 years

    if args.max_days_ago > MAX_BACKFILL_DAYS:
        raise ValueError(f"max_days_ago cannot exceed {MAX_BACKFILL_DAYS}")


def run_scraper_for_dates(dates: datetime, robots_txt_allowed: bool) -> ScraperResult:
    """
    Runs the scraper for a single year within the specified date range.

    Args:
        dates (Dates): Object containing start date, end date, and years to loop through.
        robots_txt_allowed (bool): Whether scraping is permitted by robots.txt.

    Returns:
        ScraperResult: Structured result containing scraped data and metadata.
    """
    formatted_start = _format_date(dates.start_date)
    formatted_end = _format_date(dates.end_date)
    ranges = _initialize_ranges(formatted_start, formatted_end)

    _scrape_all_dates(ranges, robots_txt_allowed, formatted_start, formatted_end)


def _scrape_all_dates(
    ranges: List[Tuple[str, str]], robots_txt_allowed: bool, search_start, search_end
) -> pd.DataFrame:
    """
    Loops through ranges and gathers all data into a single DataFrame.

    Args:
        ranges (List[Tuple[str, str]]): The list of start-end date tuples to scrape.
        robots_txt_allowed (bool): Flag indicating if scraping is allowed.

    Returns:
        pd.DataFrame: Combined DataFrame of all scraped data.
    """
    SUPABASE_URL = os.environ["SUPABASE_URL"]
    SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    while ranges[:]:
        for start, end in ranges[:]:
            logger.info(f"Scraping from {start} to {end}")
            all_data = main(robots_txt_allowed, ScrapeRequest(start, end, ranges))
            if all_data.empty:
                logger.info("No new records; exiting cleanly.")
                raise SystemExit(0)
            
            all_data, addr_issues = _enrich_addresses(all_data)

            if "transfer_date" in all_data.columns:
                all_data["transfer_date"] = pd.to_datetime(
                    all_data["transfer_date"], errors="coerce"
                ).dt.date.astype("string")

            # Convert everything to object and replace non-finite values with None
            all_data = all_data.astype(object)
            all_data = all_data.replace({np.nan: None, np.inf: None, -np.inf: None})
            all_data.columns = all_data.columns.str.lower()
            all_data.columns = all_data.columns.str.replace(" ", "_")
            upsert_sales_raw(
                df=all_data,
                supabase=supabase,
                schema_name="public",
                table_name="sales_hamilton",
            )


def _enrich_addresses(df: pd.DataFrame) -> pd.DataFrame:
    parsed = []
    issues = []
    df.columns = df.columns.str.lower()
    df.columns = df.columns.str.replace(" ", "_")
    for _, row in df.iterrows():
        parts, errs = tag_address(row, addr_col="address", parcel_col="parcel_number")
        issues.extend(errs)
        if parts:
            parsed.append(asdict(normalize_address_parts(parts)))
        else:
            parsed.append({})
    enriched = pd.DataFrame(parsed)
    return pd.concat([df.reset_index(drop=True), enriched], axis=1), issues


def run_scraper_pipeline():
    """
    Executes the full scraping pipeline.

    Prompts the user for a date range, checks robots.txt permission,
    and runs the scraper for each date in the specified range.
    """
    tz = zoneinfo.ZoneInfo("America/New_York")
    args = parse_args()
    validate_args(args)

    start_date = (datetime.now(tz) - timedelta(days=args.max_days_ago)).date()
    end_date = (datetime.now(tz) - timedelta(days=args.min_days_ago)).date()
    dates = Dates(start_date, end_date)
    logger.info(f"the date range is for start is {start_date} and end is {end_date}")
    # driver, wait = init_driver(URLS["base"])

    # try:
    #     robots_txt_allowed = check_allowed_webscraping(driver)
    # finally:
    #     safe_quit(driver)
    robots_txt_allowed = True

    run_scraper_for_dates(dates, robots_txt_allowed)


def _format_date(dt: date) -> str:
    """Formats a date object to MM/DD/YYYY string."""
    return dt.strftime("%m/%d/%Y")


def _initialize_ranges(
    start: str,
    end: str,
    fmt: str = "%m/%d/%Y",  # <-- MM/DD/YYYY by default
    window_days: int = 7,
) -> List[Tuple[str, str]]:
    """
    Break the overall [start, end] span into consecutive `window_days`-long
    intervals (inclusive) and return them as (start, end) string tuples.

    Example
    -------
    >>> _initialize_ranges("06/01/2025", "06/12/2025")
    [('06/01/2025', '06/04/2025'),
     ('06/05/2025', '06/08/2025'),
     ('06/09/2025', '06/12/2025')]
    """
    start_dt = datetime.strptime(start, fmt).date()
    end_dt = datetime.strptime(end, fmt).date()
    if start_dt > end_dt:
        raise ValueError("`start` must be on or before `end`.")

    step = timedelta(days=window_days)
    ranges = []

    current_start = start_dt
    while current_start < end_dt:
        current_end = min(current_start + step, end_dt)
        ranges.append((current_start.strftime(fmt), current_end.strftime(fmt)))
        current_start += step + timedelta(days=1)

    return ranges


def main(
    robots_txt_allowed: bool, request: ScrapeRequest
) -> Tuple[pd.DataFrame, List[Tuple[str, str]], object, bool]:
    """
    Initializes the web driver and performs scraping for a specific date range.

    Args:
        robots_txt_allowed (bool): Flag indicating if scraping is allowed.
        request (ScrapeRequest): Structured input with start, end, and date ranges.

    Returns:
        Tuple containing:
            - pd.DataFrame: The scraped data.
            - List[Tuple[str, str]]: Updated list of date ranges (if reset occurred).
            - object: Selenium WebDriver instance.
            - bool: Whether reset was triggered (i.e., result count exceeded max).
    """

    BASE_URL = URLS["base"]
    driver, wait = init_driver(BASE_URL)

    if not robots_txt_allowed:
        robots_txt_allowed = check_allowed_webscraping(driver)

    try:
        initialize_search(wait, request.start, request.end)
        time.sleep(2)
        check = check_reset_needed(
            driver, wait, request.start, request.end, request.ranges
        )
        if check.reset_needed:
            logger.info("Reset needed, closing WebDriver.")
            return pd.DataFrame(), check.dates, driver, check.modified

        data = get_csv_data(wait)
        if data.empty and len(request.ranges) == 1:
            logger.info(f"No data for {request.start}–{request.end}.")
            return pd.DataFrame()
            
        logger.info(
            f"Completed scraping for {request.start}–{request.end}: {data.shape[0]} rows."
        )
        check.dates.pop(0)
        return data

    finally:
        safe_quit(driver)


if __name__ == "__main__":
    load_dotenv()
    run_scraper_pipeline()
