import time

from urllib.robotparser import RobotFileParser

# Selenium-related imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException
    ,ElementClickInterceptedException
    ,StaleElementReferenceException
    ,TimeoutException
    )

import hch_scraper.utils.logging_setup  
from hch_scraper.utils.logging_setup import logger

# Custom exceptions
class SafeClickError(Exception):
    """Custom exception for safe click failures."""
    pass

from hch_scraper.config.settings import form_xpaths_list, XPATHS, URLS
from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import fill_form_field

def safe_click(wait, xpath, retries=3, delay=1, log=True):
    """
    Clicks an element located by its XPATH with retry logic.
    """
    for attempt in range(1, retries + 1):
        try:
            element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            element.click()
            if log:
                logger.info(f"Successfully clicked element at {xpath}.")
            return True
        except (ElementClickInterceptedException, TimeoutException) as e:
            if log:
                logger.info(f"Attempt {attempt}/{retries} to click element failed: {e}")
            time.sleep(delay)
        except StaleElementReferenceException as e:
            if log:
                logger.info(f"Stale element encountered on attempt {attempt}/{retries}: {e}")
            time.sleep(delay)
        except Exception as e:
            if log:
                logger.error(f"Unexpected error on attempt {attempt}/{retries}: {e}")
            raise

    # Log failure and raise custom exception
    if log:
        logger.error(f"Failed to click element at {xpath} after {retries} attempts.")
    raise SafeClickError(f"Failed to click element at {xpath} after {retries} attempts.")

def next_navigation(driver, wait, xpath):
    """Navigates to the next page in the search results, if available."""
    try:
        next_button = driver.find_element(By.XPATH, xpath)
        if "disabled" not in next_button.get_attribute("class"):
            safe_click(wait, xpath)
            return True  # Successfully moved to next page
        else:
            return False  # No more pages
    except NoSuchElementException:
        return False  # "Next" button doesn"t exist

def initialize_search(wait,start,end,ids,values):
    
    safe_click(wait,XPATHS["search"]["property_search"])
    safe_click(wait,XPATHS["search"]["sales_radio_button"]) 

    fill_form_field(wait, "sale_date_low", start)
    fill_form_field(wait, "sale_date_high", end)

    # Form values to filter search.
    for field_id, value in zip(ids, values):
        fill_form_field(wait, field_id, value)

    # Click conventional style
    for xpath in form_xpaths_list:
        safe_click(wait,xpath)
        
def check_allowed_webscraping(driver):

    ROBOTS_TXT_URL = URLS['robots']
    BASE_URL = URLS['base']

    rp = RobotFileParser()
    rp.set_url(ROBOTS_TXT_URL)
    rp.read()

    if rp.can_fetch("*", BASE_URL):
        logger.info(f"Scraping allowed for {BASE_URL}")
        return True
    else:
        print(f"Scraping NOT allowed for {BASE_URL}")
        driver.quit()
        return False