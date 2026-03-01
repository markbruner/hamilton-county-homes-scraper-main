#!/usr/bin/env bash
set -euo pipefail

set -a
source .env
set +a

SHAPEFILE_PATH="data/raw/shapefiles/ohio-school-district-shapes/ohio-school-districts.shp"

ogr2ogr -f "PostgreSQL" \
  "PG:host=${SUPABASE_DB_HOST} port=${SUPABASE_DB_PORT} dbname=${SUPABASE_DB_NAME} user=${SUPABASE_DB_USER} password=${SUPABASE_DB_PASSWORD} sslmode=require" \
  "${SHAPEFILE_PATH}" \
  -nln public.school_districts_raw \
  -overwrite \
  -lco GEOMETRY_NAME=geom \
  -nlt MULTIPOLYGON \
  -t_srs EPSG:4326

    echo "SCHOOL DISTRICT LOAD COMPLETE at $(date)"