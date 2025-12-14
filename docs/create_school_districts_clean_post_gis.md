# Creating `school_districts_clean` (PostGIS)

This document describes the **repeatable, production-safe process** for transforming raw Ohio school district shapefile data into a clean, analytics-ready table: `school_districts_clean`.

The goal of this table is:
- **One row per school district**
- **Stable geometry** (MultiPolygon, EPSG:4326)
- **Safe for spatial joins** (parcels, sales points)
- **Safe to expose via views / dashboards**

---

## 1. Purpose & Design

The raw shapefile load (`school_districts_raw`) may contain:
- Multiple rows per district
- Multipart geometries
- Redundant attributes

`school_districts_clean` resolves these issues by:
- Grouping records by district identifiers
- Unioning geometries into a single shape per district
- Enforcing a consistent geometry type

This table is the **authoritative boundary layer** for all downstream joins.

---

## 2. Prerequisites

- `school_districts_raw` exists and is populated
- PostGIS extension enabled

```sql
create extension if not exists postgis;
```

Confirm raw geometry health:
```sql
select geometrytype(geom), st_srid(geom), count(*)
from public.school_districts_raw
group by 1,2;
```

Expected:
```
MULTIPOLYGON | 4326
```

---

## 3. Common Pitfall (Why This Step Matters)

Even if **all raw geometries are MULTIPOLYGON**, this operation:

```sql
st_union(geom)
```

may legally return:
- `POLYGON`
- `MULTIPOLYGON`
- `GEOMETRYCOLLECTION`

PostGIS will throw this error if the result is not coerced:

```
Geometry type (Polygon) does not match column type (MultiPolygon)
```

To avoid this, we must explicitly:
1. Extract polygon components
2. Force multipolygon output

---

## 4. Create `school_districts_clean`

This version is **robust** and safe against all geometry edge cases.

```sql
drop table if exists public.school_districts_clean;

create table public.school_districts_clean as
select
  coalesce(nullif(lea_id,''), nullif(ode_irn,'')) as district_key,
  lea_id,
  ode_irn,
  max(district_name) as district_name,
  st_multi(
    st_collectionextract(
      st_union(geom),
      3  -- 3 = Polygon geometries
    )
  )::geometry(MultiPolygon, 4326) as geom
from public.school_districts_raw
group by 1,2,3;
```

### Why this works
- `st_union` dissolves boundaries
- `st_collectionextract(...,3)` removes non-polygon artifacts
- `st_multi` enforces MultiPolygon consistency
- Explicit cast locks SRID and type

---

## 5. Add Primary Key & Indexes

```sql
alter table public.school_districts_clean
  add column id bigserial primary key;

create index if not exists school_districts_clean_geom_gix
  on public.school_districts_clean
  using gist (geom);

create index if not exists school_districts_clean_lea_id_ix
  on public.school_districts_clean (lea_id);
```

These indexes are required for:
- Fast spatial joins (`ST_Intersects`)
- Dashboard filtering by district

---

## 6. Validation Queries (Do Not Skip)

### 6.1 Geometry type + SRID
```sql
select geometrytype(geom), st_srid(geom), count(*)
from public.school_districts_clean
group by 1,2;
```

Expected:
```
MULTIPOLYGON | 4326
```

---

### 6.2 One row per district
```sql
select count(*) as districts
from public.school_districts_clean;
```

Expected:
- Approximately the number of Ohio school districts

---

### 6.3 Geometry validity (optional but recommended)
```sql
select count(*)
from public.school_districts_clean
where not st_isvalid(geom);
```

Expected:
```
0
```

If non-zero, fix with:
```sql
update public.school_districts_clean
set geom = st_makevalid(geom)::geometry(MultiPolygon,4326)
where not st_isvalid(geom);
```

---

## 7. How This Table Is Used

`school_districts_clean` is designed to be used for:

- Sale → district assignment
- Parcel → district assignment
- District-level aggregations
- Realtor-facing dashboards

Example join:
```sql
select s.*, d.district_name
from public.sales_with_geom s
join public.school_districts_clean d
  on st_intersects(d.geom, s.geom);
```

---

## 8. Why This Should Be a Table (Not a View)

This step is **computationally expensive**:
- `ST_Union`
- Geometry normalization

Materializing it as a table:
- Avoids repeated computation
- Improves dashboard performance
- Produces stable, inspectable geometry

Rebuild only when:
- The source shapefile changes
- You refresh boundary data

---

## 9. Summary

`school_districts_clean` is the **canonical school district boundary layer**.

It guarantees:
- One row per district
- Consistent geometry type
- Safe spatial joins
- Production-ready performance

All downstream analytics and dashboards should reference this table — never the raw shapefile load.