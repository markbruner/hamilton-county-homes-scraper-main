# 🏠 Hamilton County Homes Web Scraper
A webscraper for real estate data in Hamilton County Ohio
---

 **Data Collection Pipeline**  
   - Scrapes home sale and parcel data  
   - Performs geocoding to enrich addresses with latitude and longitude  
   - Cleans and patches missing or inconsistent data  



---

## 🗂️ Project Structure

hamilton-county-homes-scraper-main/ 
    ├── src/hch_scraper # Core project code 
    │ ├── config/ # Config files and selectors
    | ├── repair/ # helps patch missing data from dataset
    │ └── utils/ # Reusable helper functions ├── .env # API keys or secrets (not committed) 
    ├── driver_setup.py # Creates the driver
    ├── main.py # Main script that runs the scraper
    ├── scraper.py # Sets up 
    ├── .gitignore 
    ├── requirements.txt 
    └── README.md
---

## 🚀 Getting Started

### 1. Clone the Repo
git clone https://github.com/your-username/hamilton-county-homes-scraper-main.git
cd hamilton-county-homes-scraper-main

### 2. Create a Virtual Environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

### 3. Intall Dependencies
pip install -r requirements.txt

### 4. Set Environment Variables
Create a .env file in the root directory with your API keys (e.g., for geocoding services):
GEOCODING_API_KEY=your_key_here


🧪 How to Run
### Run the scraper:
python -m src.hch_scraper.main

### Run the patching process:
python -m src.hch_scraper.repair.patch_dataset


### 📌 Features
* Batch geocoding with error handling and retries
* Data cleaning for inconsistent addresses
* Modular and testable architecture


### 🛠️ Tech Stack
* Python 3.11+
*  Pandas
* Selenium
* OpenStreetMap / PositionStack (for geocoding)

### 📬 Contact
Created by Mark Bruner – feel free to reach out or contribute.
