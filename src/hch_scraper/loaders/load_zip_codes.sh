#!/usr/bin/env bash
set -euo pipefail

set -a
source .env
set +a

SHAPEFILE_PATH="data/raw/downloads/tl_2023_us_zcta520/tl_2023_us_zcta520.shp"

ogr2ogr -f "PostgreSQL" \
  "PG:host=${SUPABASE_DB_HOST} port=${SUPABASE_DB_PORT} dbname=${SUPABASE_DB_NAME} user=${SUPABASE_DB_USER} password=${SUPABASE_DB_PASSWORD} sslmode=require" \
  "${SHAPEFILE_PATH}" \
  -nln public.zip_areas_raw \
  -append \
  -lco GEOMETRY_NAME=geom \
  -nlt MULTIPOLYGON \
  -t_srs EPSG:4326

  echo "ZIP CODE LOAD COMPLETE at $(date)"