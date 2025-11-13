import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "selectors/xpaths.yaml"

# Loading XPaths and other settings from YAML file
def load_config(file_path):
    with open(file_path,"r") as file:
        return yaml.safe_load(file)

XPATHS = load_config(CONFIG_PATH)

# Form elements used in multiple scrapers
form_xpaths_list = [
    # XPATHS["search"]["conventional_home_type"],
    XPATHS["search"]["form_search_button"]
]

# Web and API endpoints
URLS = {
    "base": 'https://www.hamiltoncountyauditor.org',
    "robots": 'https://www.hamiltoncountyauditor.org/robots.txt',
    "geocoding_api": 'http://api.positionstack.com/v1/forward'
}

CACHE_PATHS = {
    "geocoding_cache":"data/processed/geocode_cache.json",
    "address_parts_cache":"data/processed/address_parts_cache.json"
}

# Retry and timeout settings, all in seconds
SCRAPING_CONFIG = {
    "page_load_timeout": 30,
    "max_entries_per_page": 1000,
    "retry_limit": 3
}

logging_config = {
    "filename": "scraper.log",
    "level": "INFO",
    "format": "%(asctime)s - %(levelname)s - %(message)s",
}

data_storage = {
    "raw": "data/raw/",
    "processed": "data/processed/",
    "output_file": "data/output.csv"
}

map_center = dict(lat=39.2127649, lon=-84.3831728)


colorscale = {
     '044867':'rgba(0, 38, 66,.1)',    
     '045146':'rgba(132, 0, 50,.1)',
     '044289':'rgba(0, 187, 249,.1)',
     '044313':'rgba(0, 245, 212,.1)',
    '044271':'rgba(175, 43, 191,.1)',
}

district_color_map = {
    'SYCAMORE CSD': ' rgba(132, 0, 50,1)',
    'WYOMING CSD': 'rgba(0, 38, 66,1)',
    'MADEIRA CSD': 'rgba(0, 187, 249,1)',
    'MARIEMONT CSD': 'rgba(0, 245, 212,1)',
    'LOVELAND CSD':'rgba(175, 43, 191,1)',
    # Add more districts and colors as needed
}


CLUSTER_MIN_SIZE = 5
CLUSTER_MIN_SAMPLES = 1

# Normalized street suffix mapping
from hch_scraper.config.mappings.street_types import street_type_map

# School district mappings
from hch_scraper.config.mappings.school_districts import school_city_map, zip_code_map





