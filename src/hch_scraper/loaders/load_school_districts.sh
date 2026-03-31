#!/usr/bin/env bash
set -e

# Load env vars
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
else
  echo ".env file not found"
  exit 1
fi

SHAPEFILE_PATH="data/raw/shapefiles/ohio-school-district-shapes/ohio-school-districts.shp"

ogr2ogr -f "PostgreSQL" \
  "PG:host=${SUPABASE_DB_HOST} port=${SUPABASE_DB_PORT} dbname=${SUPABASE_DB_NAME} user=${SUPABASE_DB_USER} password=${SUPABASE_DB_PASSWORD} sslmode=require" \
  "${SHAPEFILE_PATH}" \
  -nln public.school_districts_raw \
  -lco SCHEMA=public \
  -lco GEOMETRY_NAME=geom \
  -lco FID=gid \
  -nlt MULTIPOLYGON \
  -t_srs EPSG:4326 \
  -overwrite