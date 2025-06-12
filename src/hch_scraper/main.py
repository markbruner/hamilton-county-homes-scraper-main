import subprocess
import sys
from datetime import datetime

import time
import pandas as pd

import hch_scraper.utils.logging_setup  
from hch_scraper.utils.logging_setup import logger
from hch_scraper.config.settings import URLS
from hch_scraper.driver_setup import init_driver
from hch_scraper.scraper import scrape_data, get_csv_data

from hch_scraper.utils.io.navigation import initialize_search, check_allowed_webscraping

from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import safe_quit
from hch_scraper.utils.data_extraction.form_helpers.data_formatting import final_csv_conversion
from hch_scraper.utils.data_extraction.form_helpers.datetime_utils import check_reset_needed

def _ask_date(prompt: str) -> str:
    """
    Prompt the user until they enter a date in MM/DD/YYYY format.
    Returns the valid date string.
    """
    while True:
        s = input(f"{prompt} (MM/DD/YYYY): ")
        try:
            # this will raise ValueError if the format is wrong
            dt = datetime.strptime(s, "%m/%d/%Y")
            return dt # or return dt if you want a datetime object
        except ValueError:
            print("  ↳ Invalid date format. Please use MM/DD/YYYY.")

def get_user_input():
    # ask the dates first
    start_date = _ask_date("Enter the start date")
    end_date   = _ask_date("Enter the end date")
    
    start_year = start_date.year
    end_year = end_date.year

    years = range(start_year, end_year + 1)
    return start_date, end_date, years

# def run_scraper_for_year(year, allowed, query_ids, query_values):
def run_scraper_for_year(start_date, end_date, year, allowed):
    start_date = f"{start_date}"
    end_date = f"{end_date}"
    dates = [(start_date, end_date)]

    while dates:
        for start_date, end_date in dates[:]:
            logger.info(f"Starting scraping process for start date, {start_date}, and end date, {end_date}")

            all_data_df = pd.DataFrame()
            # appraisal_data_df = pd.DataFrame()

            # all_data, appraisal_data, dates, driver, modified = main(
            all_data, dates, driver, modified = main(
                allowed=allowed,
                start=start_date,
                end=end_date,
                # ids=query_ids,
                # values=query_values,
                dates=dates
            )

            if modified:
                break

            all_data_df = pd.concat([all_data_df, all_data], axis=0, ignore_index=True)
            # appraisal_data_df = pd.concat([appraisal_data_df, appraisal_data], axis=0, ignore_index=True)
            # final_csv_conversion(
            #     all_data_df, appraisal_data_df, dates, start_date, end_date, year
            #     )
            final_csv_conversion(
                all_data_df, dates, start_date, end_date, year
                )

# def main(allowed, start, end, dates, ids, values): 
def main(allowed, start, end, dates): 
    BASE_URL = URLS['base']
    driver, wait = init_driver(BASE_URL)

    # Ensuring that webscraping on the website is allowed.
    if not allowed:
        allowed = check_allowed_webscraping(driver)

    try:
        # initialize_search(wait, start, end, ids, values)
        initialize_search(wait, start, end)
        time.sleep(2)
        reset_needed, modified, dates, num_properties_to_scrape  = check_reset_needed(driver, wait, start, end, dates)

        if reset_needed:
            logger.info("Reset needed, closing WebDriver.")
            # return pd.DataFrame(), pd.DataFrame(), dates, driver, modified
            return pd.DataFrame(), dates, driver, modified
        
        # Scrape data
        # data = scrape_data(driver, wait, num_properties_to_scrape )  
        data = get_csv_data(wait)
        all_data = data
        # appraisal_data = data['details']

        assert all_data, "No all_data returned!"
        # assert appraisal_data, "No appraisal_data returned!"            
        # Consolidate data
        all_data_df = pd.concat(all_data).reset_index(drop=True)
        all_data_df.columns = ['Parcel Number', 'Address', 'BBB', 'FinSqFt', 'Use', 'Year Built','Transfer Date', 'Amount']
        # appraisal_data_df = pd.concat(appraisal_data).reset_index(drop=True)

        logger.info(
            f"Completed scraping for {start}–{end}: "
            f"{all_data_df.shape[0]} rows (ZIP enriched)."
        )
        # return all_data_df, appraisal_data_df, dates, driver, modified
        return all_data_df, dates, driver, modified
    
    finally:
        safe_quit(driver)



allowed = False
if __name__ == "__main__":
    start_date, end_date, years = get_user_input()
    allowed = False

    # Main loop to process each year
    for year in years:
        logger.info(f"Starting scraping process for year {year}")
        run_scraper_for_year(start_date, end_date, year, allowed)