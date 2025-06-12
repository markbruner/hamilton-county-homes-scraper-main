import time

from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException, TimeoutException

import hch_scraper.utils.logging_setup  
from hch_scraper.utils.logging_setup import logger
from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import safe_quit
from pathlib import Path

from hch_scraper.config.settings import SCRAPING_CONFIG, data_storage

MAX_RETRIES = SCRAPING_CONFIG['retry_limit']
TIMEOUT = SCRAPING_CONFIG['page_load_timeout']

def is_valid_url(url):
    """Ensures that a valid URL is being passed"""
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)

def init_driver(base_url, driver_type="firefox", headless=True, max_retries=MAX_RETRIES, timeout=TIMEOUT):
    """
    Initializes a Selenium WebDriver with retries, timeout, and headless option.

    Args:
        base_url (str): URL to open after driver initializes
        driver_type (str): 'firefox' or 'chrome'
        headless (bool): Run browser in headless mode
        max_retries (int): Retry attempts for driver creation
        timeout (int): Seconds to wait for element timeouts

    Returns:
        tuple: (WebDriver instance, WebDriverWait instance)
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
                options.set_preference('browser.download.folderList', 2)
                options.set_preference('browser.download.dir', str(download_dir))
                options.set_preference('browser.helperApps.neverAsk.saveToDisk', 'text/csv,application/csv')
                driver = webdriver.Firefox(options=options)

            elif driver_type.lower() == "chrome":
                options = webdriver.ChromeOptions()
                if headless:
                    options.add_argument('--headless')
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
            logger.warning(f"Attempt {attempt+1} failed: {e}")
            time.sleep(2)

    if driver:
        safe_quit(driver)
    logger.error("Failed to initialize WebDriver after all retry attempts.")
    raise WebDriverException("Failed to initialize WebDriver.")
