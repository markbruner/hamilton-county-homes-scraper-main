# ZIP Code Loader Runbook (End-to-End)

This runbook documents the full process for:
- building a loader shell script (`.sh`)
- wrapping it with a Windows batch runner (`.bat`) for OSGeo4W
- scheduling it in Windows Task Scheduler

Use this as a repeatable pattern for other data-loading applications.

## 1. Architecture Overview

Execution flow:
1. Task Scheduler starts `run_load_zip_codes.bat`
2. `run_load_zip_codes.bat` boots OSGeo4W environment and runs Bash
3. Bash runs `src/hch_scraper/loaders/load_zip_codes.sh`
4. `load_zip_codes.sh` downloads GeoJSON and loads PostgreSQL table
5. Logs are written to `logs/load_zip_codes.log`

Current files:
- `src/hch_scraper/loaders/load_zip_codes.sh`
- `src/hch_scraper/loaders/run_load_zip_codes.bat`

## 2. Prerequisites

Required:
- Windows machine
- OSGeo4W (or QGIS with OSGeo tools)
- `python` and the PostgreSQL client `psql` available on PATH
- `bash` and `curl` available in OSGeo environment
- PostgreSQL/Supabase connection values in project `.env`

Project assumptions:
- Repo root: `C:\Users\markd\hamilton-county-homes-scraper-main`
- `.env` exists at repo root and includes:
  - `SUPABASE_DB_HOST`
  - `SUPABASE_DB_PORT`
  - `SUPABASE_DB_NAME`
  - `SUPABASE_DB_USER`
  - `SUPABASE_DB_PASSWORD`

## 3. Loader Script (`load_zip_codes.sh`)

Purpose:
- Download current zip-code layer GeoJSON from ArcGIS
- Refresh the rows in `bronze.cagis_zip_codes_layer_raw` while preserving its dependent views

Location:
- `src/hch_scraper/loaders/load_zip_codes.sh`

Current behavior:
1. Downloads the public ZIP layer and compares its feature count with the source count.
2. Checks ZIP code uniqueness and polygon presence, then saves validated GeoJSON.
3. In a live run, stages the data in a temporary PostgreSQL table and validates the geometries.
4. Updates existing ZIP codes in place and inserts new ZIP codes in one transaction.

Run `bash src/hch_scraper/loaders/load_zip_codes.sh --dry-run` to validate the public source without connecting to PostgreSQL. Manual GitHub Actions runs default to this mode.

Key implementation details:
- `set -euo pipefail` fails fast on any command error
- `curl -fsS` fails on HTTP errors
- `mkdir -p` ensures output directory exists
- The refresh stops if existing ZIP codes are duplicated or missing from the source. A failed transaction rolls back its row changes.

## 4. OSGeo Wrapper (`run_load_zip_codes.bat`)

Purpose:
- Run the Bash loader from Windows/Task Scheduler in a known OSGeo environment

Location:
- `src/hch_scraper/loaders/run_load_zip_codes.bat`

Current behavior:
1. Sets repo and log paths
2. Detects OSGeo bootstrap script, preferring:
   - `C:\Users\markd\AppData\Local\Programs\OSGeo4W\OSGeo4W.bat`
   - fallback `...bin\o4w_env.bat`
3. Creates `logs` directory if needed
4. Runs loader script through OSGeo shell
5. Appends output to `logs\load_zip_codes.log`
6. Returns the child process exit code (`exit /b %errorlevel%`)

Exit code meaning:
- `0` = success
- non-zero = failure (check log file)

## 5. Manual Test Procedure

From repo root PowerShell:

```powershell
.\src\hch_scraper\loaders\run_load_zip_codes.bat
```

Check result:
1. Exit code should be `0`
2. Log should show completion in `logs\load_zip_codes.log`
3. Validate in database:

```sql
select count(*) from bronze.cagis_zip_codes_layer_raw;
```

## 6. Task Scheduler Setup (Quarterly)

Create task:
1. Open Task Scheduler
2. `Create Task...` (recommended over Basic Task)
3. Name: `HCH - Load ZIP Codes`
4. Security options:
   - Run whether user is logged on or not
   - Run with highest privileges (optional, usually safe)

Trigger (quarterly):
1. Add new trigger
2. Begin task: On a schedule
3. Monthly
4. Select months: `Jan, Apr, Jul, Oct`
5. Choose day/time (example: day 1 at 2:00 AM)

Action:
1. Start a program
2. Program/script:
   - `C:\Users\markd\hamilton-county-homes-scraper-main\src\hch_scraper\loaders\run_load_zip_codes.bat`
3. Start in:
   - `C:\Users\markd\hamilton-county-homes-scraper-main`

Settings:
- Enable "Run task as soon as possible after a scheduled start is missed"
- Enable retry if desired (example: retry every 30 minutes, up to 3 times)

## 7. Troubleshooting Guide

### Error: `OSGeo4W.bat not found`
- Fix bootstrap path in `run_load_zip_codes.bat`
- To locate tools, use the working OSGeo shell and run:
  - `where python`
  - `where psql`

### Error: `Destination contains unmatched or duplicate ZIP codes`
- Compare destination ZIP codes with the validated GeoJSON before making any data corrections.

### Batch returns non-zero exit code
1. Open `logs\load_zip_codes.log`
2. Read the last errors
3. Fix command/path/env issue indicated in the log

### Connection/auth errors
- Verify `.env` DB values
- Confirm network/firewall access to DB host
- Confirm the database user can create temporary tables and select, update, and insert ZIP rows. Inserting new ZIP codes also requires access to the existing ID default and its sequence, if used.

## 8. Reusable Template for Another Loader

Copy this pattern:
1. Create `<new_loader>.sh`
2. Use:
   - `set -euo pipefail`
   - `.env` loading
   - download step (`curl`)
   - optional file validation
   - explicit table drop
   - `ogr2ogr` load to target schema/table
3. Create `run_<new_loader>.bat`
4. Reuse OSGeo bootstrap detection and log handling
5. Add Task Scheduler task with desired cadence

Recommended naming:
- Shell loader: `src/hch_scraper/loaders/load_<dataset>.sh`
- Batch wrapper: `src/hch_scraper/loaders/run_load_<dataset>.bat`
- Log file: `logs/load_<dataset>.log`

## 9. Operational Checklist

Before go-live:
1. Manual run succeeds (`exit /b 0`)
2. Target table row count is non-zero
3. Log file captures expected success line
4. Scheduled task run is tested once with "Run" button
5. Next run time is visible and correct in Task Scheduler

After each scheduled run:
1. Confirm task status is successful
2. Spot-check `logs/load_zip_codes.log`
3. Spot-check row count in target table
