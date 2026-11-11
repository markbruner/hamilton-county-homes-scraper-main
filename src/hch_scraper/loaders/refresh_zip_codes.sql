BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '2min';
SET LOCAL search_path = pg_catalog, public, extensions;

CREATE TEMP TABLE zip_source (
    objectid integer NOT NULL UNIQUE,
    zipcode integer PRIMARY KEY,
    uspscity text,
    uspscityal text,
    acres text,
    perimeter text,
    miles_sq double precision,
    globalid text,
    shape__area double precision,
    shape__length double precision,
    geojson text NOT NULL
) ON COMMIT DROP;

\copy zip_source FROM 'zip.csv' WITH (FORMAT csv)

ALTER TABLE zip_source ADD COLUMN geom geometry(Geometry,4326);
UPDATE zip_source SET geom = ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(geojson), 4326));

LOCK TABLE bronze.cagis_zip_codes_layer_raw IN SHARE ROW EXCLUSIVE MODE;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM zip_source)
       OR EXISTS (SELECT 1 FROM zip_source WHERE geom IS NULL OR ST_IsEmpty(geom) OR NOT ST_IsValid(geom)) THEN
        RAISE EXCEPTION 'ZIP source must contain valid, nonempty polygons';
    END IF;
    IF EXISTS (
        SELECT 1 FROM bronze.cagis_zip_codes_layer_raw AS target
        LEFT JOIN zip_source AS source USING (zipcode)
        WHERE source.zipcode IS NULL
    ) OR EXISTS (
        SELECT 1 FROM bronze.cagis_zip_codes_layer_raw GROUP BY zipcode HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Destination contains unmatched or duplicate ZIP codes; review before refreshing';
    END IF;
END;
$$;

UPDATE bronze.cagis_zip_codes_layer_raw AS target
SET objectid = source.objectid, uspscity = source.uspscity, uspscityal = source.uspscityal,
    acres = source.acres, perimeter = source.perimeter, miles_sq = source.miles_sq,
    globalid = source.globalid, shape__area = source.shape__area,
    shape__length = source.shape__length, geom = source.geom
FROM zip_source AS source
WHERE target.zipcode = source.zipcode;

INSERT INTO bronze.cagis_zip_codes_layer_raw (
    objectid, zipcode, uspscity, uspscityal, acres, perimeter, miles_sq,
    globalid, shape__area, shape__length, geom
)
SELECT objectid, zipcode, uspscity, uspscityal, acres, perimeter, miles_sq,
       globalid, shape__area, shape__length, geom
FROM zip_source AS source
WHERE NOT EXISTS (
    SELECT 1 FROM bronze.cagis_zip_codes_layer_raw AS target WHERE target.zipcode = source.zipcode
);

COMMIT;
