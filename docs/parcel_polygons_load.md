# Hamilton County Parcel Polygons → Supabase/Postgres

This document describes how the **Hamilton_County_Parcel_Polygons** dataset is:

1. Loaded into a raw landing table (`parcel_polygons_raw`)
2. Transformed into a curated table (`parcel_polygons`) with enforced uniqueness and web-ready geometry

---

## Prerequisites

- PostgreSQL with **PostGIS** enabled
- Source geometry in **EPSG:3735**
- Target geometry in **EPSG:4326** (web mapping)

```sql
create extension if not exists postgis;
```

---

## 1. Raw Table: `parcel_polygons_raw`

The raw table stores the parcel polygon layer *as-ingested*, preserving all attributes in JSONB.

```sql
create table if not exists public.parcel_polygons_raw (
  id bigserial primary key,
  source_file text,
  loaded_at timestamptz default now(),
  properties jsonb not null,
  geom geometry(MultiPolygon, 3735) not null
);
```
# Create indexes

```sql
create index if not exists parcel_polygons_raw_geom_gix
  on public.parcel_polygons_raw using gist (geom);

create index if not exists parcel_polygons_raw_properties_gin
  on public.parcel_polygons_raw using gin (properties);
```

### Purpose
- Preserve original attribute structure
- Allow reprocessing without re-ingestion
- Avoid schema churn from upstream changes

---

## 2. Curated Table: `parcel_polygons`

This table extracts key identifiers from `properties` and standardizes geometry.

```sql
create table if not exists public.parcel_polygons (
  id bigserial primary key,
  parcelid   text,
  audpclid   text,
  proptyid   text,
  geom       geometry(MultiPolygon, 4326) not null
);
```
# Create indexes

```sql
create index if not exists parcel_polygons_geom_gix
  on public.parcel_polygons
  using gist (geom);

create unique index if not exists parcel_polygons_uq
  on public.parcel_polygons (proptyid, parcelid);
```
# Insert data into parcel_polygons

```sql
insert into public.parcel_polygons (parcelid, audpclid, proptyid, geom)
select distinct on (properties->>'PROPTYID', properties->>'PARCELID')
  properties ->> 'PARCELID' as parcelid,
  properties ->> 'AUDPCLID' as audpclid,
  properties ->> 'PROPTYID' as proptyid,
  st_multi(st_transform(st_setsrid(geom, 3735), 4326)) as geom
from public.parcel_polygons_raw
on conflict (proptyid, parcelid) do nothing;
```
# Create longitude and latitude columns

```sql
alter table public.parcel_polygons
  add column if not exists longitude double precision
    generated always as (st_x(st_pointonsurface(geom))) stored,
  add column if not exists latitude double precision
    generated always as (st_y(st_pointonsurface(geom))) stored;
```

---

## 3. Uniqueness Enforcement

Hamilton County parcel geometry can repeat in the raw data.  
We define a **natural key** using:

- `proptyid`
- `parcelid`

---

### One-time cleanup (if duplicates exist)

```sql
delete from public.parcel_polygons p
using public.parcel_polygons d
where p.proptyid = d.proptyid
  and p.parcelid = d.parcelid
  and p.id > d.id;
```
---

## 6. Validation Queries

### Duplicate check

```sql
select
  proptyid,
  parcelid,
  count(*) as n
from public.parcel_polygons
group by proptyid, parcelid
having count(*) > 1;
```

### SRID check

```sql
select st_srid(geom) as srid, count(*)
from public.parcel_polygons
group by st_srid(geom);
```

Expected result: SRID = 4326 only.

---

## Summary

- `parcel_polygons_raw` stores the source data exactly as received
- `parcel_polygons` is the authoritative GIS table for applications
- Uniqueness is enforced at the database level
- Geometry is standardized for web mapping and analytics

