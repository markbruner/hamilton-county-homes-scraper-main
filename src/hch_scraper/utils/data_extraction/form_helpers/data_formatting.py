import re
import pandas as pd
import numpy as np
from typing import List, Tuple, Dict

from hch_scraper.utils.logging_setup import logger

from hch_scraper.utils.data_extraction.form_helpers.file_io import get_file_path, save_to_csv


def format_column_name(
    name: str,
    to_lower: bool = True, 
    strip_underscores: bool = False, 
    prefix: str = None
) -> str:
    """
    Formats a column name by replacing spaces with underscores, removing special characters,
    and optionally converting to lowercase, stripping leading/trailing underscores, or adding a prefix.

    Args :
    - name (str) : The column name to format.
    - to_lower (bool) : Whether to convert the name to lowercase. Default is True.
    - strip_underscores (bool) : Whether to strip leading/trailing underscores. Default is False.
    - prefix (str) : Optional prefix to add to the column name. Default is None.

    Returns :
    - str : The formatted column name.

    Raises :
    - ValueError: If the provided name is not a non-empty string.
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


def final_csv_conversion(
    all_data_df: pd.DataFrame,
    start_date : str,
    end_date : str,
) -> Dict[pd.DataFrame,pd.DataFrame]:
    """
    Cleans and saves home sales data to CSV files.

    This function formats column names, removes duplicates, updates the date list,
    and writes the resulting DataFrame to year-specific and cumulative CSV files.

    Args:
        all_data_df (pd.DataFrame): The raw DataFrame to clean and save.
        start_date (str): Start date of the current range.
        end_date (str): End date of the current range.

    Raises:
        ValueError: If `dates` is not a list of (start, end) tuples.
    """
    # Merge and process data
    df = all_data_df

    logger.info(f"Beginning cleaning and formatting data of {df.shape[0]} rows.")
    df = clean_and_format_columns(df, ["last_transfer_date", "last_sale_amount", "parcel_id"])
    
    df = df.drop_duplicates()
    start_date_clean = start_date.replace("/",'')
    end_date_clean = end_date.replace("/",'')

    # Save CSV files
    homes_csv_path = get_file_path(".", "raw/home_sales", f"homes_{start_date_clean}_{end_date_clean}.csv")
    all_homes_csv_path = get_file_path(".", "raw/home_sales", "homes_all.csv")
    save_to_csv(df, homes_csv_path)
    save_to_csv(df, all_homes_csv_path)
    
def clean_and_format_columns(df: pd.DataFrame, drop_cols: List[str]) -> pd.DataFrame:
    """
    Formats and cleans DataFrame column names, and removes specified columns if present.

    This function applies standard formatting to all column names using `format_column_name`,
    then removes any columns listed in `drop_cols` that exist in the DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame whose columns will be formatted and optionally dropped.
        drop_cols (List[str]): A list of column names to drop, if they exist in the DataFrame.

    Returns:
        pd.DataFrame: A new DataFrame with formatted column names and specified columns removed.
    """
    formatted_columns = [format_column_name(col) for col in df.columns]
    df.columns = formatted_columns
    return df.drop([col for col in drop_cols if col in df.columns], axis=1)
