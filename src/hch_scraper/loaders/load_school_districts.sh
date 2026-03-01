#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

SHAPEFILE_PATH="data/raw/shapefiles/ohio-school-district-shapes/ohio-school-districts.shp"

PG_CONN="PG:host=${SUPABASE_DB_HOST} port=${SUPABASE_DB_PORT} dbname=${SUPABASE_DB_NAME} user=${SUPABASE_DB_USER} password=${SUPABASE_DB_PASSWORD} sslmode=require"

ogrinfo "$PG_CONN" -q -sql "DROP TABLE IF EXISTS bronze.school_districts_raw"

ogr2ogr -f "PostgreSQL" \
  "$PG_CONN" \
  "${SHAPEFILE_PATH}" \
  -nln school_districts_raw \
  -lco SCHEMA=bronze \
  -lco GEOMETRY_NAME=geom \
  -nlt MULTIPOLYGON \
  -t_srs EPSG:4326

    echo "SCHOOL DISTRICT LOAD COMPLETE at $(date)"