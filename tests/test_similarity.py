import pandas as pd

from hch_scraper.services.similarity import (
    find_similar_properties,
    rank_similar_properties,
    score_property_similarity,
)


def _properties_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "parcel_number": "P1",
                "address": "100 MAIN ST",
                "finsqft": 1500,
                "year_built": 1950,
                "bedrooms": 3,
                "full_baths": 2,
                "half_baths": 1,
                "acreage": 0.20,
                "amount": "$250,000",
                "use": 510,
                "school_district": "CINCINNATI CSD",
                "latitude": 39.1000,
                "longitude": -84.5000,
            },
            {
                "parcel_number": "P2",
                "address": "102 MAIN ST",
                "finsqft": 1525,
                "year_built": 1952,
                "bedrooms": 3,
                "full_baths": 2,
                "half_baths": 1,
                "acreage": 0.19,
                "amount": "$255,000",
                "use": 510,
                "school_district": "CINCINNATI CSD",
                "latitude": 39.1005,
                "longitude": -84.5003,
            },
            {
                "parcel_number": "P3",
                "address": "999 FAR RD",
                "finsqft": 2900,
                "year_built": 2005,
                "bedrooms": 5,
                "full_baths": 3,
                "half_baths": 1,
                "acreage": 1.40,
                "amount": "$510,000",
                "use": 599,
                "school_district": "OTHER CSD",
                "latitude": 39.3000,
                "longitude": -84.7000,
            },
            {
                "parcel_number": "P4",
                "address": "104 MAIN ST",
                "finsqft": 1490,
                "year_built": 1949,
                "bedrooms": 3,
                "full_baths": 2,
                "half_baths": 0,
                "acreage": 0.22,
                "amount": "$248,000",
                "use": 510,
                "school_district": "CINCINNATI CSD",
                "latitude": 39.1700,
                "longitude": -84.5000,
            },
        ]
    )


def test_score_property_similarity_prefers_close_match():
    properties = _properties_frame()
    subject = properties.iloc[0]
    close_match = properties.iloc[1]
    distant_match = properties.iloc[2]

    close_score = score_property_similarity(subject, close_match)
    distant_score = score_property_similarity(subject, distant_match)

    assert close_score.score > distant_score.score
    assert close_score.distance_miles is not None
    assert close_score.components["distance_miles"] > distant_score.components["distance_miles"]


def test_score_property_similarity_handles_missing_location():
    subject = {
        "parcel_number": "P1",
        "finsqft": 1500,
        "year_built": 1950,
        "bedrooms": 3,
        "full_baths": 2,
        "half_baths": 1,
        "acreage": 0.20,
        "amount": "$250,000",
        "school_district": "CINCINNATI CSD",
    }
    candidate = {
        "parcel_number": "P2",
        "finsqft": 1510,
        "year_built": 1948,
        "bedrooms": 3,
        "full_baths": 2,
        "half_baths": 1,
        "acreage": 0.18,
        "amount": "$252,000",
        "school_district": "CINCINNATI CSD",
    }

    scored = score_property_similarity(subject, candidate)

    assert scored.score > 0
    assert scored.distance_miles is None
    assert "distance_miles" not in scored.components
    assert abs(sum(scored.weights_used.values()) - 1.0) < 1e-9


def test_score_property_similarity_does_not_use_acreage():
    subject = {
        "parcel_number": "P1",
        "finsqft": 1500,
        "year_built": 1950,
        "bedrooms": 3,
        "full_baths": 2,
        "half_baths": 1,
        "acreage": 0.10,
        "amount": "$250,000",
        "school_district": "CINCINNATI CSD",
        "latitude": 39.1,
        "longitude": -84.5,
    }
    candidate = {
        "parcel_number": "P2",
        "finsqft": 1500,
        "year_built": 1950,
        "bedrooms": 3,
        "full_baths": 2,
        "half_baths": 1,
        "acreage": 5.00,
        "amount": "$250,000",
        "school_district": "CINCINNATI CSD",
        "latitude": 39.1,
        "longitude": -84.5,
    }

    scored = score_property_similarity(subject, candidate)

    assert "acreage" not in scored.components
    assert scored.score == 100.0


def test_rank_similar_properties_excludes_subject_and_sorts():
    properties = _properties_frame()
    subject = properties.iloc[0]

    ranked = rank_similar_properties(subject, properties, top_n=3)

    assert list(ranked["parcel_number"]) == ["P2", "P4", "P3"]
    assert ranked["similarity_score"].tolist() == sorted(
        ranked["similarity_score"].tolist(), reverse=True
    )


def test_find_similar_properties_respects_distance_filter():
    properties = _properties_frame()

    ranked = find_similar_properties(
        properties,
        "P1",
        top_n=5,
        max_distance_miles=2.0,
    )

    assert ranked["parcel_number"].tolist() == ["P2"]
