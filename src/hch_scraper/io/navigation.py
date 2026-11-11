import time
from datetime import datetime
from urllib.robotparser import RobotFileParser

# Selenium-related imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)

from hch_scraper.utils.logging_setup import logger
from hch_scraper.config.settings import XPATHS, URLS

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
    wait: WebDriverWait, xpath: str, retries: int = 3, delay: int = 1, log: bool = True
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
    raise SafeClickError(
        f"Failed to click element at {xpath} after {retries} attempts."
    )


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
    """Submit a sales search for the supplied MM/DD/YYYY date range."""
    dates = [
        datetime.strptime(value, "%m/%d/%Y").date().isoformat()
        for value in (start, end)
    ]
    safe_click(wait, XPATHS["search"]["sales_tab"])
    for field_id, value in zip(("sale-date-low", "sale-date-high"), dates):
        field = wait.until(EC.visibility_of_element_located((By.ID, field_id)))
        # Native date inputs use ISO values regardless of the browser locale.
        field.parent.execute_script("arguments[0].value = arguments[1];", field, value)
        if field.get_property("value") != value:
            raise ValueError(f"Could not set transfer date field {field_id}.")
    safe_click(wait, XPATHS["search"]["sales_submit"])


def check_allowed_webscraping() -> bool:
    """Check robots.txt for the sales form, results, and export paths."""
    rules = RobotFileParser(URLS["sales_robots"])
    rules.read()
    return all(
        rules.can_fetch("*", URLS["sales"] + path)
        for path in ("", "execute", "results", "results/csv")
    )
