# Parcel & Sales → School District Mapping (PostGIS)

This document covers the **downstream spatial mapping layer** that connects parcels and sales to school districts for analytics and dashboards.

It documents the following objects, grouped by purpose:

- `parcel_school_district` (materialized lookup table)
- `sales_school_district` (materialized analytics table)
- `v_sales_hamilton_with_school_district` (analytics view)
- `v_realtor_sales_map` (dashboard-safe view)

Together, these objects form the **core serving layer** for realtor-facing maps and district analytics.

---

## 1. Design Overview

### Why this layer exists

Raw identifiers in county data are:
- inconsistent across systems
- unstable over time
- not suitable for direct joins

This layer solves that by:
1. Assigning **each parcel** to a school district using geometry
2. Assigning **each sale** to a district via its parcel geometry
3. Exposing only **safe, read-optimized views** to dashboards

### Architectural pattern

```
parcel_polygons ─┐
                  ├─▶ parcel_school_district ─┐
school_districts ─┘                            ├─▶ sales_school_district
                                               │
sales_hamilton ────────────────────────────────┘
                                               │
                                               ├─▶ v_sales_hamilton_with_school_district
                                               └─▶ v_realtor_sales_map
```

---

## 2. `parcel_school_district`

### Purpose

A **lookup table** that assigns each parcel to exactly one school district and provides a representative point for fast joins and mapping.

This table is intentionally materialized to avoid repeated spatial joins.

---

### Creation SQL

```sql
drop table if exists public.parcel_school_district;

create table public.parcel_school_district as
select
  p.parcelid,
  p.audpclid,
  p.proptyid,
  d.id as district_id,
  d.district_name,
  d.lea_id,
  st_pointonsurface(p.geom)::geometry(Point,4326) as parcel_point
from public.parcel_polygons p
join public.school_districts_clean d
  on st_intersects(d.geom, st_pointonsurface(p.geom));
```

### Why `ST_PointOnSurface`
- Guaranteed to lie inside the parcel
- Avoids centroid edge cases
- Much faster than polygon-in-polygon joins

---

### Indexes

```sql
create index if not exists parcel_school_district_parcelid_ix
  on public.parcel_school_district (parcelid);

create index if not exists parcel_school_district_district_id_ix
  on public.parcel_school_district (district_id);

create index if not exists parcel_school_district_point_gix
  on public.parcel_school_district
  using gist (parcel_point);
```

---

## 3. `sales_school_district`

### Purpose

A **materialized analytics table** that joins sales to parcels and districts.

This table:
- powers district-level metrics
- supports fast time filtering
- avoids recomputing expensive joins in dashboards

**Important note on numeric fields:** `sales_hamilton.amount` is typically stored as text (as scraped). We derive a numeric `amount_num` here (and in downstream views) so analytics can aggregate without casting everywhere.

**Important note on BBB parsing:** `sales_hamilton.bbb` is a string. We parse it into numeric components for dashboards and modeling.

---

### Creation SQL

```sql
drop table if exists public.sales_school_district;

create table public.sales_school_district as
with base as (
  select
    s.record_key,
    s.transfer_date,
    s.amount,
    s.amount_num,
    s.address,
    s.parcel_number,
    s.bbb as bbb_raw,
    s.total_rooms,
    s.bedrooms,
    s.full_baths,
    s.half_baths,
    psd.district_id,
    psd.ode_irn,
    psd.district_name,
    psd.lea_id,
    psd.parcel_point as geom
  from public.sales_hamilton s
  join public.parcel_school_district psd
    on psd.parcelid = s.parcelid_join
)
select
  record_key,
  transfer_date,
  amount,
  amount_num,
  address,
  parcel_number,
  bbb_raw,
  total_rooms,
  bedrooms,
  full_baths,
  half_baths,
  district_id,
  district_name,
  lea_id,
  geom
from base;
```

---

### Indexes

```sql
create index if not exists sales_school_district_geom_gix
  on public.sales_school_district
  using gist (geom);

create index if not exists sales_school_district_district_id_ix
  on public.sales_school_district (district_id);

create index if not exists sales_school_district_transfer_date_ix
  on public.sales_school_district (transfer_date);

create index if not exists sales_school_district_amount_num_ix
  on public.sales_school_district (amount_num);
```

---

## 4. `v_sales_hamilton_with_school_district`

### Purpose

A **canonical analytics view** that exposes sales data with school district context.

This view:
- standardizes column naming
- includes **analytics-ready numeric fields** (e.g., `amount_num`)
- includes **BBB parsed fields** for dashboards/modeling

---

### Definition

```sql
create or replace view public.v_sales_hamilton_with_school_district as
select
  record_key,
  transfer_date,
  amount,
  amount_num,
  address,
  parcel_number,
  bbb_raw,
  bedrooms,
  full_bath,
  half_bath,
  district_id,
  district_name,
  lea_id,
  geom
from public.sales_school_district;
```

---

## 5. `v_realtor_sales_map`

### Purpose (Security-Critical)

This is the **only object intended to be queried by a realtor-facing dashboard**.

It intentionally:
- hides parcel IDs
- hides join keys
- limits columns to what is visually necessary
- provides dashboard-friendly numeric fields (e.g., `amount_num`)

This dramatically reduces scraping risk.

---

### Definition

```sql
create or replace view public.v_realtor_sales_map as
select
  record_key,
  transfer_date,
  amount,
  amount_num,
  address,
  district_name,
  bedrooms,
  full_bath,
  half_bath,
  geom
from public.sales_school_district
where transfer_date >= current_date - interval '365 days'
  and amount_num is not null;
```

---

## 6. Row-Level Security (Recommended)

Enable RLS on the dashboard view:

```sql
alter view public.v_realtor_sales_map enable row level security;

create policy "authenticated read-only"
on public.v_realtor_sales_map
for select
using (auth.role() = 'authenticated');
```

This ensures:
- no anonymous access
- no public scraping
- read-only behavior

---

## 7. Validation Queries

### Match rate sanity check

```sql
select
  count(*) as total_sales,
  count(*) filter (where district_id is not null) as matched_sales,
  round(
    100.0 * count(*) filter (where district_id is not null)
    / nullif(count(*),0),
    2
  ) as pct_matched
from public.sales_school_district;
```

### Amount parse sanity check (null rate)

```sql
select
  count(*) as total,
  count(*) filter (where amount_num is null) as amount_num_nulls,
  round(100.0 * count(*) filter (where amount_num is null) / nullif(count(*),0), 2) as pct_null
from public.sales_school_district;
```

### BBB parse sanity check (sample)

```sql
select
  bbb_raw,
  bedrooms,
  full_bath,
  half_bath,
  count(*) as n
from public.sales_school_district
group by 1,2,3,4
order by n desc
limit 50;
```

---

## 8. Rebuild Strategy

Rebuild in this order **only when source data changes**:

1. `school_districts_clean`
2. `parcel_school_district`
3. `sales_school_district`

Views (`v_*`) do **not** require rebuilds.

---

## 9. Summary

This layer provides:
- Stable parcel → district assignment
- High-confidence sales → district mapping
- Analytics-ready numeric + parsed fields (`amount_num`, BBB splits)
- Dashboard-safe data exposure
- Excellent performance for maps and filters

All realtor-facing dashboards should query **only** `v_realtor_sales_map`.

Raw tables should never be exposed directly.
