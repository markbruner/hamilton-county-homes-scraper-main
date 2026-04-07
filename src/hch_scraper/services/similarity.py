from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

import pandas as pd


EARTH_RADIUS_MILES = 3958.7613


@dataclass(frozen=True)
class FeatureSpec:
    aliases: tuple[str, ...]
    weight: float
    scale: float | None = None
    kind: str = "numeric"


@dataclass(frozen=True)
class SimilarityScore:
    score: float
    components: dict[str, float]
    weights_used: dict[str, float]
    distance_miles: float | None


DEFAULT_FEATURE_SPECS: dict[str, FeatureSpec] = {
    "distance_miles": FeatureSpec(
        aliases=("lat", "latitude", "lon", "longitude"),
        weight=0.30,
        scale=1.5,
        kind="distance",
    ),
    "finsqft": FeatureSpec(aliases=("finsqft",), weight=0.22, scale=300.0),
    "year_built": FeatureSpec(aliases=("year_built",), weight=0.10, scale=15.0),
    "bedrooms": FeatureSpec(aliases=("bedrooms",), weight=0.08, scale=1.0),
    "full_baths": FeatureSpec(aliases=("full_baths",), weight=0.08, scale=1.0),
    "half_baths": FeatureSpec(aliases=("half_baths",), weight=0.04, scale=1.0),
    "sale_amount": FeatureSpec(
        aliases=("amount_num", "sale_amount", "amount"),
        weight=0.08,
        scale=50000.0,
    ),
    "use": FeatureSpec(aliases=("use",), weight=0.03, kind="categorical"),
    "school_district": FeatureSpec(
        aliases=("school_district",),
        weight=0.02,
        kind="categorical",
    ),
}


def score_property_similarity(
    subject: Mapping[str, object] | pd.Series,
    candidate: Mapping[str, object] | pd.Series,
    feature_specs: Mapping[str, FeatureSpec] | None = None,
) -> SimilarityScore:
    """
    Score similarity between two property records on a 0-100 scale.

    The model is intentionally lightweight and explainable:
    - numeric features use a smooth distance decay based on feature-specific scales
    - categorical features use exact-match similarity
    - geographic distance uses haversine miles when coordinates are available
    - missing features are ignored and remaining weights are renormalized
    """

    specs = dict(feature_specs or DEFAULT_FEATURE_SPECS)
    components: dict[str, float] = {}
    raw_weights: dict[str, float] = {}
    distance_miles: float | None = None

    for feature_name, spec in specs.items():
        if spec.kind == "distance":
            distance_miles = _distance_miles(subject, candidate)
            if distance_miles is None:
                continue
            similarity = _scaled_similarity(distance_miles, spec.scale or 1.0)
        elif spec.kind == "categorical":
            similarity = _categorical_similarity(subject, candidate, spec.aliases)
            if similarity is None:
                continue
        else:
            similarity = _numeric_similarity(subject, candidate, spec.aliases, spec.scale)
            if similarity is None:
                continue

        components[feature_name] = similarity
        raw_weights[feature_name] = spec.weight

    total_weight = sum(raw_weights.values())
    if total_weight <= 0:
        return SimilarityScore(
            score=0.0,
            components={},
            weights_used={},
            distance_miles=distance_miles,
        )

    weights_used = {
        feature_name: weight / total_weight for feature_name, weight in raw_weights.items()
    }
    score = 100.0 * sum(
        components[feature_name] * weights_used[feature_name]
        for feature_name in components
    )

    return SimilarityScore(
        score=round(score, 2),
        components=components,
        weights_used=weights_used,
        distance_miles=distance_miles,
    )


def rank_similar_properties(
    subject: Mapping[str, object] | pd.Series,
    candidates: pd.DataFrame,
    *,
    top_n: int = 10,
    feature_specs: Mapping[str, FeatureSpec] | None = None,
    exclude_same_parcel: bool = True,
    max_distance_miles: float | None = None,
    min_score: float | None = None,
) -> pd.DataFrame:
    """
    Score and rank a candidate property frame against a subject property record.
    """

    subject_parcel = _clean_text(_first_value(subject, ("parcel_number",)))
    ranked_rows: list[dict[str, object]] = []

    for _, candidate in candidates.iterrows():
        candidate_parcel = _clean_text(_first_value(candidate, ("parcel_number",)))
        if exclude_same_parcel and subject_parcel and candidate_parcel == subject_parcel:
            continue

        scored = score_property_similarity(subject, candidate, feature_specs)
        if max_distance_miles is not None and scored.distance_miles is not None:
            if scored.distance_miles > max_distance_miles:
                continue
        if min_score is not None and scored.score < min_score:
            continue

        row = candidate.to_dict()
        row["similarity_score"] = scored.score
        row["distance_miles"] = scored.distance_miles
        for feature_name, value in scored.components.items():
            row[f"similarity_{feature_name}"] = round(value, 4)
        ranked_rows.append(row)

    if not ranked_rows:
        return pd.DataFrame()

    ranked = pd.DataFrame(ranked_rows)
    ranked = ranked.sort_values(
        by=["similarity_score", "distance_miles"],
        ascending=[False, True],
        na_position="last",
    )
    return ranked.head(top_n).reset_index(drop=True)


def find_similar_properties(
    properties: pd.DataFrame,
    subject_parcel_number: str,
    *,
    top_n: int = 10,
    feature_specs: Mapping[str, FeatureSpec] | None = None,
    exclude_same_parcel: bool = True,
    max_distance_miles: float | None = None,
    min_score: float | None = None,
) -> pd.DataFrame:
    """
    Convenience wrapper that looks up the subject row by parcel number.
    """

    matches = properties.loc[
        properties["parcel_number"].astype("string") == str(subject_parcel_number)
    ]
    if matches.empty:
        raise KeyError(f"Parcel number not found: {subject_parcel_number}")

    subject = matches.iloc[0]
    return rank_similar_properties(
        subject,
        properties,
        top_n=top_n,
        feature_specs=feature_specs,
        exclude_same_parcel=exclude_same_parcel,
        max_distance_miles=max_distance_miles,
        min_score=min_score,
    )


def _numeric_similarity(
    left: Mapping[str, object] | pd.Series,
    right: Mapping[str, object] | pd.Series,
    aliases: tuple[str, ...],
    scale: float | None,
) -> float | None:
    """Score a numeric feature by applying a smooth decay to the absolute difference."""
    left_value = _to_float(_first_value(left, aliases))
    right_value = _to_float(_first_value(right, aliases))
    if left_value is None or right_value is None:
        return None
    return _scaled_similarity(abs(left_value - right_value), scale or 1.0)


def _categorical_similarity(
    left: Mapping[str, object] | pd.Series,
    right: Mapping[str, object] | pd.Series,
    aliases: tuple[str, ...],
) -> float | None:
    """Return exact-match similarity for the first available categorical value."""
    left_value = _clean_text(_first_value(left, aliases))
    right_value = _clean_text(_first_value(right, aliases))
    if left_value is None or right_value is None:
        return None
    return 1.0 if left_value == right_value else 0.0


def _scaled_similarity(difference: float, scale: float) -> float:
    """Convert a non-negative feature difference into a 0-1 similarity score."""
    return 1.0 / (1.0 + (difference / scale))


def _distance_miles(
    left: Mapping[str, object] | pd.Series,
    right: Mapping[str, object] | pd.Series,
) -> float | None:
    """Compute haversine distance in miles when both records include coordinates."""
    lat1 = _to_float(_first_value(left, ("lat", "latitude")))
    lon1 = _to_float(_first_value(left, ("lon", "longitude")))
    lat2 = _to_float(_first_value(right, ("lat", "latitude")))
    lon2 = _to_float(_first_value(right, ("lon", "longitude")))

    if None in {lat1, lon1, lat2, lon2}:
        return None

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    haversine = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(haversine))


def _first_value(
    record: Mapping[str, object] | pd.Series,
    aliases: tuple[str, ...],
) -> object | None:
    """Return the first non-null field value found under the provided aliases."""
    for alias in aliases:
        value = record.get(alias)
        if value is None or pd.isna(value):
            continue
        return value
    return None


def _to_float(value: object | None) -> float | None:
    """Best-effort float coercion for numeric strings and scalar values."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: object | None) -> str | None:
    """Normalize free-text values for case-insensitive equality comparisons."""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().upper()
    return text or None


__all__ = [
    "DEFAULT_FEATURE_SPECS",
    "FeatureSpec",
    "SimilarityScore",
    "find_similar_properties",
    "rank_similar_properties",
    "score_property_similarity",
]
