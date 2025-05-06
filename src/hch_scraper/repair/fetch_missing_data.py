from hch_scraper.config.settings import  XPATHS
import hch_scraper.utils.logging_setup 
from hch_scraper.utils.logging_setup import logger
from hch_scraper.scraper import scrape_table_by_xpath
from hch_scraper.utils.io.navigation import safe_click
from hch_scraper.utils.data_extraction.form_helpers.selenium_utils import fill_form_field, get_text
from hch_scraper.utils.data_extraction.table_extraction import transform_table

def extract_patched_property_details(driver, id, wait):
    """
    Extracts detailed property information, including appraisal, tax, and transfer data.

    Parameters:
    - wait (WebDriverWait): Selenium WebDriverWait instance for handling explicit waits.

    Returns:
    - pd.DataFrame: DataFrame containing property details, or None if an error occurs.
    """
    try:
        # Scrape and transform the appraisal table
        appraisal_table = scrape_table_by_xpath(wait, XPATHS["view"]["appraisal_information"])

        if appraisal_table is None or appraisal_table.empty:
            logger.warning(f"Appraisal table is empty for parcel {id}.")
            return None
        appraisal_table = transform_table(appraisal_table)
        # Drop unwanted columns
        columns_to_drop = ["Year Built", "Deed Number", "# of Parcels Sold"]
        appraisal_table = appraisal_table.drop(
            [col for col in columns_to_drop if col in appraisal_table.columns], axis=1
        )

        # Rename columns
        appraisal_table.rename(
            columns={
                "# Bedrooms": "Bedrooms",
                "# Full Bathrooms": "Full Baths",
                "# Half Bathrooms": "Half Baths"
            }, inplace=True
        )

        # Add additional property details
        appraisal_table["parcel_id"] = id
        appraisal_table["school_district"] = get_text(driver, wait, XPATHS["property"]["school_district"])
        appraisal_table["owner_address"] = get_text(driver, wait, XPATHS["property"]["owner"])

        return appraisal_table

    except Exception as e:
        logger.error(f"Error extracting details for parcel {id if 'parcel_id' in locals() else 'unknown'}: {e}")
        return None

def patch_data(wait, driver, missing_id):
    safe_click(wait,XPATHS["search"]["parcel_id"]) 
    # Form values to filter search.
    fill_form_field(wait, "parcel_number",missing_id)

    safe_click(wait, XPATHS['search']['parcel_id_search_button'])
    appraisal_table = extract_patched_property_details(driver, missing_id, wait)
    safe_click(wait, XPATHS['property']['new_search'])   
    return appraisal_table