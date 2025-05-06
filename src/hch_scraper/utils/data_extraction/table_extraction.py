import pandas as pd
from io import StringIO

# Selenium-related imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementNotInteractableException,TimeoutException

import hch_scraper.utils.logging_setup  
from hch_scraper.utils.logging_setup import logger

def scrape_table_by_xpath(wait, xpath):
    """
    Scrapes an HTML table by its XPath.

    Args:
        wait: WebDriverWait instance for Selenium.
        xpath: XPath of the table to scrape.

    Returns:
        A pandas DataFrame containing the table data, or an empty DataFrame if scraping fails.
    """    
    if not xpath:
        logger.error("XPath is empty. Cannot locate element.")
        return pd.DataFrame()
    try:
        html = wait.until(EC.visibility_of_element_located((By.XPATH, xpath))).get_attribute("outerHTML")
        return pd.read_html(StringIO(html))[0]
    except TimeoutException as e:
        logger.error(f"Table at {xpath} not found: {e}")
        return pd.DataFrame()
    except ValueError as e:
        logger.error(f"Failed to parse table at {xpath}: {e}")
        return pd.DataFrame()

def scroll_and_click(driver, wait, element):
    """
    Scrolls to an element and clicks it.

    Args:
    - driver: Selenium WebDriver instance.
    - element: A web element on a webpage.

    Returns:
        None
    """
    try:
        # Wait until the element is clickable
        wait.until(EC.element_to_be_clickable(element))

        # Scroll to the element
        driver.execute_script("arguments[0].scrollIntoView(true);", element)

        # Click the element
        element.click()
        
    except ElementNotInteractableException as e:
        logger.warning(f"Element not interactable. Using JS click: {e}")
        driver.execute_script("arguments[0].click();", element)

    except Exception as e:
        logger.error(f"Failed to interact with element: {e}")

def find_click_row(driver, wait, xpath:str):
    """
    Clicks on an element in a table

    Args:
    - driver: Selenium WebDriver instance.
    - wait: a web element on a webpage.
    - xpath: locates an element in an XML or HTML document

    Returns:
        A table in a DataFrame format.
    """
    row = driver.find_element(By.XPATH, xpath)
    wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    scroll_and_click(driver, wait, row)

def transform_table(table):
    if table.empty:
        logger.warning("Received an empty table for transformation.")
        return pd.DataFrame()  # Return an empty DataFrame if input is empty
    table = table.T.reset_index(drop=True)
    table.columns = table.iloc[0,:]
    table = table.drop(0,axis=0)
    return table
