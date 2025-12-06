import os
from pathlib import Path
from typing import Union
import pandas as pd

from hch_scraper.utils.logging_setup import logger


def save_to_csv(
    df: pd.DataFrame,
    file_path: Union[str, Path],
    overwrite: bool = False,
    index: bool = False,
) -> bool:
    """
    Saves a Pandas DataFrame to a CSV file with robust error handling.

    Args:
        df (pd.DataFrame): The DataFrame to save.
        file_path (Union[str, Path]): The full path where the CSV will be saved.
        overwrite (bool): If True, overwrites the existing file. If False and file exists, appends without header. Default is False.
        index (bool): Whether to include the DataFrame index in the CSV file. Default is False.

    Returns:
        bool: True if the file is saved successfully, False otherwise.

    Raises:
        ValueError: If the input is not a DataFrame or the file path is invalid.
        Exception: If the file fails to save due to an I/O error.
    """
    if not isinstance(df, pd.DataFrame):
        logger.error("Provided object is not a Pandas DataFrame.")
        raise ValueError("The input data must be a Pandas DataFrame.")

    if not isinstance(file_path, (str, Path)):
        raise ValueError("The file path must be a string or Path object.")

    file_path = Path(file_path)  # Ensures consistency

    # Choose mode: write ('w') or append ('a') based on overwrite flag and file existence
    mode, header = (
        ("w", True)
        if overwrite
        else ("a", False) if file_path.exists() else ("w", True)
    )

    try:
        df.to_csv(file_path, mode=mode, header=header, index=index)
        logger.info(
            f"Saved {df.shape[0]} rows and {df.shape[1]} columns to {file_path}"
        )
        return True
    except Exception as e:
        logger.error(f"Error saving CSV to {file_path}: {e}")
        raise


def get_file_path(base_dir: str, data_type: str, filename: str) -> Path:
    """
    Constructs a file path by combining base directory, data type subfolder, and filename.

    Args:
        base_dir (str): Base directory for saving the file.
        data_type (str): Subdirectory like 'raw' or 'processed'.
        filename (str): Name of the output file.

    Returns:
        Path: A Path object representing the complete file path.
    """
    return Path(base_dir) / "data" / data_type / filename
