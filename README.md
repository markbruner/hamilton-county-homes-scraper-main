# Hamilton County Homes Scraper

Scrapes public home sale and parcel data from the Hamilton County Auditor site,
enriches addresses, and loads results into Supabase. Includes a scheduled
pipeline used by GitHub Actions.

## Features
- Date-range scraping with pagination handling
- Address normalization and geocoding enrichment
- Supabase ingestion for cleaned results
- Daily backfill pipeline for scheduled runs

## Requirements
- Python 3.11+
- Firefox or Chrome with a matching WebDriver on PATH
- Supabase project credentials

## Quick Start
```bash
git clone https://github.com/<your-username>/hamilton-county-homes-scraper-main.git
cd hamilton-county-homes-scraper-main
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Environment Variables
Create a `.env` file in the repo root:
```
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
API_KEY=your_positionstack_api_key
```

## Run Locally
Interactive date range run:
```bash
python -m hch_scraper.pipelines.scrape
```

Daily range run (used by Actions):
```bash
python -m hch_scraper.pipelines.daily_scraper --min_days_ago 1 --max_days_ago 3
```

## Project Layout
```
src/hch_scraper/        Core package
  pipelines/            Entry points (scrape, daily_scraper)
  drivers/              Selenium driver setup
  io/                   Download and ingestion helpers
  services/             Geocoding integrations
  utils/                Data cleaning and helpers
scripts/                Shell helpers
```

## Notes
- Downloaded CSVs are stored under `data/raw/` by default.
- Geocoding cache is stored in `data/processed/`.

