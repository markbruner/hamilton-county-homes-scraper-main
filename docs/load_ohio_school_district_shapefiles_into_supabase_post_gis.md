# Loading Ohio School District Shapefiles into Supabase (PostGIS)

This document describes the **end-to-end, repeatable process** for loading Ohio school district boundary shapefiles into **Supabase (Postgres + PostGIS)** using `ogr2ogr`, with proper handling of credentials, schemas, geometry, and common failure modes.

This approach is designed to be:
- Reproducible
- Secure (no credentials in source control)
- Compatible with Windows (Git Bash / WSL / OSGeo4W)
- Ready for downstream spatial joins (e.g., parcels → school districts)

---

## 1. Prerequisites

### 1.1 Supabase
- A Supabase project
- Direct database access enabled
- PostGIS extension installed

```sql
create extension if not exists postgis;
```

### 1.2 Local tooling
You need **GDAL** installed with `ogr2ogr` available on PATH.

Open terminal and type 'bash' in the cmd line.

Recommended options:
- **OSGeo4W** (Windows-native)
- **WSL Ubuntu** (`sudo apt install gdal-bin`)

Verify:
```bash
ogr2ogr --version
```

---

## 2. Repository Layout

Recommended structure:

```
repo-root/
├── data/
│   └── raw/
│       └── shapefiles/
│           └── ohio-school-district-shapes/
│               ├── ohio-school-districts.shp
│               ├── ohio-school-districts.dbf
│               ├── ohio-school-districts.prj
│               └── ...
├── src/
│   └── hch_scraper/
│       └── loaders/
│           └── load_school_districts.sh
├── .env
└── .gitignore
```

---

## 3. Environment Variables (.env)

Create a `.env` file at the **repo root** (never commit this file).

```env
SUPABASE_DB_HOST=aws-0-us-east-1.pooler.supabase.com
SUPABASE_DB_PORT=6543
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=YOUR_PASSWORD
```

Add to `.gitignore`:
```
.env
```

> **Note:** The pooler endpoint is recommended to avoid IPv6 connection issues on Windows/WSL.

---

## 4. Create the Target Table (Controlled Schema)

Create the table **before** loading data to avoid type inference issues.

```sql
drop table if exists public.school_districts_raw cascade;

create table public.school_districts_raw (
  gid            bigserial primary key,

  ode_irn        text,
  lea_id         text,
  district_name  text,
  beg_grade      text,
  end_grade      text,
  taxid          text,
  pct_chg        double precision,

  starea         double precision,
  stlength       double precision,

  geom           geometry(MultiPolygon, 4326) not null,

  loaded_at      timestamptz default now()
);

create index school_districts_raw_geom_gix
  on public.school_districts_raw
  using gist (geom);

create index school_districts_raw_lea_id_ix
  on public.school_districts_raw (lea_id);
```

Why `double precision`?
- Shapefile area/length fields routinely exceed `numeric(24,15)` limits
- Floating-point precision is sufficient for GIS analytics

---

## 5. Loader Script (`load_school_districts.sh`)

Location:
```
src/hch_scraper/loaders/load_school_districts.sh
```

Script:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Load environment variables
set -a
source .env
set +a

SHAPEFILE_PATH="data/raw/shapefiles/ohio-school-district-shapes/ohio-school-districts.shp"

ogr2ogr -f "PostgreSQL" \
  "PG:host=${SUPABASE_DB_HOST} port=${SUPABASE_DB_PORT} dbname=${SUPABASE_DB_NAME} user=${SUPABASE_DB_USER} password=${SUPABASE_DB_PASSWORD} sslmode=require" \
  "${SHAPEFILE_PATH}" \
  -nln public.school_districts_raw \
  -append \
  -lco GEOMETRY_NAME=geom \
  -nlt MULTIPOLYGON \
  -t_srs EPSG:4326
```

Make executable:
```bash
chmod +x src/hch_scraper/loaders/load_school_districts.sh
```

---

## 6. Running the Loader

### 6.1 Git Bash / OSGeo4W Bash

From repo root:
```bash
./src/hch_scraper/loaders/load_school_districts.sh
```

### 6.2 WSL
```bash
cd /mnt/c/Users/markd/hamilton-county-homes-scraper-main
./src/hch_scraper/loaders/load_school_districts.sh
```

---

## 7. Validation Queries

### 7.1 Table exists
```sql
select table_schema, table_name
from information_schema.tables
where table_name = 'school_districts_raw';
```

### 7.2 Row count
```sql
select count(*) from public.school_districts_raw;
```

Expected: ~600–700 rows

### 7.3 Geometry + SRID
```sql
select
  geometrytype(geom) as geom_type,
  st_srid(geom) as srid,
  count(*)
from public.school_districts_raw
group by 1,2;
```

Expected:
```
MULTIPOLYGON | 4326
```

### 7.4 Area sanity check
```sql
select max(starea) from public.school_districts_raw;
```

---

## 8. Common Failure Modes & Fixes

### `ogr2ogr: command not found`
- GDAL not installed or not on PATH

### `Connection refused`
- Using direct DB host over IPv6
- Fix: use Supabase **transaction pooler** host

### `numeric field overflow (starea)`
- Table created with `numeric(24,15)`
- Fix: use `double precision` or recreate table

### Script fails with `not a valid identifier`
- Windows CRLF line endings
- Fix:
```bash
dos2unix .env
```

---

## 9. Next Steps (Recommended)

1. Create `school_districts_clean` with one geometry per district
2. Validate geometries (`ST_IsValid`)
3. Spatial join `parcel_polygons` → `school_districts_clean`
4. Index joins for analytics and API usage

Example clean table:
```sql
create table public.school_districts_clean as
select
  lea_id,
  district_name,
  st_union(geom)::geometry(MultiPolygon, 4326) as geom
from public.school_districts_raw
group by 1,2;
```

---

## 10. Summary

This process establishes a **production-grade GIS ingestion pipeline**:
- Secure credentials
- Controlled schema
- Reliable loading via ogr2ogr
- PostGIS-ready geometries

This forms the foundation for downstream real-estate, parcel, and school-district analytics.

