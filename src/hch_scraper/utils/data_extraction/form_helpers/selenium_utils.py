import time

# Selenium-related imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException, StaleElementReferenceException

import hch_scraper.utils.logging_setup  
from hch_scraper.utils.logging_setup import logger

def fill_form_field(wait, field_id, value, retries=3, delay=1, clear_field=True):
    """
    Fills in a form field given its ID and value to enter.

    Parameters:
    - wait (WebDriverWait): Selenium WebDriverWait instance for handling explicit waits.
    - field_id (str): The ID of the form field to locate.
    - value (str): The value to enter into the form field.
    - retries (int): Number of retries if the field is not immediately available. Default is 3.
    - delay (int): Delay in seconds between retries. Default is 1.
    - clear_field (bool): Whether to clear the existing value before entering a new one. Default is True.

    Returns:
    - bool: True if the field was successfully filled, False otherwise.
    """
    # Validate parameters
    if not isinstance(field_id, str) or not field_id.strip():
        logger.error("Invalid field ID provided.")
        raise ValueError("field_id must be a non-empty string.")
    if value is None:
        logger.error("Value to enter in the form field cannot be None.")
        raise ValueError("value must not be None.")

    for attempt in range(1, retries + 1):
        try:
            # Locate the form field by its ID
            field = wait.until(EC.presence_of_element_located((By.ID, field_id)))

            # Optionally clear the existing value
            if clear_field:
                field.clear()

            # Enter the provided value
            field.send_keys(value)
            logger.info(f"Successfully filled form field {field_id} with value '{value}'.")
            return True
        except TimeoutException as e:
            logger.warning(f"Attempt {attempt}/{retries} to locate form field {field_id} timed out: {e}")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Unexpected error while interacting with form field {field_id}: {e}")
            raise

    # Log failure after exhausting retries
    logger.error(f"Failed to fill form field {field_id} after {retries} attempts.")
    return False


def get_text(driver, wait, xpath, retries=3, delay=1):
    """
    Retrieves the text from an element located by its XPATH with retry logic.

    Parameters:
    - wait (WebDriverWait): Selenium WebDriverWait instance for waiting on elements.
    - xpath (str): The XPATH of the element to retrieve text from.
    - retries (int): Number of retries if the element is not found or is inaccessible. Default is 3.
    - delay (int): Delay in seconds between retries. Default is 1.

    Returns:
    - str: The text of the element if found, or raises an exception if all retries fail.
    """
    for attempt in range(1, retries + 1):
        try:
            # Wait for the element to be located
            element = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            text = element.text.strip()
            if not text:
                logger.warning(f"Element located at {xpath} exists but contains no text.")
            return text
        
        except ElementClickInterceptedException as e:
            logger.warning(
                f"Attempt {attempt}/{retries} to get text at {xpath} intercepted by another element: {e}"
            )
            time.sleep(delay)

        except TimeoutException as e:
            logger.error(
                f"Attempt {attempt}/{retries} timed out while waiting for element at {xpath}: {e}"
            )
            time.sleep(delay)
            
        except StaleElementReferenceException as e:
            logger.warning(
                f"Stale element encountered at {xpath}. Retrying... (Attempt {attempt}/{retries})"
            )
            time.sleep(delay)

        except Exception as e:
            logger.error(f"Unexpected error while attempting to get text at {xpath}: {e}")
            raise

    # Raise a timeout error if all retries fail
    raise TimeoutException(f"Failed to retrieve text from element at {xpath} after {retries} attempts.")


def safe_quit(driver):
    try:
        driver.quit()
        logger.info("Driver quit successfully.")
    except Exception as e:
        logger.error(f"Failed to quit the driver gracefully: {e}")