import re
import pandas as pd
import numpy as np

import hch_scraper.utils.logging_setup 
from hch_scraper.utils.logging_setup import logger
from hch_scraper.config.mappings.street_map import street_type_map
from hch_scraper.config.mappings.district_map import school_city_map

from hch_scraper.utils.data_extraction.address_cleaners import tag_address, address_enricher
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

    logger.info(f"Beginning cleaning and formatting data of {final_df.shape[0]} rows.")
    final_df = clean_and_format_columns(final_df, ["last_transfer_date", "last_sale_amount", "parcel_id"])

    logger.info("Beginning replacing of the street type (i.e. dr, rd, way, etc...) with the new mapping.")    
    pattern = r'\b(' + '|'.join(map(re.escape, street_type_map.keys())) + r')\b'
    final_df['address'] = final_df['address'].str.replace(
                            pattern,
                            lambda m: street_type_map[m.group(0)],
                            regex=True
                        )
    enricher = address_enricher      # load center-lines once

    # Address processing
    logger.info("Processing address columns for geocoding.")
    parsed_rows = []
    for parcel, addr in zip(final_df.parcel_number, final_df.address):
        enrich = enricher.enrich(addr)        # st_num, street_corrected, postal_code
        enrich["parcel_number"] = parcel
        parsed_rows.append(enrich)

    address_df = pd.DataFrame(parsed_rows).drop_duplicates()
    print(address_df.head())

    final_df = final_df.merge(address_df, on="parcel_number", how="left")

      # Initialize geocoding-related columns
    final_df["formatted_address"] = None
    final_df["city"] = None
    final_df["state"] = None

    # Add city and state defaults
    final_df["city"] = "Cincinnati"
    final_df["state"] = "Ohio"

    final_df["new_address"] = (
        final_df["st_num"] + " " +
        final_df["street_corrected"].fillna(final_df["street"]).str.title() + ", " +
        final_df["city"] + ", " +
        final_df["state"] + " " +
        final_df["postal_code"]
        ).str.replace(r"\s+", " ", regex=True).str.strip(", ")

    print(final_df["street_corrected"]) 
    print(final_df['new_address'])

    final_df = final_df.drop_duplicates()
    logger.info(f'Removing these dates: {start_date} and {end_date}')
    dates.remove((start_date, end_date))

    final_df['latitude'] = np.nan
    final_df['longitude'] = np.nan

    # geocoding the addresses of all the homes.
    final_df = geocode_until_complete(final_df)
    
    cols = ['parcel_number',
            'address',
            'bbb',
            'finsqft',
            'use',
            'year_built',	
            'transfer_date',	
            'amount',	
            'total_rooms',	
            'bedrooms',	
            'full_baths',	
            'half_baths',	
            'conveyance_number',	
            'deed_type',	
            'acreage',	
            'school_district',	
            'st_num',	
            'apt_num',	
            'street',
            'street_corrected',	
            'city',	
            'state',	
            'new_address',	
            'formatted_address',	
            'longitude',	
            'latitude',
            ]
    
    final_df = final_df[cols]
    # Save CSV files
    homes_csv_path = get_file_path(".", "raw/home_sales", f"homes_{year}.csv")
    all_homes_csv_path = get_file_path(".", "raw/home_sales", "homes_all.csv")
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
