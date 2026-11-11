"""
Main scraping pipeline for Hamilton County Auditor data.

This script allows a user to scrape parcel data from the Hamilton County Auditor's website
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

import json
import os
import pandas as pd
from datetime import datetime, date, timedelta
from typing import List, Tuple
from dataclasses import dataclass, asdict
from dotenv import load_dotenv
import numpy as np
from supabase import create_client
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
from hch_scraper.io.ingestion import prepare_sales_records, upsert_sales_raw
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hamilton County sales scraper")

    parser.add_argument(
        "--min_days_ago",
        type=int,
        help="Most recent day to scrape (e.g. 1 = yesterday)",
    )

    parser.add_argument(
        "--max_days_ago",
        type=int,
        help="Oldest day to scrape (e.g. 3 = three days ago)",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Prepare payloads without contacting Supabase"
    )
    parser.add_argument("--start-date", type=date.fromisoformat, help="First date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=date.fromisoformat, help="Last date (YYYY-MM-DD)")
    return parser.parse_args(argv)


def resolve_dates(args: argparse.Namespace, today: date) -> Dates:
    start = getattr(args, "start_date", None)
    end = getattr(args, "end_date", None)
    max_backfill_days = 730
    if start is not None or end is not None:
        if start is None or end is None:
            raise ValueError("--start-date and --end-date are required together.")
        if args.min_days_ago is not None or args.max_days_ago is not None:
            raise ValueError("Use either fixed dates or days-ago arguments.")
        if not today - timedelta(days=max_backfill_days) <= start <= end < today:
            raise ValueError("Fixed dates must be ordered and within the previous 730 days.")
        return Dates(start, end)

    if args.min_days_ago is None or args.max_days_ago is None:
        raise ValueError("--min_days_ago and --max_days_ago are required together.")
    if args.min_days_ago >= args.max_days_ago:
        raise ValueError(
            f"min_days_ago ({args.min_days_ago}) must be < max_days_ago ({args.max_days_ago})"
        )

    if args.min_days_ago < 0 or args.max_days_ago < 0:
        raise ValueError("min_days_ago and max_days_ago must be >= 0")

    if args.max_days_ago > max_backfill_days:
        raise ValueError(f"max_days_ago cannot exceed {max_backfill_days}")

    return Dates(
        today - timedelta(days=args.max_days_ago),
        today - timedelta(days=args.min_days_ago),
    )


def run_scraper_for_dates(
    dates: Dates, robots_txt_allowed: bool, *, dry_run: bool = False
) -> None:
    """Process the requested inclusive date range."""
    formatted_start = _format_date(dates.start_date)
    formatted_end = _format_date(dates.end_date)
    ranges = _initialize_ranges(formatted_start, formatted_end)

    _scrape_all_dates(ranges, robots_txt_allowed, dry_run=dry_run)


def _get_required_env(keys: List[str]) -> dict:
    missing = [key for key in keys if not os.getenv(key)]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    return {key: os.getenv(key) for key in keys}


def _scrape_all_dates(
    ranges: List[Tuple[str, str]], robots_txt_allowed: bool, *, dry_run: bool = False
) -> None:
    """Scrape and prepare each date range, then optionally send it to Supabase."""
    if not robots_txt_allowed:
        raise PermissionError("Sales scraping requires a successful robots.txt check.")

    supabase = None
    if not dry_run:
        env = _get_required_env(["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"])
        supabase = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    while ranges[:]:
        for start, end in ranges[:]:
            logger.info(f"Scraping from {start} to {end}")
            all_data, updated_ranges, _, modified = main(
                robots_txt_allowed, ScrapeRequest(start, end, ranges)
            )
            ranges = updated_ranges
            
            if modified:
                break

            if all_data.empty:
                logger.info("No sales in this date range.")
                continue
            
            all_data, _addr_issues = _enrich_addresses(all_data)
            
            if "transfer_date" in all_data.columns:
                all_data["transfer_date"] = pd.to_datetime(
                    all_data["transfer_date"], errors="coerce"
                ).dt.date.astype("string")

            # Convert everything to object and replace non-finite values with None
            all_data = all_data.astype(object)
            all_data = all_data.replace({np.nan: None, np.inf: None, -np.inf: None})
            all_data.columns = all_data.columns.str.lower()
            all_data.columns = all_data.columns.str.replace(" ", "_")
            if dry_run:
                records = prepare_sales_records(all_data)
                json.dumps(records, allow_nan=False)
                logger.info(
                    "Dry run prepared %d sales records for %s to %s.",
                    len(records), start, end,
                )
                continue

            count = upsert_sales_raw(df=all_data, supabase=supabase)
            logger.info("Completed %d Supabase upsert calls for %s to %s.", count, start, end)


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


def run_scraper_pipeline(args: argparse.Namespace | None = None):
    """Run the scheduled sales pipeline for the requested days-ago window."""
    tz = zoneinfo.ZoneInfo("America/New_York")
    args = args or parse_args()
    dates = resolve_dates(args, datetime.now(tz).date())
    dry_run = getattr(args, "dry_run", False)
    if not dry_run:
        load_dotenv()

    logger.info("Sales date range: %s to %s.", dates.start_date, dates.end_date)
    if not check_allowed_webscraping():
        raise PermissionError("The auditor's robots.txt disallows sales scraping.")
    run_scraper_for_dates(dates, robots_txt_allowed=True, dry_run=dry_run)


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
    while current_start <= end_dt:
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

    if not robots_txt_allowed:
        raise PermissionError("Sales scraping requires a successful robots.txt check.")

    driver, wait = init_driver(URLS["sales"])
    try:
        initialize_search(wait, request.start, request.end)
        check = check_reset_needed(
            driver, wait, request.start, request.end, request.ranges
        )
        if check.reset_needed:
            logger.info("Reset needed, closing WebDriver.")
            return pd.DataFrame(), check.dates, driver, check.modified

        data = get_csv_data(wait, expected_rows=check.total_entries)
            
        logger.info(
            f"Completed scraping for {request.start} to {request.end}: {data.shape[0]} rows."
        )
        check.dates.pop(0)
        return data, check.dates, driver, check.modified

    finally:
        safe_quit(driver)


if __name__ == "__main__":
    run_scraper_pipeline()
