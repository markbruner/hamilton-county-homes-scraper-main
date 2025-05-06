import os
import logging

from logging.handlers import RotatingFileHandler

# 1) Create logs folder (one level above src/)
LOG_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs')
)
os.makedirs(LOG_DIR, exist_ok=True)

# 2) Configure root logger (or a named one)
logger = logging.getLogger('hch_scraper')
logger.setLevel(logging.INFO)

# 3) Console handler (optional)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)-8s [%(name)s] %(message)s'
))
logger.addHandler(ch)

# 4) Rotating file handler
fh = RotatingFileHandler(
    os.path.join(LOG_DIR, 'scraper.log'),
    maxBytes=5 * 1024 * 1024,
    backupCount=3
)
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)-8s [%(name)s] %(message)s'
))
logger.addHandler(fh)





