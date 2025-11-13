import time
import numpy as np
from urllib.robotparser import RobotFileParser

# Selenium-related imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)

from hch_scraper.utils.logging_setup import logger
from hch_scraper.config.settings import form_xpaths_list, XPATHS, URLS
from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import fill_form_field

# ----------------------------------------
# Custom Exception
# ----------------------------------------

class SafeClickError(Exception):
    """
    Custom exception raised when an element fails to be clicked
    after a defined number of retry attempts using `safe_click`.
    """
    pass

# ----------------------------------------
# Web Interaction Utilities
# ----------------------------------------

def safe_click(
    wait: WebDriverWait,
    xpath: str, 
    retries: int = 3, 
    delay: int = 1, 
    log: bool = True
) -> bool:
    """
    Clicks an element located by its XPath with retries and optional logging.

    Args:
        wait (WebDriverWait): WebDriverWait instance to manage timing.
        xpath (str): XPath to the clickable element.
        retries (int, optional): Number of retry attempts. Defaults to 3.
        delay (int, optional): Delay (in seconds) between attempts. Defaults to 1.
        log (bool, optional): Enable logging of attempts and errors. Defaults to True.

    Returns:
        bool: True if the element was clicked successfully.

    Raises:
        SafeClickError: If the element could not be clicked after all retries.
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
                logger.info(f"Stale element on attempt {attempt}/{retries}: {e}")
            time.sleep(delay)
        except Exception as e:
            if log:
                logger.error(f"Unexpected error on attempt {attempt}/{retries}: {e}")
            raise

    if log:
        logger.error(f"Failed to click element at {xpath} after {retries} attempts.")
    raise SafeClickError(f"Failed to click element at {xpath} after {retries} attempts.")

def next_navigation(driver, wait: WebDriverWait, xpath: str) -> bool:
    """
    Navigates to the next page in a paginated search result table.

    Args:
        driver: Selenium WebDriver instance.
        wait (WebDriverWait): Wait object to allow element availability.
        xpath (str): XPath of the "Next" pagination button.

    Returns:
        bool: True if navigation succeeded, False if no more pages are available.
    """
    try:
        next_button = driver.find_element(By.XPATH, xpath)
        if "disabled" not in next_button.get_attribute("class"):
            safe_click(wait, xpath)
            return True
        return False
    except NoSuchElementException:
        return False

def initialize_search(wait: WebDriverWait, start: str, end: str) -> None:
    """
    Executes the initial form selection and date filter setup for the property search.

    Args:
        wait (WebDriverWait): WebDriverWait instance to control interactions.
        start (str): Start date string for the sale date filter (MM/DD/YYYY).
        end (str): End date string for the sale date filter (MM/DD/YYYY).

    Behavior:
        - Selects the property search tab and sales radio option.
        - Inputs the start and end sale dates.
        - Clicks any additional form field XPaths defined in `form_xpaths_list`.
    """
    safe_click(wait, XPATHS["search"]["property_search"])
    safe_click(wait, XPATHS["search"]["sales_radio_button"])

    fill_form_field(wait, "sale_date_low", start)
    fill_form_field(wait, "sale_date_high", end)

    for xpath in form_xpaths_list:
        safe_click(wait, xpath)

def check_allowed_webscraping(driver) -> bool:
    """
    Validates whether web scraping is allowed for the site based on `robots.txt`.

    Args:
        driver: Selenium WebDriver instance, used to quit if disallowed.

    Returns:
        bool: True if scraping is allowed, False otherwise.

    Behavior:
        - Parses the site's `robots.txt` file.
        - Quits the driver and logs if scraping is disallowed.
    """
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
