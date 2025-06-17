"""
Logging setup module for the Hamilton County Homes Scraper.

This script initializes a logger named 'hch_scraper' with both a console
stream handler (for real-time feedback during development) and a rotating
file handler (for persistent logs). Logs are saved in a 'logs/' directory 
located three levels above the current file (at the project root).

Features:
- Console output for debugging
- Rotating log files with size limit and backups
- Automatic creation of a logs directory

Usage:
    from hch_scraper.utils.logging_setup import logger
    logger.info("Message to log")
"""

import os
import logging
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------
# 1) Create logs folder (relative to project root, not inside src/)
# ---------------------------------------------------------------------
LOG_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs')
)
os.makedirs(LOG_DIR, exist_ok=True)  # Create the logs directory if it doesn't exist

# ---------------------------------------------------------------------
# 2) Set up named logger for the application
# ---------------------------------------------------------------------
logger = logging.getLogger('hch_scraper')
logger.setLevel(logging.INFO)  # Default level; can be adjusted dynamically

# ---------------------------------------------------------------------
# 3) Console handler (logs to terminal during execution)
# ---------------------------------------------------------------------
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)  # Show all logs in the console during dev
ch.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)-8s [%(name)s] %(message)s'
))
logger.addHandler(ch)

# ---------------------------------------------------------------------
# 4) Rotating file handler (logs written to disk with rotation)
# ---------------------------------------------------------------------
fh = RotatingFileHandler(
    os.path.join(LOG_DIR, 'scraper.log'),  # Log file path
    maxBytes=5 * 1024 * 1024,              # 5 MB per file
    backupCount=3                          # Keep 3 backup files
)
fh.setLevel(logging.INFO)  # Only log INFO and above to file
fh.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)-8s [%(name)s] %(message)s'
))
logger.addHandler(fh)
