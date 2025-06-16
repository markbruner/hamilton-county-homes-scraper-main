"""
Selenium WebDriver Initialization Utility

This module provides helper functions to initialize a Selenium WebDriver
(Firefox or Chrome) with configurable retry logic, download preferences,
timeout settings, and headless execution.

Primary use case: initializing a browser session to begin scraping from a 
valid URL, with support for automatic file downloading.

Usage:
    from hch_scraper.utils.webdriver_init import init_driver
    driver, wait = init_driver("https://example.com", driver_type="firefox")
"""

import time
from urllib.parse import urlparse
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException, TimeoutException

from hch_scraper.utils.logging_setup import logger
from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import safe_quit
from hch_scraper.config.settings import SCRAPING_CONFIG, data_storage

# Constants from configuration
MAX_RETRIES = SCRAPING_CONFIG['retry_limit']
TIMEOUT = SCRAPING_CONFIG['page_load_timeout']


def is_valid_url(url: str) -> bool:
    """
    Validates a URL string to ensure it includes both scheme and netloc.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)


def init_driver(
    base_url: str,
    driver_type: str = "firefox",
    headless: bool = True,
    max_retries: int = MAX_RETRIES,
    timeout: int = TIMEOUT
) -> tuple:
    """
    Initializes a Selenium WebDriver (Firefox or Chrome) with retries,
    headless option, timeout settings, and download preferences.

    Args:
        base_url (str): URL to navigate to after browser starts.
        driver_type (str): Type of browser ("firefox" or "chrome").
        headless (bool): Run browser in headless mode (no UI). Default True.
        max_retries (int): Number of retry attempts if driver fails.
        timeout (int): Timeout in seconds for page elements.

    Returns:
        tuple: (driver: WebDriver, wait: WebDriverWait)

    Raises:
        ValueError: If URL is invalid or driver_type is unsupported.
        WebDriverException: If the driver fails after all retries.
    """
    if not is_valid_url(base_url):
        logger.error(f"Invalid URL provided: {base_url}")
        raise ValueError(f"Invalid URL: {base_url}")

    driver = None
    download_dir = Path(data_storage["raw"]).resolve()
    download_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(max_retries):
        try:
            if driver_type.lower() == "firefox":
                options = webdriver.FirefoxOptions()
                if headless:
                    options.add_argument('--headless')

                # Set Firefox download preferences
                options.set_preference('browser.download.folderList', 2)
                options.set_preference('browser.download.dir', str(download_dir))
                options.set_preference('browser.helperApps.neverAsk.saveToDisk', 'text/csv,application/csv')

                driver = webdriver.Firefox(options=options)

            elif driver_type.lower() == "chrome":
                options = webdriver.ChromeOptions()
                if headless:
                    options.add_argument('--headless')

                # Set Chrome download preferences
                prefs = {
                    'download.default_directory': str(download_dir),
                    'download.prompt_for_download': False,
                    'safebrowsing.enabled': True,
                }
                options.add_experimental_option('prefs', prefs)

                driver = webdriver.Chrome(options=options)

            else:
                raise ValueError(f"Unsupported driver type: {driver_type}")

            driver.get(base_url)
            logger.info(f"Driver initialized and navigated to {base_url}")
            return driver, WebDriverWait(driver, timeout)

        except (WebDriverException, TimeoutException) as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2)

    # If initialization failed after retries, clean up
    if driver:
        safe_quit(driver)

    logger.error("Failed to initialize WebDriver after all retry attempts.")
    raise WebDriverException("Failed to initialize WebDriver.")
