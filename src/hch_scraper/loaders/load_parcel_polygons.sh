#!/usr/bin/env bash
set -euo pipefail

set -a
source .env
set +a

QUERY_URL="https://services.arcgis.com/JyZag7oO4NteHGiq/arcgis/rest/services/OpenData/FeatureServer/10/query"
OUT_DIR="data/raw"
PAGE_FILE="${OUT_DIR}/cagis_parcels_layer_page.geojson"
PAGE_SIZE=2000

mkdir -p "$OUT_DIR"

PG_CONN="PG:host=${SUPABASE_DB_HOST} port=${SUPABASE_DB_PORT} dbname=${SUPABASE_DB_NAME} user=${SUPABASE_DB_USER} password=${SUPABASE_DB_PASSWORD} sslmode=require"

# Some GDAL builds are inconsistent with -overwrite for PostgreSQL layers.
# Drop first so the create step is deterministic.
ogrinfo "$PG_CONN" -q -sql "DROP TABLE IF EXISTS bronze.cagis_parcels_layer_raw CASCADE"

OFFSET=0
PAGE_NUM=1

while true; do
  HTTP_CODE="$(
    curl -sS -G "$QUERY_URL" \
      --data-urlencode "where=1=1" \
      --data-urlencode "outFields=*" \
      --data-urlencode "returnGeometry=true" \
      --data-urlencode "orderByFields=OBJECTID ASC" \
      --data-urlencode "outSR=4326" \
      --data-urlencode "f=geojson" \
      --data-urlencode "resultOffset=${OFFSET}" \
      --data-urlencode "resultRecordCount=${PAGE_SIZE}" \
      -o "$PAGE_FILE" \
      -w "%{http_code}"
  )"

  if [ "$HTTP_CODE" -ge 400 ]; then
    echo "ArcGIS request failed with HTTP $HTTP_CODE on page $PAGE_NUM (offset $OFFSET)" >&2
    echo "Response preview:" >&2
    head -c 500 "$PAGE_FILE" >&2 || true
    echo >&2
    exit 1
  fi

  if ! grep -q '"features"' "$PAGE_FILE"; then
    echo "Downloaded file does not look like valid GeoJSON: $PAGE_FILE" >&2
    exit 1
  fi

  if grep -Eq '"features"[[:space:]]*:[[:space:]]*\[[[:space:]]*\]' "$PAGE_FILE"; then
    break
  fi

  if [ "$PAGE_NUM" -eq 1 ]; then
    ogr2ogr -f "PostgreSQL" \
      "$PG_CONN" \
      "$PAGE_FILE" \
      -update \
      -overwrite \
      -nln bronze.cagis_parcels_layer_raw \
      -lco OVERWRITE=YES \
      -lco GEOMETRY_NAME=geom \
      -nlt PROMOTE_TO_MULTI \
      -t_srs EPSG:4326
  else
    ogr2ogr -f "PostgreSQL" \
      "$PG_CONN" \
      "$PAGE_FILE" \
      -update \
      -append \
      -nln bronze.cagis_parcels_layer_raw \
      -nlt PROMOTE_TO_MULTI \
      -t_srs EPSG:4326
  fi

  echo "Loaded page $PAGE_NUM (offset $OFFSET)"

  if ! grep -Eq '"exceededTransferLimit"[[:space:]]*:[[:space:]]*true' "$PAGE_FILE"; then
    break
  fi

  OFFSET=$((OFFSET + PAGE_SIZE))
  PAGE_NUM=$((PAGE_NUM + 1))
done

echo "PARCEL LOAD COMPLETE: bronze.cagis_parcels_layer_raw at $(date)"
