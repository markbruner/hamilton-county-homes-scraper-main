import re
import pandas as pd
import numpy as np

import hch_scraper.utils.logging_setup 
from hch_scraper.utils.logging_setup import logger
from hch_scraper.config.mappings.street_map import street_type_map
from hch_scraper.config.mappings.district_map import school_city_map

from hch_scraper.utils.data_extraction.address_cleaners import owner_address_cleaner, tag_address
from hch_scraper.geocoding import geocode_until_complete
from hch_scraper.utils.data_extraction.form_helpers.file_io import get_file_path, save_to_csv


def format_column_name(name, to_lower=True, strip_underscores=False, prefix=None):
    """
    Formats a column name by replacing spaces with underscores, removing special characters,
    and optionally converting to lowercase, stripping leading/trailing underscores, or adding a prefix.

    Parameters:
    - name (str): The column name to format.
    - to_lower (bool): Whether to convert the name to lowercase. Default is True.
    - strip_underscores (bool): Whether to strip leading/trailing underscores. Default is False.
    - prefix (str): Optional prefix to add to the column name. Default is None.

    Returns:
    - str: The formatted column name.
    """
    if not isinstance(name, str) or not name:
        logger.error(f"Invalid column name: {name}")
        raise ValueError("Column name must be a non-empty string")
    
    # Replace spaces and remove special characters
    name = name.replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9_]+", "", name)
    
    # Apply transformations
    if to_lower:
        name = name.lower()
    if strip_underscores:
        name = name.strip("_")
    if prefix:
        name = f"{prefix}_{name}"
    
    return name


def final_csv_conversion(all_data_df, appraisal_data_df, dates, start_date, end_date, year):
    """
    Processes and saves home data to CSV files with additional cleaning and address concatenation.
    """
    if appraisal_data_df.empty:
        logger.warning("Appraisal data is empty. Exiting function.")
        return None

    # Validate dates
    if not isinstance(dates, list) or not all(isinstance(d, tuple) and len(d) == 2 for d in dates):
        logger.error("Dates must be a list of tuples with start and end dates.")
        raise ValueError("Invalid dates format")

    # Merge and process data

    final_df = all_data_df.merge(appraisal_data_df, left_on="Parcel Number", right_on="parcel_id", how="left")
    logger.info(f'These are the dates in the list: {dates}')

    logger.info("Beginning cleaning and formatting data.")
    final_df = clean_and_format_columns(final_df, ["last_transfer_date", "last_sale_amount", "parcel_id"])

    logger.info("Beginning replacing of the street type (i.e. dr, rd, way, etc...) with the new mapping.")    
    pattern = r'\b(' + '|'.join(map(re.escape, street_type_map.keys())) + r')\b'
    final_df['address'] = final_df['address'].str.replace(
                            pattern,
                            lambda m: street_type_map[m.group(0)],
                            regex=True
                        )
    
    logger.info("Owners data is starting the cleaning and formatting data process.")
    final_df = owner_address_cleaner(final_df)


    # Address processing
    logger.info("Processing address columns for geocoding.")
    address_parts = [
    {**tag_address(address), 'parcel_number': parcel}
    for parcel, address in zip(final_df.parcel_number, final_df.address)
    ]
    address_df = pd.DataFrame.from_dict(address_parts)
    address_df = address_df.drop_duplicates()
    final_df = final_df.merge(address_df, left_on='parcel_number', right_on='parcel_number',how='left')

    # Add city and state
    final_df["city"] = final_df.school_district.map(school_city_map)
    final_df["state"] = "OH"

    # Create concatenated address field
    final_df["new_address"] = np.where(
        final_df["owner_home_address_match"] == "Y",
        final_df["st_num"] + " " + final_df["street"] + " " + final_df["city"] + ", " + final_df["state"] + final_df["owner_postal_code"],
        final_df["st_num"] + " " + final_df["street"] + " " + final_df["city"] + ", " + final_df["state"]
    )
    
    final_df = final_df.drop_duplicates()
    logger.info(f'Removing these dates: {start_date} and {end_date}')
    dates.remove((start_date, end_date))

    final_df['latitude'] = np.nan
    final_df['longitude'] = np.nan

    # geocoding the addresses of all the homes.
    final_df = geocode_until_complete(final_df)

    # Save CSV files
    homes_csv_path = get_file_path(".", 'raw', f"homes_{year}.csv")
    all_homes_csv_path = get_file_path(".", 'raw', "homes_all.csv")
    geocoded_homes_csv_path = get_file_path(".", 'processed', "homes_geocoded.csv")
    save_to_csv(final_df, homes_csv_path)
    save_to_csv(final_df, all_homes_csv_path)
    save_to_csv(final_df, geocoded_homes_csv_path)
    
    return {"homes_csv": homes_csv_path, "all_homes_csv": all_homes_csv_path, "geocoded_homes_csv":geocoded_homes_csv_path}



def clean_and_format_columns(df, drop_cols):
    """
    Replaces the current df's columns with ones that have been formatted or better readability.
    """
    formatted_columns = [format_column_name(col) for col in df.columns]
    df.columns = formatted_columns
    return df.drop([col for col in drop_cols if col in df.columns], axis=1)
