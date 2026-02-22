#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

QUERY_URL="https://services.arcgis.com/JyZag7oO4NteHGiq/arcgis/rest/services/OpenData/FeatureServer/26/query"
OUT="data/raw/cagis_zip_codes_layer.geojson"

mkdir -p "$(dirname "$OUT")"

curl -fsS -G "$QUERY_URL" \
  --data-urlencode "where=1=1" \
  --data-urlencode "outFields=*" \
  --data-urlencode "returnGeometry=true" \
  --data-urlencode "outSR=4326" \
  --data-urlencode "f=geojson" \
  -o "$OUT"

if ! grep -q '"features"' "$OUT"; then
  echo "Downloaded file does not look like valid GeoJSON: $OUT" >&2
  exit 1
fi

PG_CONN="PG:host=${SUPABASE_DB_HOST} port=${SUPABASE_DB_PORT} dbname=${SUPABASE_DB_NAME} user=${SUPABASE_DB_USER} password=${SUPABASE_DB_PASSWORD} sslmode=require"

ogrinfo "$PG_CONN" -q -sql "DROP TABLE IF EXISTS bronze.cagis_zip_codes_layer_raw"

ogr2ogr -f "PostgreSQL" \
  "$PG_CONN" \
  "$OUT" \
  -nln cagis_zip_codes_layer_raw \
  -lco SCHEMA=bronze \
  -lco GEOMETRY_NAME=geom \
  -nlt PROMOTE_TO_MULTI \
  -t_srs EPSG:4326

echo "ZIP CODE LOAD COMPLETE: bronze.cagis_zip_codes_layer_raw at $(date)"