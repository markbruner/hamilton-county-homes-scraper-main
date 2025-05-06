import subprocess
import sys

import time
import pandas as pd

import hch_scraper.utils.logging_setup  
from hch_scraper.utils.logging_setup import logger
from hch_scraper.config.settings import URLS
from hch_scraper.driver_setup import init_driver
from hch_scraper.scraper import scrape_data

from hch_scraper.utils.io.navigation import initialize_search, check_allowed_webscraping

from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import safe_quit
from hch_scraper.utils.data_extraction.form_helpers.data_formatting import final_csv_conversion
from hch_scraper.utils.data_extraction.form_helpers.datetime_utils import check_reset_needed

def install_packages(requirements_files='requirements.txt'):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_files])

def get_user_input():
    sale_price_low = int(input("What is the lowest price? "))
    sale_price_high = int(input("What is the highest price? "))
    finished_sq_ft_low = int(input("What is the lowest square feet? "))
    finished_sq_ft_high = int(input("What is the highest square feet? "))
    bedrooms_low = int(input("What is the lowest number of bedrooms? "))

    query_ids = ["sale_price_low", "sale_price_high", "finished_sq_ft_low", "finished_sq_ft_high", "bedrooms_low"]
    query_values = [sale_price_low, sale_price_high, finished_sq_ft_low, finished_sq_ft_high, bedrooms_low]

    start_year = int(input("What year do you want to start the search? "))
    end_year = int(input("What year do you want to end the search? "))

    return query_ids, query_values, range(start_year, end_year + 1)

def run_scraper_for_year(year, allowed, query_ids, query_values):
    start_date = f"01/01/{year}"
    end_date = f"12/31/{year}"
    dates = [(start_date, end_date)]

    while dates:
        for start_date, end_date in dates[:]:
            logger.info(f"Starting scraping process for start date, {start_date}, and end date, {end_date}")

            all_data_df = pd.DataFrame()
            appraisal_data_df = pd.DataFrame()

            all_data, appraisal_data, dates, driver, modified = main(
                allowed=allowed,
                start=start_date,
                end=end_date,
                ids=query_ids,
                values=query_values,
                dates=dates
            )

            if modified:
                break

            all_data_df = pd.concat([all_data_df, all_data], axis=0, ignore_index=True)
            appraisal_data_df = pd.concat([appraisal_data_df, appraisal_data], axis=0, ignore_index=True)

            csv_path_dict, final_df = final_csv_conversion(
            all_data_df, appraisal_data_df, dates, start_date, end_date, year
            )

def main(allowed, start, end, dates, ids, values): 
    BASE_URL = URLS['base']
    driver, wait = init_driver(BASE_URL)

    # Ensuring that webscraping on the website is allowed.
    if not allowed:
        allowed = check_allowed_webscraping(driver)

    try:
        initialize_search(wait, start, end, ids, values)
        time.sleep(2)
        reset_needed, modified, dates, num_properties_to_scrape  = check_reset_needed(driver, wait, start, end, dates)

        if reset_needed:
            logger.info("Reset needed, closing WebDriver.")
            return pd.DataFrame(), pd.DataFrame(), dates, driver, modified
        
        # Scrape data
        data = scrape_data(driver, wait, num_properties_to_scrape )  
        all_data = data['summary']
        appraisal_data = data['details']

        assert all_data, "No all_data returned!"
        assert appraisal_data, "No appraisal_data returned!"            
        # Consolidate data

        all_data_df = pd.concat(all_data).reset_index(drop=True)
        all_data_df.columns = ['Parcel Number', 'Address', 'BBB', 'FinSqFt', 'Use', 'Year Built','Transfer Date', 'Amount']
        appraisal_data_df = pd.concat(appraisal_data).reset_index(drop=True)

        logger.info(f'Completed the main scraping of property data for {start} and {end}. Beginning address cleaning and converting to a csv file.')
        return all_data_df, appraisal_data_df, dates, driver, modified
    
    finally:
        safe_quit(driver)



allowed = False
if __name__ == "__main__":
    # Check and install requirements
    install_packages("requirements.txt")

    query_ids, query_values, years = get_user_input()
    allowed = False

    # Main loop to process each year
    for year in years:
        logger.info(f"Starting scraping process for year {year}")
        run_scraper_for_year(year, allowed, query_ids, query_values)