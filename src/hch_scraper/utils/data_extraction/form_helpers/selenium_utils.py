import time

# Selenium-related imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
    StaleElementReferenceException,
)

from hch_scraper.utils.logging_setup import logger


def fill_form_field(
    wait,
    field_id: str,
    value: str,
    retries: int = 3,
    delay: int = 1,
    clear_field: bool = True
) -> bool:
    """
    Fills a form field identified by its ID with a given value.

    Args:
        wait: Selenium WebDriverWait instance.
        field_id (str): The ID of the form input field.
        value (str): The value to enter.
        retries (int, optional): Number of retry attempts. Defaults to 3.
        delay (int, optional): Delay in seconds between retries. Defaults to 1.
        clear_field (bool, optional): Whether to clear the field before input. Defaults to True.

    Returns:
        bool: True if successfully filled, False otherwise.

    Raises:
        ValueError: If `field_id` is invalid or `value` is None.
        Exception: If unexpected issues occur while interacting with the field.
    """
    if not isinstance(field_id, str) or not field_id.strip():
        logger.error("Invalid field ID provided.")
        raise ValueError("field_id must be a non-empty string.")
    if value is None:
        logger.error("Value to enter in the form field cannot be None.")
        raise ValueError("value must not be None.")

    for attempt in range(1, retries + 1):
        try:
            field = wait.until(EC.presence_of_element_located((By.ID, field_id)))
            if clear_field:
                field.clear()
            field.send_keys(value)
            logger.info(f"Filled form field '{field_id}' with '{value}'.")
            return True
        except TimeoutException as e:
            logger.warning(f"[{attempt}/{retries}] Timeout locating field '{field_id}': {e}")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Error interacting with form field '{field_id}': {e}")
            raise

    logger.error(f"Failed to fill form field '{field_id}' after {retries} attempts.")
    return False


def get_text(
    driver,
    wait,
    xpath: str,
    retries: int = 3,
    delay: int = 1
) -> str:
    """
    Retrieves and returns the text content from an element located by XPATH.

    Args:
        driver: Selenium WebDriver instance.
        wait: Selenium WebDriverWait instance.
        xpath (str): The XPATH of the target element.
        retries (int, optional): Number of retry attempts. Defaults to 3.
        delay (int, optional): Delay in seconds between retries. Defaults to 1.

    Returns:
        str: The stripped text from the element.

    Raises:
        TimeoutException: If element not found after all retries.
        Exception: For unexpected Selenium errors.
    """
    for attempt in range(1, retries + 1):
        try:
            element = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            text = element.text.strip()
            if not text:
                logger.warning(f"Element at {xpath} exists but contains no text.")
            return text
        except ElementClickInterceptedException as e:
            logger.warning(f"[{attempt}/{retries}] Click intercepted at {xpath}: {e}")
            time.sleep(delay)
        except TimeoutException as e:
            logger.error(f"[{attempt}/{retries}] Timeout waiting for {xpath}: {e}")
            time.sleep(delay)
        except StaleElementReferenceException:
            logger.warning(f"[{attempt}/{retries}] Stale element at {xpath}. Retrying...")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Unexpected error at {xpath}: {e}")
            raise

    raise TimeoutException(f"Failed to retrieve text at {xpath} after {retries} attempts.")


def safe_quit(driver) -> None:
    """
    Quits the Selenium WebDriver instance safely, logging success or failure.

    Args:
        driver: Selenium WebDriver instance to quit.
    """
    try:
        driver.quit()
        logger.info("Driver quit successfully.")
    except Exception as e:
        logger.error(f"Failed to quit the driver: {e}")