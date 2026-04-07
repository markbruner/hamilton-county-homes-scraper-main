import geopandas as gpd
import numpy as np
from shapely.geometry import Point, Polygon

from hch_scraper.services.high_turnover_visual import (
    BLUE_RED_COLORSCALE,
    CustomerError,
    _build_dashboard_html,
    _build_detail_payload,
    _build_initial_detail_html,
    _build_leaderboard_html,
    _build_map_rows_payload,
    _build_yearly_turnover_figure,
    _calculate_turnover,
    _format_year_ranges,
    _prepare_yearly_map_data,
    create_hotspot_persistence_wgs84,
    create_sales_stock_by_year,
    gpd_is_empty_check,
)


def _polygon(min_x, min_y):
    return Polygon(
        [
            (min_x, min_y),
            (min_x + 0.01, min_y),
            (min_x + 0.01, min_y + 0.01),
            (min_x, min_y + 0.01),
        ]
    )


def _subdivision_grid() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        [
            {
                "planid": "A",
                "subdivision_name": "Alpha Acres",
                "housing_stock": 100,
                "geometry": _polygon(-84.60, 39.10),
            },
            {
                "planid": "B",
                "subdivision_name": "Beta Woods",
                "housing_stock": 50,
                "geometry": _polygon(-84.58, 39.10),
            },
            {
                "planid": "C",
                "subdivision_name": "Cedar Court",
                "housing_stock": 10,
                "geometry": _polygon(-84.56, 39.10),
            },
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )


def _sale_rows(planid: str, year: int, count: int) -> list[dict]:
    point_by_planid = {
        "A": Point(-84.595, 39.105),
        "B": Point(-84.575, 39.105),
        "C": Point(-84.555, 39.105),
    }
    return [
        {
            "parcel_number": f"{planid}-{year}-{index}",
            "transfer_year": year,
            "centroid": point_by_planid[planid],
        }
        for index in range(count)
    ]


def _parcel_sales_points() -> gpd.GeoDataFrame:
    rows = []
    rows.extend(_sale_rows("A", 2024, 20))
    rows.extend(_sale_rows("B", 2024, 5))
    rows.extend(_sale_rows("C", 2024, 8))
    rows.extend(_sale_rows("A", 2025, 5))
    rows.extend(_sale_rows("B", 2025, 10))
    return gpd.GeoDataFrame(rows, geometry="centroid", crs="EPSG:4326")


def _by_year_and_planid(result: gpd.GeoDataFrame, year: int, planid: str):
    rows = result[
        (result["transfer_year"] == year)
        & (result["planid"] == planid)
    ]
    assert len(rows) == 1
    return rows.iloc[0]


def test_create_sales_stock_by_year_calculates_counts_turnover_and_hotspots():
    result = create_sales_stock_by_year(
        _parcel_sales_points(),
        _subdivision_grid(),
        hotspot_quantile=0.5,
        min_housing_stock=30,
    )

    assert len(result) == 6

    a_2024 = _by_year_and_planid(result, 2024, "A")
    b_2024 = _by_year_and_planid(result, 2024, "B")
    c_2024 = _by_year_and_planid(result, 2024, "C")
    a_2025 = _by_year_and_planid(result, 2025, "A")
    b_2025 = _by_year_and_planid(result, 2025, "B")
    c_2025 = _by_year_and_planid(result, 2025, "C")

    assert a_2024["parcels_sold"] == 20
    assert b_2024["parcels_sold"] == 5
    assert c_2024["parcels_sold"] == 8
    assert c_2025["parcels_sold"] == 0

    assert a_2024["turnover_rate"] == 0.20
    assert b_2024["turnover_rate"] == 0.10
    assert c_2024["turnover_rate"] == 0.80
    assert a_2025["turnover_rate"] == 0.05
    assert b_2025["turnover_rate"] == 0.20

    assert a_2024["hotspot_threshold"] == 0.15
    assert b_2024["hotspot_threshold"] == 0.15
    assert a_2025["hotspot_threshold"] == 0.125
    assert b_2025["hotspot_threshold"] == 0.125

    assert bool(a_2024["is_hotspot"]) is True
    assert bool(b_2024["is_hotspot"]) is False
    assert bool(c_2024["is_hotspot"]) is False
    assert bool(a_2025["is_hotspot"]) is False
    assert bool(b_2025["is_hotspot"]) is True
    assert bool(c_2025["is_hotspot"]) is False
    assert bool(c_2024["meets_min_housing_stock"]) is False
    assert bool(c_2025["meets_min_housing_stock"]) is False


def test_calculate_turnover_returns_nan_when_housing_stock_is_zero():
    result = _calculate_turnover(
        gpd.GeoDataFrame(
            [
                {"housing_stock": 0, "parcels_sold": 3},
                {"housing_stock": 4, "parcels_sold": 1},
            ]
        )
    )

    assert np.isnan(result[0])
    assert result[1] == 0.25


def test_gpd_is_empty_check_accepts_non_empty_geodataframe():
    gpd_is_empty_check(_subdivision_grid())


def test_gpd_is_empty_check_raises_for_empty_geodataframe():
    empty = gpd.GeoDataFrame(columns=["planid", "geometry"], geometry="geometry", crs="EPSG:4326")

    try:
        gpd_is_empty_check(empty)
    except CustomerError as exc:
        assert exc.error_code == "GPD_001"
    else:
        raise AssertionError("Expected CustomerError for empty GeoDataFrame")


def test_prepare_yearly_map_data_filters_subdivisions_below_min_housing_stock():
    sales_stock_by_year = create_sales_stock_by_year(
        _parcel_sales_points(),
        _subdivision_grid(),
        hotspot_quantile=0.5,
        min_housing_stock=30,
    )
    persistence, _center = create_hotspot_persistence_wgs84(sales_stock_by_year)

    prepared = _prepare_yearly_map_data(sales_stock_by_year, persistence)

    assert set(prepared["planid"]) == {"A", "B"}
    assert prepared["housing_stock"].min() >= 30
    assert set(prepared["subdivision_label"]) == {"Alpha Acres", "Beta Woods"}


def test_yearly_turnover_figure_uses_blue_to_red_colorscale():
    sales_stock_by_year = create_sales_stock_by_year(
        _parcel_sales_points(),
        _subdivision_grid(),
        hotspot_quantile=0.5,
        min_housing_stock=30,
    )
    persistence, center = create_hotspot_persistence_wgs84(sales_stock_by_year)
    prepared = _prepare_yearly_map_data(sales_stock_by_year, persistence)

    fig = _build_yearly_turnover_figure(prepared, center)

    assert fig.data[0].colorscale == tuple((value, color) for value, color in BLUE_RED_COLORSCALE)
    assert fig.data[0].type == "choroplethmap"
    assert "Alpha Acres" in fig.data[0].customdata[:, 1]


def test_yearly_turnover_figure_adds_selected_subdivision_highlight_trace():
    sales_stock_by_year = create_sales_stock_by_year(
        _parcel_sales_points(),
        _subdivision_grid(),
        hotspot_quantile=0.5,
        min_housing_stock=30,
    )
    persistence, center = create_hotspot_persistence_wgs84(sales_stock_by_year)
    prepared = _prepare_yearly_map_data(sales_stock_by_year, persistence)

    fig = _build_yearly_turnover_figure(prepared, center)

    assert len(fig.data) == 2
    highlight = fig.data[1]
    assert highlight.type == "choroplethmap"
    assert highlight.name == "Selected Subdivision"
    assert highlight.locations == ()
    assert highlight.z == ()
    assert highlight.marker.line.width == 4
    assert highlight.showscale is False


def test_yearly_turnover_figure_scales_to_max_displayed_turnover_pct():
    sales_stock_by_year = create_sales_stock_by_year(
        _parcel_sales_points(),
        _subdivision_grid(),
        hotspot_quantile=0.5,
        min_housing_stock=30,
    )
    persistence, center = create_hotspot_persistence_wgs84(sales_stock_by_year)
    prepared = _prepare_yearly_map_data(sales_stock_by_year, persistence)
    prepared["turnover_pct"] = [0.2, 0.4, 0.1, 0.6]

    fig = _build_yearly_turnover_figure(prepared, center)

    assert fig.data[0].zmin == 0
    assert fig.data[0].zmax == 0.6


def test_yearly_turnover_figure_has_top_slider_without_title_or_animation_buttons():
    sales_stock_by_year = create_sales_stock_by_year(
        _parcel_sales_points(),
        _subdivision_grid(),
        hotspot_quantile=0.5,
        min_housing_stock=30,
    )
    persistence, center = create_hotspot_persistence_wgs84(sales_stock_by_year)
    prepared = _prepare_yearly_map_data(sales_stock_by_year, persistence)

    fig = _build_yearly_turnover_figure(prepared, center)

    assert fig.layout.title.text is None
    assert fig.layout.map.style == "open-street-map"
    assert len(fig.layout.updatemenus) == 0
    assert fig.layout.sliders[0].y > 1
    assert fig.layout.sliders[0].x == 0.08
    assert all(frame.layout.title.text is None for frame in fig.frames)


def test_format_year_ranges_compacts_sequential_years():
    assert _format_year_ranges("2020, 2021, 2022, 2024, 2025") == "2020-2022, 2024-2025"
    assert _format_year_ranges("2023") == "2023"
    assert _format_year_ranges("None") == "None"


def test_leaderboard_defaults_to_top_five_and_renders_avg_turnover_kpi():
    rows = [
        {
            "planid": f"P{index}",
            "subdivision_name": f"Named Place {index}",
            "hotspot_year_count": 6 - index,
            "hotspot_years": "2020, 2021, 2022, 2024",
            "avg_turnover_pct": 10 + index,
            "geometry": _polygon(-84.60 + (index * 0.01), 39.10),
        }
        for index in range(6)
    ]
    persistence = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")

    html = _build_leaderboard_html(persistence)

    assert html.count("leaderboard-row") == 5
    assert "P0" in html
    assert "P4" in html
    assert "P5" not in html
    assert "Named Place 0" in html
    assert "Subdivision P0" not in html
    assert 'class="leaderboard-name"' in html
    assert 'class="leaderboard-kpi"' in html
    assert "<strong>10.00%</strong>" in html
    assert "avg turnover" in html
    assert "2020-2022, 2024" not in html


def test_selected_subdivision_detail_uses_compact_year_ranges():
    yearly = gpd.GeoDataFrame(
        [
            {
                "planid": "A",
                "subdivision_label": "Alpha Acres",
                "transfer_year": 2020,
                "housing_stock": 100,
                "parcels_sold": 10,
                "turnover_pct": 10,
                "hotspot_threshold_pct": 8,
                "is_hotspot": True,
                "hotspot_year_count": 4,
                "hotspot_years": "2020, 2021, 2022, 2024",
                "avg_turnover_pct": 12.5,
                "geometry": _polygon(-84.60, 39.10),
            }
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )
    persistence = gpd.GeoDataFrame(
        [
            {
                "planid": "A",
                "subdivision_name": "Alpha Acres",
                "subdivision_label": "Alpha Acres",
                "hotspot_year_count": 4,
                "hotspot_years": "2020, 2021, 2022, 2024",
                "avg_turnover_pct": 12.5,
                "geometry": _polygon(-84.60, 39.10),
            }
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )

    payload = _build_detail_payload(yearly)
    initial_html = _build_initial_detail_html(persistence)

    assert payload["A"]["summary"]["hotspot_year_ranges"] == "2020-2022, 2024"
    assert "2020-2022, 2024" in initial_html


def test_dashboard_updates_selected_subdivision_on_map_year_changes():
    sales_stock_by_year = create_sales_stock_by_year(
        _parcel_sales_points(),
        _subdivision_grid(),
        hotspot_quantile=0.5,
        min_housing_stock=30,
    )
    persistence, center = create_hotspot_persistence_wgs84(sales_stock_by_year)
    prepared = _prepare_yearly_map_data(sales_stock_by_year, persistence)
    fig = _build_yearly_turnover_figure(prepared, center)

    html = _build_dashboard_html(fig, prepared, persistence)

    assert "Map Year" in html
    assert "plotly_sliderchange" in html
    assert "plotly_animatingframe" in html
    assert "currentMapYear" in html
    assert "HIGHLIGHT_TRACE_INDEX" in html
    assert "highlightSubdivision" in html
    assert "Plotly.restyle" in html


def test_map_rows_payload_supports_hotspot_only_filtering():
    sales_stock_by_year = create_sales_stock_by_year(
        _parcel_sales_points(),
        _subdivision_grid(),
        hotspot_quantile=0.5,
        min_housing_stock=30,
    )
    persistence, _center = create_hotspot_persistence_wgs84(sales_stock_by_year)
    prepared = _prepare_yearly_map_data(sales_stock_by_year, persistence)

    payload = _build_map_rows_payload(prepared)

    assert set(payload) == {"2024", "2025"}
    assert [row["planid"] for row in payload["2024"]] == ["A", "B"]
    assert [row["planid"] for row in payload["2024"] if row["is_hotspot"]] == ["A"]
    assert [row["planid"] for row in payload["2025"] if row["is_hotspot"]] == ["B"]


def test_dashboard_includes_hotspot_only_toggle():
    sales_stock_by_year = create_sales_stock_by_year(
        _parcel_sales_points(),
        _subdivision_grid(),
        hotspot_quantile=0.5,
        min_housing_stock=30,
    )
    persistence, center = create_hotspot_persistence_wgs84(sales_stock_by_year)
    prepared = _prepare_yearly_map_data(sales_stock_by_year, persistence)
    fig = _build_yearly_turnover_figure(prepared, center)

    html = _build_dashboard_html(fig, prepared, persistence)

    assert "hotspots-only-toggle" in html
    assert "Show hotspots only" in html
    assert "mapRowsForYear" in html
    assert "row.is_hotspot" in html
    assert "refreshMapTrace" in html


def test_dashboard_disables_plotly_autoplay():
    class FakeFigure:
        def __init__(self):
            self.to_html_kwargs = None

        def to_html(self, **kwargs):
            self.to_html_kwargs = kwargs
            return "<div id='turnover-map'></div>"

    yearly = gpd.GeoDataFrame(
        [
            {
                "planid": "A",
                "subdivision_label": "Alpha Acres",
                "transfer_year": 2020,
                "housing_stock": 100,
                "parcels_sold": 10,
                "turnover_pct": 10,
                "hotspot_threshold_pct": 8,
                "is_hotspot": True,
                "is_hotspot_label": "Yes",
                "hotspot_year_count": 1,
                "hotspot_years": "2020",
                "avg_turnover_pct": 10,
                "geometry": _polygon(-84.60, 39.10),
            }
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )
    persistence = gpd.GeoDataFrame(
        [
            {
                "planid": "A",
                "subdivision_label": "Alpha Acres",
                "hotspot_year_count": 1,
                "hotspot_years": "2020",
                "avg_turnover_pct": 10,
                "geometry": _polygon(-84.60, 39.10),
            }
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )
    fig = FakeFigure()

    _build_dashboard_html(fig, yearly, persistence)

    assert fig.to_html_kwargs["auto_play"] is False


def test_create_hotspot_persistence_wgs84_summarizes_years_and_average_turnover():
    sales_stock_by_year = create_sales_stock_by_year(
        _parcel_sales_points(),
        _subdivision_grid(),
        hotspot_quantile=0.5,
        min_housing_stock=30,
    )

    persistence, center = create_hotspot_persistence_wgs84(sales_stock_by_year)

    assert persistence.crs.to_epsg() == 4326
    assert set(persistence["planid"]) == {"A", "B"}
    assert center.x < -84.57
    assert center.y > 39.10

    by_planid = persistence.set_index("planid")
    assert by_planid.loc["A", "hotspot_year_count"] == 1
    assert by_planid.loc["A", "subdivision_name"] == "Alpha Acres"
    assert by_planid.loc["A", "subdivision_label"] == "Alpha Acres"
    assert by_planid.loc["A", "hotspot_years"] == "2024"
    assert by_planid.loc["A", "avg_turnover_pct"] == 20.0
    assert by_planid.loc["B", "hotspot_year_count"] == 1
    assert by_planid.loc["B", "subdivision_name"] == "Beta Woods"
    assert by_planid.loc["B", "subdivision_label"] == "Beta Woods"
    assert by_planid.loc["B", "hotspot_years"] == "2025"
    assert by_planid.loc["B", "avg_turnover_pct"] == 20.0


def test_create_hotspot_persistence_wgs84_handles_no_hotspots():
    sales_stock_by_year = create_sales_stock_by_year(
        _parcel_sales_points(),
        _subdivision_grid(),
        hotspot_quantile=1.0,
        min_housing_stock=1_000,
    )

    persistence, center = create_hotspot_persistence_wgs84(sales_stock_by_year)

    assert persistence.empty
    assert persistence.crs.to_epsg() == 4326
    assert center.x < -84.55
    assert center.y > 39.10
