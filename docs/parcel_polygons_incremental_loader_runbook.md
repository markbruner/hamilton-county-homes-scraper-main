# Parcel Polygons Incremental Loader Runbook

This document explains the full process for running and scheduling incremental parcel polygon loads.

## 1. Files Involved

- Loader script: `src/hch_scraper/loaders/load_parcel_polygons_incremental.sh`
- Windows runner: `src/hch_scraper/loaders/run_load_parcel_polygons_incremental.bat`
- Log file: `logs/load_parcel_polygons_incremental.log`
- Incremental state file: `data/state/cagis_parcels_layer_raw.last_objectid`

## 2. What the Incremental Loader Does

`load_parcel_polygons_incremental.sh`:
1. Loads DB credentials from `.env`
2. Reads last processed `OBJECTID` from the state file (defaults to `0`)
3. Calls ArcGIS REST API with:
   - `where=OBJECTID > <last_objectid>`
   - pagination (`resultOffset`, `resultRecordCount=2000`)
4. Appends returned pages to `bronze.cagis_parcels_layer_raw`
5. Tracks the max `OBJECTID` seen
6. Writes new max `OBJECTID` back to state file on success

Result: next run only loads rows newer than the last successful run.

## 3. Prerequisites

- OSGeo4W/QGIS environment with `ogr2ogr`, `ogrinfo`, `bash`, `curl`
- Working `.env` at repo root with:
  - `SUPABASE_DB_HOST`
  - `SUPABASE_DB_PORT`
  - `SUPABASE_DB_NAME`
  - `SUPABASE_DB_USER`
  - `SUPABASE_DB_PASSWORD`
- Existing target table or permissions to create:
  - `bronze.cagis_parcels_layer_raw`

## 4. Manual Run

From repo root PowerShell:

```powershell
.\src\hch_scraper\loaders\run_load_parcel_polygons_incremental.bat
```

Check:
1. Exit code is `0`
2. `logs/load_parcel_polygons_incremental.log` shows page loads and completion
3. State file updated:
   - `data/state/cagis_parcels_layer_raw.last_objectid`

## 5. Task Scheduler Setup

Create a task:
1. Open Task Scheduler -> `Create Task...`
2. Name: `HCH - Incremental Parcel Polygons`
3. Trigger: choose your cadence (daily recommended for incremental jobs)
4. Action:
   - Program/script:  
     `C:\Users\markd\hamilton-county-homes-scraper-main\src\hch_scraper\loaders\run_load_parcel_polygons_incremental.bat`
   - Start in:  
     `C:\Users\markd\hamilton-county-homes-scraper-main`
5. Settings:
   - Enable `Run task as soon as possible after a scheduled start is missed`
   - Optional: enable retry on failure

## 6. Reset / Backfill Options

To re-run from scratch incrementally:
1. Set state file to `0`:
   - `data/state/cagis_parcels_layer_raw.last_objectid`
2. Run the incremental batch file again

To do a full refresh:
1. Use full loader: `src/hch_scraper/loaders/load_parcel_polygons.sh`
2. Then resume incremental runs

## 7. Troubleshooting

### `Could not find OSGeo bootstrap script`
- Update bootstrap path in:
  - `src/hch_scraper/loaders/run_load_parcel_polygons_incremental.bat`

### `curl` HTTP 400/500
- Check response preview in log
- Validate layer URL and query params

### Only a subset of records loaded
- Confirm multiple `Loaded incremental page ...` lines in log
- Validate API pagination and `exceededTransferLimit` behavior

### No changes loaded
- Normal if no new `OBJECTID` values exist beyond state

## 8. Important Limitation

Current incremental logic uses `OBJECTID > last_objectid`, which captures new rows only.
It does not detect updates to older rows with lower `OBJECTID`.

If you need true change capture (inserts + updates), switch to an edit timestamp field (for example `EditDate`) and use timestamp-based filtering plus upsert logic.

## 9. Reuse Pattern for Other Layers

For another layer:
1. Copy the incremental `.sh` script
2. Change:
   - `QUERY_URL`
   - target table name
   - state file name
   - ID/timestamp field
3. Copy the `.bat` runner and point it to the new script
4. Create a new Task Scheduler task
