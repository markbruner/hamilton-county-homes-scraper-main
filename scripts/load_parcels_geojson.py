import json
import os
import psycopg2
from psycopg2 import Error as PgError

# ---- update these from your Supabase DB settings ----
DB_HOST = "aws-0-us-east-2.pooler.supabase.com"
DB_PORT = 6543
DB_NAME = "postgres"
DB_USER = "postgres.zutmsvpkqvmnnpmrsbfe"
DB_PASSWORD = "BjhfE750814!"  # consider using env var in real code
# -----------------------------------------------------


def load_street_centerlines_raw(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data["features"]
    print(f"Loaded {len(features)} centerline features from {path}")

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require",
    )
    conn.autocommit = True

    sql = """
        INSERT INTO street_centerlines_raw (objectid, properties, geom)
        VALUES (
            %s,
            %s::jsonb,
            ST_SetSRID(
                ST_Force2D(
                    ST_GeomFromGeoJSON(%s)
                ),
                4326
            )
        )
        ON CONFLICT (objectid) DO UPDATE
        SET
            properties = EXCLUDED.properties,
            geom       = EXCLUDED.geom;
    """

    inserted = 0
    skipped = 0

    try:
        with conn.cursor() as cur:
            for i, feat in enumerate(features, start=1):
                props = feat.get("properties") or {}
                geom_obj = feat.get("geometry")

                # skip features with no geometry
                if not geom_obj:
                    skipped += 1
                    print(f"Skipping feature with no geometry (index {i})")
                    continue

                objectid = props.get("OBJECTID")
                if objectid is None:
                    skipped += 1
                    print(f"Skipping feature with no OBJECTID (index {i})")
                    continue

                try:
                    objectid_int = int(objectid)
                except (TypeError, ValueError):
                    skipped += 1
                    print(f"Skipping feature with non-integer OBJECTID={objectid!r}")
                    continue

                try:
                    geom_json = json.dumps(geom_obj)
                except (TypeError, ValueError) as e:
                    skipped += 1
                    print(f"Skipping OBJECTID={objectid_int} due to bad geometry JSON: {e}")
                    continue

                try:
                    cur.execute(
                        sql,
                        (
                            objectid_int,
                            json.dumps(props),
                            geom_json,
                        ),
                    )
                    inserted += 1
                except PgError as e:
                    skipped += 1
                    print(f"Skipping OBJECTID={objectid_int} due to PostGIS error: {e.pgerror}")

                if i % 1000 == 0:
                    print(f"Processed {i} features... inserted={inserted}, skipped={skipped}")

        conn.commit()
        print(f"Done. Inserted={inserted}, skipped={skipped}")

    except Exception as e:
        conn.rollback()
        print("Error during centerline insert, rolled back:", e)
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    # adjust path if needed
    geojson_path = r"C:\Users\markd\hamilton-county-homes-scraper-main\data\raw\downloads\Hamilton_County_Parcel_Polygons\parcels.geojson"
    load_street_centerlines_raw(geojson_path)
