# Address Parsing and Enrichment Utility

This module provides tools for parsing and enriching street address data using NLP and fuzzy matching, specifically tailored for Hamilton County datasets.

## Features

- Parse unstructured address strings into structured components (house number, street, etc.)
- Match street names using fuzzy matching (RapidFuzz)
- Map addresses to ZIP codes and cities using official street centerline and ZIP datasets
- Includes reusable `AddressEnricher` class

---

## Installation

```bash
pip install pandas numpy rapidfuzz spacy
python -m spacy download en_core_web_sm
```

---

## Usage

### 1. Basic Enrichment with `AddressEnricher`

```python
from address_module import address_enricher

result = address_enricher.enrich("123 Main St")
print(result)
# Output: {'st_num': '123', 'apt_num': None, 'street': 'Main St', 'postal_code': '45202', 'street_corrected': 'MAIN ST', 'city': 'Cincinnati', 'state': 'Ohio'}
```

### 2. DataFrame ZIP Code Assignment

```python
from address_module import add_zip_code

df = pd.DataFrame({"Address": ["123 Main St", "500 Vine St"]})
df = add_zip_code(df)
print(df[['Address', 'postal_code']])
```

---

## Components

### Functions

- `parse_house_number(str)`: Extracts numeric prefix from a house number string.
- `add_zip_code(df, centerline_path, address_col)`: Adds ZIP info to a DataFrame.
- `tag_address(address)`: Tokenizes and parses components using spaCy.

### Classes

#### AddressEnricher

```python
AddressEnricher(centerline_path: str, zipcode_path: str, score_cut: int = 80)
```

- `enrich(raw_address: str) -> dict`: Enrich a raw address with ZIP and city.

---

## Notes

- You may disable enrichment by setting the `HCH_SCRAPER_SKIP_ENRICHER` environment variable.
- All ZIP matching is based on Hamilton County datasets.

## License

MIT