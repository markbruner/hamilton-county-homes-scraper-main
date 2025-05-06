import os
import pandas as pd

import hch_scraper.utils.logging_setup  
from hch_scraper.utils.logging_setup import logger
from pathlib import Path

def save_to_csv(df, file_path, overwrite=False, index=False):
    """
    Saves a Pandas DataFrame to a CSV file with robust error handling.
    
    Parameters:
    - df (pd.DataFrame): The DataFrame to save.
    - file_path (str): The file path where the CSV will be saved.
    - overwrite (bool): Whether to overwrite the file if it exists. Default is False.
    - index (bool): Whether to include the DataFrame index in the CSV. Default is False.
    
    Returns:
    - bool: True if the file is saved successfully, False otherwise.
    """
    if not isinstance(df, pd.DataFrame):
        logger.error("Provided object is not a Pandas DataFrame.")
        raise ValueError("The input data must be a Pandas DataFrame.")
    
    if not isinstance(file_path, (str, Path)):
        raise ValueError("The file path must be a string or Path object.")
    
    # Determine file write modes
    mode, header = ("w", True) if overwrite else ("a", False) if os.path.exists(file_path) else ("w", True)
    
    try:
        df.to_csv(file_path, mode=mode, header=header, index=index)
        logger.info(f"Saved {df.shape[0]} rows and {df.shape[1]} columns to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving CSV to {file_path}: {e}")
        raise

def get_file_path(base_dir, data_type, filename):
    """
    Constructs a file path given the base directory and filename.
    """
    file_path = Path(base_dir) / "data" / data_type / filename
    return file_path

