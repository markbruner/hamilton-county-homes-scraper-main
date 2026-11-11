#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  ""|--dry-run) ;;
  *) echo "Usage: $0 [--dry-run]" >&2; exit 2 ;;
esac

url="https://services.arcgis.com/JyZag7oO4NteHGiq/arcgis/rest/services/Open_Data_Feature_Collection/FeatureServer/24/query"
out="data/raw/cagis_zip_codes_layer.geojson"
sql="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/refresh_zip_codes.sql"
work="$(mktemp -d)"
trap 'rm -f -- "$work/source.geojson" "$work/count.json" "$work/zip.csv"; rmdir -- "$work"' EXIT

curl -fsSG --max-time 60 "$url" --data-urlencode "where=1=1" \
  --data-urlencode "returnCountOnly=true" --data-urlencode "f=json" -o "$work/count.json"
curl -fsSG --max-time 60 "$url" --data-urlencode "where=1=1" \
  --data-urlencode "outFields=*" --data-urlencode "returnGeometry=true" \
  --data-urlencode "outSR=4326" --data-urlencode "f=geojson" -o "$work/source.geojson"

python - "$work" <<'PY'
import csv
import json
import sys
from pathlib import Path

work = Path(sys.argv[1])
count = json.loads((work / "count.json").read_bytes()).get("count")
source = json.loads((work / "source.geojson").read_bytes())
features = source.get("features", [])
if (source.get("type") != "FeatureCollection" or source.get("exceededTransferLimit")
        or not features or len(features) != count):
    raise SystemExit("ZIP layer returned an incomplete or invalid feature collection.")

fields = (
    "OBJECTID", "ZIPCODE", "USPSCITY", "USPSCITYAL", "ACRES", "PERIMETER",
    "MILES_SQ", "GLOBALID", "SHAPE__Area", "SHAPE__Length",
)
seen = set()
with (work / "zip.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream)
    for feature in features:
        props = feature["properties"]
        zipcode = props["ZIPCODE"]
        geometry = feature.get("geometry") or {}
        if type(zipcode) is not int or not 10000 <= zipcode <= 99999 or zipcode in seen:
            raise SystemExit("ZIP layer contains a missing, invalid, or duplicate ZIP code.")
        if geometry.get("type") not in {"Polygon", "MultiPolygon"} or not geometry.get("coordinates"):
            raise SystemExit("ZIP layer contains a missing or unsupported polygon.")
        seen.add(zipcode)
        writer.writerow([*(props[field] for field in fields), json.dumps(geometry)])
print(f"Validated {len(seen)} ZIP code features.")
PY

mkdir -p "$(dirname "$out")"
cp -- "$work/source.geojson" "$out"
if [ "${1:-}" = "--dry-run" ]; then
  exit 0
fi

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

(
  cd "$work"
  PGHOST="${SUPABASE_DB_HOST:?}" PGPORT="${SUPABASE_DB_PORT:?}" \
    PGDATABASE="${SUPABASE_DB_NAME:?}" PGUSER="${SUPABASE_DB_USER:?}" \
    PGPASSWORD="${SUPABASE_DB_PASSWORD:?}" PGSSLMODE=require PGCLIENTENCODING=UTF8 \
    psql --no-psqlrc --no-password --set=ON_ERROR_STOP=1 --file="$sql"
)
echo "ZIP code refresh complete."
