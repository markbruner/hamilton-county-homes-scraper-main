import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "xpaths.yaml"

# Loading XPaths and other settings from YAML file
def load_config(file_path):
    with open(file_path,"r") as file:
        return yaml.safe_load(file)

XPATHS = load_config(CONFIG_PATH)

# Form elements used in multiple scrapers
form_xpaths_list = [
    XPATHS["search"]["conventional_home_type"],
    XPATHS["search"]["form_search_button"]
]

# Web and API endpoints
URLS = {
    "base": 'https://www.hamiltoncountyauditor.org',
    "robots": 'https://www.hamiltoncountyauditor.org/robots.txt',
    "geocoding_api": 'http://api.positionstack.com/v1/forward'
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

district_idn_map = {
    'CINCINNATI CSD': '043752',
    'DEER PARK CSD': '043851',
    'FINNEYTOWN LSD': '047332',
    'FOREST HILLS LSD': '047340',
    'INDIAN HILL EVSD': '045435',
    'LOCKLAND CSD': '044230',
    'LOVELAND CSD': '044271',
    'MADEIRA CSD': '044289',
    'MARIEMONT CSD': '044313',
    'MILFORD EVSD': '045500',
    'MOUNT HEALTHY CSD': '044412',
    'NORTH COLLEGE HILL CSD': '044511',
    'NORTHWEST LSD (HAMILTON CO.)': '047365',
    'NORWOOD CSD': '044578',
    'OAK HILLS LSD': '047373',
    'PRINCETON CSD': '044677',
    'READING CSD': '044693',
    'SOUTHWEST LSD (HAMILTON CO.)': '047381',
    'ST. BERNARD-ELMWOOD PLACE CSD': '044719',
    'SYCAMORE CSD': '044867',
    'THREE RIVERS LSD': '047399',
    'WINTON WOODS CSD': '044081',
    'WYOMING CSD': '045146'
}

home_type_map = {
    '100': 'Vacant Land',
    '101': 'Cash - Grain Or General Farm',
    '102': 'Livestock Farm Except Dairy & Poultry',
    '103': 'Dairy Farms',
    '104': 'Poultry Farms',
    '105': 'Fruit & Nut Farms',
    '106': 'Vegetable Farms',
    '107': 'Tobacco Farms',
    '108': 'Nurseries',
    '109': 'Greenhouses, Vegetables & Floraculture',
    '110': 'Vacant Land - Cauv',
    '111': 'Cash - Grain Or General Farm-Cauv',
    '112': 'Livestock Farm Except Dairy & Poultry - Cauv',
    '113': 'Dairy Farms - Cauv',
    '114': 'Poultry Farms - Cauv',
    '115': 'Fruit & Nut Farms - Cauv',
    '116': 'Vegetable Farms - Cauv',
    '117': 'Tobacco Farms - Cauv',
    '120': 'Timber',
    '121': 'Timber - Cauv',
    '122': 'Timber - Commerical',
    '123': 'Forestland (Fltp)- Prior To 1994',
    '124': 'Forestland (Fltp) 1994 Or Later',
    '190': 'Other',
    '199': 'Other - Cauv',
    '210': 'Coal Lands, Surface Rights',
    '220': 'Coal Rights, Working Interest',
    '230': 'Coal Rights, Separate Royalty Interest',
    '240': 'Oil & Gas Rights, Working Interest',
    '250': 'Oil & Gas Rights, Separate Royalty Interest',
    '260': 'Other Minerals',
    '300': 'Vacant Land',
    '307': 'Forestry',
    '310': 'Food/Drink Processing',
    '317': 'Forestry With Buildings',
    '320': 'Heavy Manufacturing',
    '330': 'Medium Manufacturing',
    '340': 'Light Manufacturing',
    '350': 'Warehouse',
    '351': 'Warehouse/Multi-Tenant',
    '352': 'Mini Warehouse',
    '360': 'Truck Terminal',
    '370': 'Small Shop',
    '380': 'Mines & Ouarries',
    '389': 'Utility',
    '390': 'Grain Elevator',
    '399': 'Other',
    '400': 'Vacant Land',
    '401': 'Apartments - 4 To 19 Units',
    '402': 'Apartments - 20 To 39 Units',
    '403': 'Apartments - 40+ Units',
    '404': 'Retail - Apartments Over',
    '405': 'Retail - Offices Over',
    '406': 'Retail - Storage Over',
    '407': 'Forestry',
    '410': 'Motel & Tourist Cabins',
    '411': 'Hotel',
    '412': 'Nursing Home / Private Hospital',
    '413': 'Independent Living (Seniors)',
    '415': 'Mobile Home / Trailer Park',
    '416': 'Campgrounds',
    '418': 'Daycare/Private Schools',
    '417': 'Forestry With Buildings',
    '419': 'Other Commercial Housing',
    '420': 'Small Detached Retail (10,000)',
    '421': 'Supermarket',
    '422': 'Discount Stores',
    '424': 'Department Stores',
    '425': 'Neighborhood Shopping Center',
    '426': 'Community Shopping Center',
    '427': 'Regional Shopping Center',
    '429': 'Other Retail Structures',
    '430': 'Restaurant, Cafeteria Or Bar',
    '431': 'Office - Apartments Over',
    '432': 'Office - Retail Over',
    '433': 'Office - Storage Over',
    '434': 'Bars',
    '435': 'Drive-In Restaurant Or Food Service',
    '436': 'Other Commercial',
    '439': 'Other Food Services',
    '440': 'Dry Cleaning Plants / Laundries',
    '441': 'Funeral Homes',
    '442': 'Medical Clinics & Offices',
    '444': 'Banks',
    '445': 'Savings & Loans',
    '447': 'Office (1 To 2 Stories )',
    '448': 'Office Walk-Up (3 Stories Plus)',
    '449': 'Office, Elevator (3 Stories Plus)',
    '450': 'Condominium Office Building',
    '452': 'Automotive Service Station',
    '453': 'Car Wash',
    '454': 'Auto Sales & Service',
    '455': 'Garages',
    '456': 'Parking Garages / Lots',
    '460': 'Theaters',
    '461': 'Country Clubs',
    '462': 'Golf Driving Ranges - Miniature',
    '463': 'Golf Courses (Public)',
    '464': 'Bowling Alleys / Recreational Facilities',
    '465': 'Lodge Hall / Amusement Parks',
    '469': 'Low Income House Tax Credit(Commercial)',
    '470': 'Dwelling Used As Office',
    '471': 'Dwelling Used As Retail',
    '480': 'Warehouse',
    '482': 'Truck Terminal',
    '488': 'Air Rights',
    '489': 'Utility',
    '490': 'Marine Service Facility',
    '495': 'Casino',
    '498': 'Marinas',
    '499': 'Other Structures',
    '500': 'Vacant Land',
    '501': 'Vacant Land 0-9 Acres',
    '502': 'Vacant Land 10-19 Acres',
    '503': 'Vacant Land 20-29 Acres',
    '504': 'Vacant Land 30-39 Acres',
    '505': 'Vacant Land 40+ Acres',
    '507': 'Forestry',
    '508': 'Street',
    '510': 'Single Family',
    '517': 'Forestry With Buildings',
    '520': 'Two Family Dwellings',
    '530': 'Three Family Dwellings',
    '550': 'Condominiums',
    '551': 'Boataminiums',
    '552': 'Condo Or P.U.D. Garage',
    '553': 'H.O.A. Recreation Area',
    '554': 'Cabana(Condo)',
    '555': 'P.U.D. (Landominium)',
    '556': 'Common Area Or Greenbelt',
    '558': 'Condominium Storage Unit',
    '560': 'Manufactured Home',
    '561 D': 'Depreciated Manufactured Home',
    '569': 'Low Income House Tax Credit (Residential)',
    '599': 'Other Structures',
    '600': 'Federal',
    '610': 'State Of Ohio',
    '620': 'Hamilton County',
    '625': 'Land Bank Owned',
    '630': 'Townships',
    '640': 'Municipalities',
    '645': 'Metropolitan Housing Authority',
    '650': 'Board Of Education',
    '660': 'Park District',
    '670': 'Colleges / Universities / Academies',
    '680': 'Charities, Hospitals & Retirement Homes',
    '685': 'Public Worship',
    '690': 'Cemeteries & Monuments',
    '700': 'Community Urban Renewal',
    '710': 'Community Reinvestment',
    '720': 'Municipal Improvement',
    '730': 'Municipal Urban Renewal',
    '740': 'Other',
    '750': 'Enterprise Zone',
    '760': 'Port Authority',
    '800': 'Agricultural Lands',
    '810': 'Mineral Lands',
    '820': 'Industrial Lands',
    '830': 'Commercial Lands',
    '840': 'Railroads, Used In Operations',
    '850': 'Railroads, Not Used In Operations',
    '860': 'Railroads, Personal Property Used In Operations',
    '870': 'Railroads, Personal Property Not Used In Operations',
    '880': 'Utilities Other Than Railroads, Personal Property',
    '881': 'Public Utility Personal Property'
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
from hch_scraper.config.mappings.street_map import street_type_map

# School district mappings
from hch_scraper.config.mappings.district_map import school_city_map, zip_code_map





