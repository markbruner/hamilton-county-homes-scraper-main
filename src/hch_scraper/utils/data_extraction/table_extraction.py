import pandas as pd
from io import StringIO

# Selenium-related imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementNotInteractableException, TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement

from hch_scraper.utils.logging_setup import logger

# -------------------------------------
# Table Extraction & Interaction Helpers
# -------------------------------------

def scrape_table_by_xpath(wait: WebDriverWait, xpath: str) -> pd.DataFrame:
    """
    Extracts the first HTML table found at the specified XPath and returns it as a DataFrame.

    Args:
        wait (WebDriverWait): WebDriverWait instance to handle explicit wait.
        xpath (str): XPath of the HTML table element to scrape.

    Returns:
        pd.DataFrame: Parsed table data if successful, otherwise an empty DataFrame.

    Logs: 
        - Errors if the table is not found or cannot be parsed.
    """
    if not xpath:
        logger.error("XPath is empty. Cannot locate element.")
        return pd.DataFrame()

    try:
        html = wait.until(EC.visibility_of_element_located((By.XPATH, xpath))).get_attribute("outerHTML")
        return pd.read_html(StringIO(html))[0]
    except TimeoutException as e:
        logger.error(f"Table at {xpath} not found: {e}")
    except ValueError as e:
        logger.error(f"Failed to parse table at {xpath}: {e}")
    
    return pd.DataFrame()


def scroll_and_click(driver: WebDriver, wait: WebDriverWait, element: WebElement) -> None:
    """
    Scrolls to a specified web element and attempts to click it. Falls back to JavaScript click if needed.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        wait (WebDriverWait): WebDriverWait instance for clickability.
        element (WebElement): Element to scroll to and click.

    Logs:
        - Warning if default click fails and fallback is used.
        - Error for unexpected failures.
    """
    try:
        wait.until(EC.element_to_be_clickable(element))
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        element.click()
    except ElementNotInteractableException as e:
        logger.warning(f"Element not interactable. Using JS click: {e}")
        driver.execute_script("arguments[0].click();", element)
    except Exception as e:
        logger.error(f"Failed to interact with element: {e}")


def find_click_row(driver: WebDriver, wait: WebDriverWait, xpath: str) -> None:
    """
    Locates and clicks an element in a table using its XPath.

    Args:
        driver (WebDriver): Selenium WebDriver instance.
        wait (WebDriverWait): Wait handler to ensure element is clickable.
        xpath (str): XPath to the target element.

    Logs:
        - Error if the element is not clickable or interaction fails.
    """
    row = driver.find_element(By.XPATH, xpath)
    wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    scroll_and_click(driver, wait, row)


def transform_table(table: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms a table by transposing it and using the first row as column headers.

    Args:
        table (pd.DataFrame): Input DataFrame to reshape.

    Returns:
        pd.DataFrame: A reshaped DataFrame or an empty DataFrame if the input is empty.

    Notes:
        - Assumes that the first row contains new headers.
        - Used when scraped tables are rotated (e.g., vertical headers).
    """
    if table.empty:
        logger.warning("Received an empty table for transformation.")
        return pd.DataFrame()
    
    table = table.T.reset_index(drop=True)
    table.columns = table.iloc[0, :]
    table = table.drop(0, axis=0)
    return table
