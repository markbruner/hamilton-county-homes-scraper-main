# Architecture

```mermaid
flowchart TD
  A[Scheduler / CLI] --> B[Date Range Builder]
  B --> C[Selenium Scraper]
  C --> D[CSV Download]
  D --> E[Address Parsing + Geocoding]
  E --> F[Supabase Upsert]
  E --> G[Local Cache - data/processed]
```
