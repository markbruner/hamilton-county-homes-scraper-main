#!/usr/bin/env bash
set -euo pipefail

set -a
source .env
set +a

QUERY_URL="https://services.arcgis.com/JyZag7oO4NteHGiq/arcgis/rest/services/OpenData/FeatureServer/10/query"
OUT_DIR="geojson"
STATE_DIR="data/state"
PAGE_FILE="${OUT_DIR}/cagis_parcels_layer_incremental_page.geojson"
STATE_FILE="${STATE_DIR}/cagis_parcels_layer_raw.last_objectid"
PAGE_SIZE=2000
ID_FIELD="OBJECTID"

mkdir -p "$OUT_DIR" "$STATE_DIR"

PG_CONN="PG:host=${SUPABASE_DB_HOST} port=${SUPABASE_DB_PORT} dbname=${SUPABASE_DB_NAME} user=${SUPABASE_DB_USER} password=${SUPABASE_DB_PASSWORD} sslmode=require"
TARGET_FULL_TABLE="bronze.cagis_parcels_layer_raw"

LAST_OBJECTID=0
if [ -f "$STATE_FILE" ]; then
  LAST_OBJECTID="$(tr -d '[:space:]' < "$STATE_FILE")"
  if [ -z "$LAST_OBJECTID" ]; then
    LAST_OBJECTID=0
  fi
fi

OFFSET=0
PAGE_NUM=1
TABLE_EXISTS=0
MAX_SEEN="$LAST_OBJECTID"
ANY_LOADED=0

if ogrinfo "$PG_CONN" "$TARGET_FULL_TABLE" >/dev/null 2>&1; then
  TABLE_EXISTS=1
fi

while true; do
  HTTP_CODE="$(
    curl -sS -G "$QUERY_URL" \
      --data-urlencode "where=${ID_FIELD} > ${LAST_OBJECTID}" \
      --data-urlencode "outFields=*" \
      --data-urlencode "returnGeometry=true" \
      --data-urlencode "orderByFields=${ID_FIELD} ASC" \
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

  if grep -Eq '"features"[[:space:]]*:[[:space:]]*\[[[:space:]]*\]' "$PAGE_FILE"; then
    break
  fi

  if ! grep -q '"features"' "$PAGE_FILE"; then
    echo "Downloaded file does not look like valid GeoJSON: $PAGE_FILE" >&2
    exit 1
  fi

  if [ "$TABLE_EXISTS" -eq 0 ]; then
    ogr2ogr -f "PostgreSQL" \
      "$PG_CONN" \
      "$PAGE_FILE" \
      -nln cagis_parcels_layer_raw \
      -lco SCHEMA=bronze \
      -lco GEOMETRY_NAME=geom \
      -nlt PROMOTE_TO_MULTI \
      -t_srs EPSG:4326
    TABLE_EXISTS=1
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

  ANY_LOADED=1
  echo "Loaded incremental page $PAGE_NUM (offset $OFFSET)"

  PAGE_MAX="$(
    python -c "import json,sys; d=json.load(open(sys.argv[1], encoding='utf-8')); vals=[]; 
for f in d.get('features',[]): 
    p=f.get('properties') or {}; 
    v=p.get(sys.argv[2]); 
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()): 
        vals.append(int(v)); 
print(max(vals) if vals else '')" "$PAGE_FILE" "$ID_FIELD"
  )"

  if [ -n "$PAGE_MAX" ]; then
    MAX_SEEN="$PAGE_MAX"
  fi

  if ! grep -Eq '"exceededTransferLimit"[[:space:]]*:[[:space:]]*true' "$PAGE_FILE"; then
    break
  fi

  OFFSET=$((OFFSET + PAGE_SIZE))
  PAGE_NUM=$((PAGE_NUM + 1))
done

if [ "$ANY_LOADED" -eq 0 ]; then
  echo "No incremental parcel changes found after OBJECTID ${LAST_OBJECTID}"
  exit 0
fi

echo "$MAX_SEEN" > "$STATE_FILE"
echo "INCREMENTAL PARCEL LOAD COMPLETE: ${TARGET_FULL_TABLE} at $(date) (state=${MAX_SEEN})"
