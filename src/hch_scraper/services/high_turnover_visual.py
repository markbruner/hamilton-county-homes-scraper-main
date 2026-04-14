import os
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path

import logging
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import geopandas as gpd


pd.set_option('display.max_columns', None)

int64_list = ["finsqft", "year_built","total_rooms","bedrooms","full_baths", "half_baths"]
core_cols = ['parcel_number', 'transfer_year', 'centroid']
TURNOVER_COLORSCALE = [
    [0.0, "#5b1f48"],
    [0.5, "#bf3f78"],
    [1.0, "#f06a4d"],
]
BLUE_RED_COLORSCALE = TURNOVER_COLORSCALE

@dataclass(frozen=True)
class HotspotConfig:
    start_year: int
    end_year: int
    use: str = '510'
    min_housing_stock: int = 30
    hotspot_quantile: float = 0.90
    output_path: Path = Path("persistent_hotspots_map.html")
    database_url: str | None = None

class CustomerError(Exception):
    """Exception raised for if the GeoDataFrame is empty"""
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code

def load_config(
    *,
    start_year: int,
    end_year: int,
    use: str = '510',
    min_housing_stock: int = 30,
    hotspot_quantile: float = 0.90,
    output_path: str = "persistent_hotspots_map.html",
) -> HotspotConfig:
    database_url = os.getenv("SUPABASE_DATABASE_URL")
    if not database_url:
        raise RuntimeError("SUPABASE_DATABASE_URL is required")
    return HotspotConfig(
        start_year=start_year,
        end_year=end_year,
        use=use,
        min_housing_stock=min_housing_stock,
        hotspot_quantile=hotspot_quantile,
        output_path=Path(output_path),
        database_url=database_url,
    )

# Query to get the parcel sales used for visualization.
def build_parcel_sales_query(use: str, start_year: int, end_year: int)->str:
    return f"""
        SELECT   sh.parcel_number,
            sh.address,
            sh.uspscity,
            sh.zipcode,
            sh.school_district,
            sh.bbb,
            sh.finsqft,
            sh.use,
            sh.home_type_name,
            sh.year_built,
            sh.transfer_date,
            sh.transfer_year,
            sh.amount,
            sh.amount_num,
            sh.total_rooms,
            sh.bedrooms,
            sh.full_baths,
            sh.half_baths,
            sh.longitude,
            sh.latitude,
            sh.planid,
            sh.name as subdivision_name,
            ST_SetSRID(ST_GeomFromGeoJSON(sh.centroid::text), 4326) as centroid,
            ST_SetSRID(ST_GeomFromGeoJSON(parcel_geom::text), 4326) as parcel_geom,
            ST_SetSRID(ST_GeomFromGeoJSON(sh.subdivision_geom::text), 4326) as subdivision_geom,
            ST_SetSRID(ST_GeomFromGeoJSON(sh.school_geom::text), 4326) as school_geom
        FROM silver.sales_enriched as sh
        WHERE use = '{use}'
            AND sh.transfer_year BETWEEN {start_year} AND {end_year}
            AND sh.amount_num > 0
        """

# Query to get all parcels in hamilton county, used for calculating
# housing stock in the county.
def build_all_parcel_query(use: str)->str:
    return f"""
            SELECT 
                pe.parcelid,
                pe.uspscity,
                pe.zipcode,
                pe.school_district,
                pe.use,
                pe.home_type_name,
                ST_SetSRID(ST_GeomFromGeoJSON(pe.centroid::text), 4326) as centroid
            FROM silver.parcels_enriched as pe
            WHERE pe.use = '{use}'
            """

def query_supabase(
        query: str,
        database_url: str,
        geom_col: str,
    ) -> gpd.GeoDataFrame:
    """
    Queries the supabase database created for this project.

    Parameters:
        - schema_name: The schema where the table is located, i.e. 
            "silver", "bronze", etc...
        - table_name : the name of the table.
        - query: the query to retrieve the data from supabase
    Returns:
        The function will return a GeoDataFrame of the data requested
        from the query.
    """
    from sqlalchemy import create_engine

    engine = create_engine(database_url)
    query = query
    try:
        return gpd.read_postgis(
            sql=query,
            con=engine,
            geom_col=geom_col
        )
    except Exception as e:
        logging.error(f"Unexpected error when querying Supabase: {e}", exc_info=True)
        raise

def prepare_sales_data(gdf: gpd.GeoDataFrame, list_int64: list[str]):
    """
    Formats data and creates data needed for visualization.
    """  

    gdf = gdf[~gdf.longitude.isna()]
    gdf[list_int64] = gdf[list_int64].astype("Int64")
    gdf = gdf.drop(['bbb','home_type_name','amount','use'],axis=1)
    gdf["transfer_date"] = pd.to_datetime(gdf["transfer_date"])

    gdf["zipcode"] = (
        gdf["zipcode"]
        .astype("Int64")
        .astype("object")
    )

    # Sort to ensure first and last sales are in order
    gdf = gdf.sort_values(['parcel_number', 'transfer_date'])
    return gdf

def get_counts(
        gdf: gpd.GeoDataFrame,
        group_list: list[str],
        counting_col: str,
        count_col_name: str,
    )->pd.DataFrame:
    """
    Creates a dataframe of counts based on specific groupings.

    Parameter
    ---------
    gdf : gdp.GeoDataFrame
    group_list : list[str]
        The columns in which are being grouped for counting.
    counting_col : str
        The field of interest for getting counts.
    count_col_name : str
        The name of the counting column.
    
    Returns
    --------
        A DataFrame that contains the grouped columns and the counts based on the 
        counting column choosen.
    """
    return (
        gdf.groupby(group_list)[counting_col]
        .nunique()
        .reset_index(name=count_col_name)
    )

def gpd_is_empty_check(gdf: gpd.GeoDataFrame):
    if gdf.empty:
        raise CustomerError("GeoDataFrame is empty", error_code="GPD_001")


def invalid_geometries(gdf: gpd.GeoDataFrame):
    if gdf.crs.to_epsg()!= 4326:
        raise CustomerError("GeoDataFrame crs is not EPSG:4326", error_code="GPD_002")
    
def missing_columns(gdf: gpd.GeoDataFrame, cols: list[str]):
    for i in cols:
        try:
            gdf[i]
        except KeyError as e:
            logging.error(f"Column {i} is missing, {e}")
            raise

def build_subdivision_grid(
        gdf: gpd.GeoDataFrame,
        subdivision_id_col: str,
        gpd_cols: list[str],
        geom_col: str,
    )->gpd.GeoDataFrame:
    """
    Creates the GeoDataFrame that will be used to map 
    high turnover subdivisions.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        The scraped property sales GeoDataFrame from the Hamilton
            County Auditors website.
    
    subdivision_id_col: str
        The id column for subdivisions.
            
    gpd_cols : list[str]
        List of columns needed for creating the subdivision grid.

    geom_col : str
        Geometry column used for the subdivisions.
    
    Returns
    -------
    A GeoDataFrame that contains the subdivision id and the 
    geometry associated with the subdivision.
    
    Additional Notes
    ----------------
    This function will change the wkb format of the geometry column 
    to EPSG:4326 the World Geodetic System 1984 (WGS84), a widely 
    standard used standard for 3D geographic mapping.
    """
    gpd_is_empty_check(gdf)
    invalid_geometries(gdf)
    missing_columns(gdf=gdf, cols=gpd_cols)

    # Gets the subdivisions that are represented in the gdf dataset.
    subdivision_gdf = (
        gdf[gpd_cols]
        .dropna(subset=[subdivision_id_col, geom_col])
        .drop_duplicates(ignore_index=True)
    )
    # Creating the geometry column
    gs = gpd.GeoSeries.from_wkb(subdivision_gdf[geom_col])
    attributes = subdivision_gdf.drop(columns=[geom_col])

    return gpd.GeoDataFrame(
        attributes,
        geometry=gs,
        crs=gdf.crs,
    )


def create_sales_stock_by_year(
        parcel_sales_points_gdf,
        subdivision_grid_gdf, 
        hotspot_quantile,
        min_housing_stock,
        )->gpd.GeoDataFrame:
    """
    Calculates the turnover rate by subdivision by year.

    Parameters
    ----------
    parcel_sales_points_gdf : gpd.GeoDataFrame
        Reduced GeoDataFrame from parcel_sales_gdf to just the core column list.

    subdivision_grid_gdf : gpd.GeoDataFrame
        The polygons of all the Hamilton County subdivisions.

    Returns
    -------
    A GeoDataFrame of subdivsions that meet the "hotspot" criteria:
        - At least 30 houses in the subdivision.
        - Has a turnover rate not null and greater than 0.
        - Has a turnover rate in the 90 percentile.
    """
    sales_stock_by_year = _calculate_sales_by_year(
        parcel_sales_points_gdf,
        subdivision_grid_gdf
    )

    sales_stock_by_year["parcels_sold"] = sales_stock_by_year["parcels_sold"].fillna(0).astype(int)

    sales_stock_by_year["turnover_rate"] = _calculate_turnover(sales_stock_by_year)

    sales_stock_by_year["turnover_pct"] = sales_stock_by_year["turnover_rate"] * 100

    sales_stock_by_year = gpd.GeoDataFrame(
        sales_stock_by_year,
        geometry="geometry",
        crs=subdivision_grid_gdf.crs,
    )

    sales_stock_by_year["meets_min_housing_stock"] = (
        sales_stock_by_year["housing_stock"] >= min_housing_stock
    )

    eligible_cells = sales_stock_by_year[sales_stock_by_year["meets_min_housing_stock"]].copy()

    thresholds = (
        eligible_cells.groupby("transfer_year")["turnover_rate"]
        .quantile(hotspot_quantile)
        .round(5)
        .reset_index(name="hotspot_threshold")
    )


    sales_stock_by_year = sales_stock_by_year.merge(
        thresholds,
        on="transfer_year",
        how="left"
    )

    sales_stock_by_year["is_hotspot"] = (
        sales_stock_by_year["meets_min_housing_stock"] &
        (sales_stock_by_year["turnover_rate"].notna()) &
        (sales_stock_by_year["turnover_rate"] > 0) &
        (sales_stock_by_year["turnover_rate"] >= sales_stock_by_year["hotspot_threshold"])
    )
    return sales_stock_by_year

def _calculate_sales_by_year(sales_point_gdf, subdivision_grid_gdf):
    """Aggregate yearly parcel-sale counts across every subdivision polygon."""
    subdivision_columns = ["planid", "housing_stock", "geometry"]
    if "subdivision_name" in subdivision_grid_gdf.columns:
        subdivision_columns.append("subdivision_name")
    if "school_district" in subdivision_grid_gdf.columns:
        subdivision_columns.append("school_district")

    # Joining the all_parcels data to the parcel_sales data.
    parcel_sales_points_grid_gdf = gpd.sjoin(
        sales_point_gdf,
        subdivision_grid_gdf,
        how="left",
        predicate="within",
    )

    sales_by_year_cell = get_counts(
        gdf = parcel_sales_points_grid_gdf,
        group_list = ["transfer_year", "planid"],
        counting_col="parcel_number",
        count_col_name="parcels_sold")
    
    years = (
        parcel_sales_points_grid_gdf["transfer_year"]
        .dropna()
        .sort_values()
        .unique()
        )
    
    year_cell = pd.MultiIndex.from_product(
    [years, subdivision_grid_gdf["planid"]],
    names=["transfer_year", "planid"]
    ).to_frame(index=False)

    return (
        year_cell
        .merge(
            subdivision_grid_gdf[subdivision_columns],
            on="planid",
            how="left"
        )
        .merge(
            sales_by_year_cell,
            on=["transfer_year", "planid"],
            how="left"
        )
    )


def _calculate_turnover(sales_stock_by_year):
    """Compute turnover as parcels sold divided by housing stock for each row."""
    return np.where(
    sales_stock_by_year["housing_stock"] > 0,
    sales_stock_by_year["parcels_sold"] / sales_stock_by_year["housing_stock"],
    np.nan,
    )

def create_hotspot_persistence_wgs84(sales_stock_by_year):
    """Summarize how many years each subdivision qualified as a hotspot."""
    hotspot_cells = sales_stock_by_year[sales_stock_by_year["is_hotspot"]].copy()

    hotspot_persistence = []

    for planid, group in hotspot_cells.groupby("planid"):
        years = sorted(group["transfer_year"].astype(int).unique())
        label = _subdivision_label(group.iloc[0])

        hotspot_persistence.append(
            {
                "planid": planid,
                "subdivision_name": _subdivision_name(group.iloc[0]),
                "subdivision_label": label,
                "hotspot_year_count": len(years),
                "hotspot_years": ", ".join(str(y) for y in years),
                "avg_turnover_pct": (group["turnover_rate"].mean() * 100).round(3),
                "geometry": group["geometry"].iloc[0],
            }
        )

    if not hotspot_persistence:
        center = sales_stock_by_year.to_crs("EPSG:4326").geometry.union_all().centroid
        empty = gpd.GeoDataFrame(
            columns=[
                "planid",
                "subdivision_name",
                "subdivision_label",
                "hotspot_year_count",
                "hotspot_years",
                "avg_turnover_pct",
                "geometry",
            ],
            geometry="geometry",
            crs="EPSG:4326",
        )
        return empty, center

    hotspot_persistence_gdf = gpd.GeoDataFrame(
        hotspot_persistence,
        geometry="geometry",
        crs=sales_stock_by_year.crs,
    )


    hotspot_persistence_wgs84 =hotspot_persistence_gdf.to_crs("EPSG:4326").copy()
    hotspot_persistence_wgs84["hotspot_year_count"] = hotspot_persistence_wgs84["hotspot_year_count"].astype(int)

    center = hotspot_persistence_wgs84.geometry.union_all().centroid

    return hotspot_persistence_wgs84, center

def create_persistence_map(
        hotspot_persistence_wgs84: gpd.GeoDataFrame,
        center: gpd.GeoSeries,
        map_file: str,
        sales_stock_by_year: gpd.GeoDataFrame,
        ) -> go.Figure:
    """Render an interactive turnover dashboard and write it to an HTML file."""
    yearly_wgs84 = _prepare_yearly_map_data(
        sales_stock_by_year=sales_stock_by_year,
        hotspot_persistence_wgs84=hotspot_persistence_wgs84,
    )
    fig = _build_yearly_turnover_figure(yearly_wgs84, center)
    dashboard_html = _build_dashboard_html(
        fig=fig,
        yearly_wgs84=yearly_wgs84,
        hotspot_persistence_wgs84=hotspot_persistence_wgs84,
    )

    Path(map_file).write_text(dashboard_html, encoding="utf-8")
    return fig


def _prepare_yearly_map_data(
        sales_stock_by_year: gpd.GeoDataFrame,
        hotspot_persistence_wgs84: gpd.GeoDataFrame,
        ) -> gpd.GeoDataFrame:
    """Merge yearly turnover rows with persistence summary fields for the UI."""
    if "meets_min_housing_stock" in sales_stock_by_year.columns:
        sales_stock_by_year = sales_stock_by_year[
            sales_stock_by_year["meets_min_housing_stock"]
        ].copy()

    yearly_wgs84 = sales_stock_by_year.to_crs("EPSG:4326").copy()
    yearly_wgs84["planid"] = yearly_wgs84["planid"].astype(str)
    if "subdivision_name" not in yearly_wgs84.columns:
        yearly_wgs84["subdivision_name"] = None
    yearly_wgs84["subdivision_label"] = yearly_wgs84.apply(_subdivision_label, axis=1)
    yearly_wgs84["transfer_year"] = yearly_wgs84["transfer_year"].astype(int)
    yearly_wgs84["turnover_pct"] = yearly_wgs84["turnover_pct"].fillna(0).round(2)
    yearly_wgs84["hotspot_threshold_pct"] = (
        yearly_wgs84["hotspot_threshold"].fillna(0) * 100
    ).round(2)

    persistence_columns = [
        "planid",
        "hotspot_year_count",
        "hotspot_years",
        "avg_turnover_pct",
    ]
    if hotspot_persistence_wgs84.empty:
        persistence = pd.DataFrame(columns=persistence_columns)
    else:
        persistence = pd.DataFrame(
            hotspot_persistence_wgs84.drop(columns="geometry")[persistence_columns]
        )
        persistence["planid"] = persistence["planid"].astype(str)

    yearly_wgs84 = yearly_wgs84.merge(persistence, on="planid", how="left")
    yearly_wgs84["hotspot_year_count"] = (
        yearly_wgs84["hotspot_year_count"].fillna(0).astype(int)
    )
    yearly_wgs84["hotspot_years"] = yearly_wgs84["hotspot_years"].fillna("None")
    yearly_wgs84["avg_turnover_pct"] = yearly_wgs84["avg_turnover_pct"].fillna(0).round(2)
    yearly_wgs84["is_hotspot_label"] = np.where(
        yearly_wgs84["is_hotspot"],
        "Yes",
        "No",
    )

    return yearly_wgs84


def _build_yearly_turnover_figure(
        yearly_wgs84: gpd.GeoDataFrame,
        center: gpd.GeoSeries,
        ) -> go.Figure:
    """Build a choropleth map that the dashboard filters by year."""
    if yearly_wgs84.empty:
        fig = go.Figure()
        fig.update_layout(
            map={
                "style": "open-street-map",
                "center": {"lat": center.y, "lon": center.x},
                "zoom": 10.5,
            },
            annotations=[
                {
                    "text": "No subdivisions meet the minimum housing stock filter.",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"size": 18},
                }
            ],
            margin=dict(r=0, l=0, b=0, t=20),
        )
        return fig

    years = sorted(yearly_wgs84["transfer_year"].unique())
    base_year = years[0]
    base_geometries = yearly_wgs84.drop_duplicates("planid")[["planid", "geometry"]]
    geojson = json.loads(base_geometries.to_json())

    def frame_data(year: int) -> gpd.GeoDataFrame:
        return (
            yearly_wgs84[yearly_wgs84["transfer_year"] == year]
            .sort_values("planid")
            .copy()
        )

    def customdata(frame: pd.DataFrame) -> np.ndarray:
        return frame[
            [
                "planid",
                "subdivision_label",
                "transfer_year",
                "housing_stock",
                "parcels_sold",
                "turnover_pct",
                "hotspot_threshold_pct",
                "is_hotspot_label",
                "hotspot_year_count",
                "hotspot_years",
                "avg_turnover_pct",
            ]
        ].to_numpy()

    initial = frame_data(base_year)
    initial_turnover = initial["turnover_pct"].dropna()
    color_min = float(initial_turnover.min()) if not initial_turnover.empty else 0
    color_max = float(initial_turnover.max()) if not initial_turnover.empty else 1
    if color_min == color_max:
        color_max = color_min + 1

    fig = go.Figure(
        data=[
            go.Choroplethmap(
                geojson=geojson,
                locations=initial["planid"],
                z=initial["turnover_pct"],
                featureidkey="properties.planid",
                customdata=customdata(initial),
                colorscale=TURNOVER_COLORSCALE,
                zmin=color_min,
                zmax=color_max,
                marker_opacity=0.68,
                marker_line_width=0.7,
                marker_line_color="#fff7ed",
                colorbar={
                    "title": "Turnover %",
                    "thickness": 14,
                    "len": 0.74,
                },
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>"
                    "Plan ID: %{customdata[0]}<br>"
                    "Year: %{customdata[2]}<br>"
                    "Turnover: %{customdata[5]:.2f}%<br>"
                    "Parcels sold: %{customdata[4]}<br>"
                    "Housing stock: %{customdata[3]}<br>"
                    "Hotspot threshold: %{customdata[6]:.2f}%<br>"
                    "Hotspot this year: %{customdata[7]}<br>"
                    "Persistent hotspot years: %{customdata[8]}"
                    "<extra></extra>"
                ),
            ),
            go.Choroplethmap(
                geojson=geojson,
                locations=[],
                z=[],
                featureidkey="properties.planid",
                colorscale=[[0, "#17324d"], [1, "#17324d"]],
                zmin=0,
                zmax=1,
                marker_opacity=0.16,
                marker_line_width=4,
                marker_line_color="#17324d",
                showscale=False,
                showlegend=False,
                hoverinfo="skip",
                name="Selected Subdivision",
            )
        ],
    )

    fig.update_layout(
        map={
            "style": "open-street-map",
            "center": {"lat": center.y, "lon": center.x},
            "zoom": 10.5,
        },
        margin=dict(r=0, l=0, b=0, t=20),
    )

    return fig


def _build_dashboard_html(
        fig: go.Figure,
        yearly_wgs84: gpd.GeoDataFrame,
        hotspot_persistence_wgs84: gpd.GeoDataFrame,
        ) -> str:
    """Wrap the Plotly map with engagement UI: leaderboard and click details."""
    plot_html = fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        div_id="turnover-map",
        auto_play=False,
        config={"responsive": True, "displaylogo": False},
    )
    detail_payload = _build_detail_payload(yearly_wgs84)
    map_rows_payload = _build_map_rows_payload(yearly_wgs84)
    school_district_payload = _build_school_district_payload(yearly_wgs84)
    default_map_view = _build_default_map_view(fig)
    leaderboard_html = _build_leaderboard_html(hotspot_persistence_wgs84)
    initial_detail = _build_initial_detail_html(hotspot_persistence_wgs84)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hamilton County Turnover Hotspots</title>
    <style>
      :root {{
        --bg: #f4efe7;
        --panel: #fffaf2;
        --panel-strong: #f0e4d2;
        --text: #1f2a30;
        --muted: #68757f;
        --accent: #a63d40;
        --accent-dark: #7f1d1d;
        --line: #d8cfc0;
        --shadow: 0 18px 50px rgba(61, 44, 22, 0.10);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        color: var(--text);
        background:
          radial-gradient(circle at top left, rgba(166, 61, 64, 0.12), transparent 30%),
          linear-gradient(180deg, #f7f1e7 0%, #efe5d6 100%);
      }}
      .page {{
        max-width: 1480px;
        margin: 0 auto;
        padding: 34px 24px 42px;
      }}
      .hero {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 24px;
        align-items: end;
        margin-bottom: 22px;
      }}
      .eyebrow {{
        margin: 0 0 8px;
        font-size: 12px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--accent-dark);
      }}
      h1 {{
        margin: 0;
        font-size: clamp(2.1rem, 4vw, 4.4rem);
        line-height: 0.98;
      }}
      .lede {{
        max-width: 760px;
        margin: 14px 0 0;
        color: var(--muted);
        font-size: 1.05rem;
        line-height: 1.55;
      }}
      .method-card {{
        max-width: 360px;
        padding: 18px;
        border-radius: 20px;
        background: var(--panel);
        border: 1px solid rgba(103, 88, 63, 0.18);
        box-shadow: var(--shadow);
      }}
      .method-card strong {{
        display: block;
        margin-bottom: 6px;
      }}
      .method-card p {{
        margin: 0;
        color: var(--muted);
        line-height: 1.45;
      }}
      .dashboard-grid {{
        display: grid;
        grid-template-columns: minmax(340px, 0.38fr) minmax(520px, 1fr);
        gap: 22px;
        align-items: start;
      }}
      .side-panel,
      .map-panel {{
        background: var(--panel);
        border: 1px solid rgba(103, 88, 63, 0.18);
        border-radius: 24px;
        box-shadow: var(--shadow);
      }}
      .side-panel {{
        display: grid;
        gap: 18px;
        padding: 20px;
      }}
      .map-panel {{
        padding: 14px;
      }}
      .section-heading {{
        margin-bottom: 12px;
      }}
      .section-heading h2 {{
        margin: 0 0 6px;
        font-size: 1.35rem;
      }}
      .section-heading p {{
        margin: 0;
        color: var(--muted);
        line-height: 1.45;
      }}
      .detail-card {{
        padding: 18px;
        border-radius: 20px;
        color: white;
        background: linear-gradient(140deg, rgba(23, 50, 77, 0.96), rgba(42, 111, 151, 0.92));
      }}
      .detail-card h3 {{
        margin: 0 0 8px;
        font-size: 1.35rem;
      }}
      .detail-card p {{
        margin: 0 0 14px;
        color: rgba(255, 255, 255, 0.78);
      }}
      .metric-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }}
      .metric {{
        min-width: 0;
        padding: 11px 12px;
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.16);
      }}
      .metric span {{
        display: block;
        margin-bottom: 5px;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: rgba(255, 255, 255, 0.72);
      }}
      .metric strong {{
        font-size: 1rem;
      }}
      .leaderboard {{
        display: grid;
        gap: 10px;
      }}
      .leaderboard-row {{
        width: 100%;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 16px;
        align-items: center;
        padding: 16px;
        border: 1px solid var(--line);
        border-radius: 16px;
        background: linear-gradient(180deg, #fffdf9 0%, #fbf5ed 100%);
        color: inherit;
        font: inherit;
        text-align: left;
        cursor: pointer;
      }}
      .leaderboard-row:hover {{
        border-color: rgba(166, 61, 64, 0.45);
        background: #f8f0e5;
      }}
      .leaderboard-name {{
        display: block;
        min-width: 0;
        font-weight: 700;
        line-height: 1.25;
      }}
      .leaderboard-kpi {{
        text-align: right;
        white-space: nowrap;
      }}
      .leaderboard-kpi strong {{
        display: block;
        font-size: 1.55rem;
        line-height: 1;
        color: var(--accent-dark);
      }}
      .leaderboard-kpi span {{
        display: block;
        margin-top: 5px;
        color: var(--muted);
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}
      .map-controls {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
        justify-content: flex-end;
        margin: 0 0 10px;
      }}
      .year-filter {{
        position: relative;
        display: inline-block;
      }}
      .district-control,
      .year-dropdown-button {{
        min-height: 40px;
        padding: 9px 32px 9px 12px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: #fffdf8;
        color: var(--text);
        font: inherit;
        font-size: 0.94rem;
        cursor: pointer;
      }}
      .year-dropdown-button {{
        min-width: 148px;
        text-align: left;
      }}
      .year-dropdown-button::after {{
        content: "v";
        position: absolute;
        right: 12px;
        color: var(--muted);
      }}
      .year-dropdown {{
        position: absolute;
        z-index: 5;
        top: calc(100% + 6px);
        right: 0;
        min-width: 170px;
        display: grid;
        gap: 4px;
        padding: 8px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: #fffdf8;
        box-shadow: var(--shadow);
      }}
      .year-dropdown[hidden] {{
        display: none;
      }}
      .year-option {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        width: 100%;
        min-height: 34px;
        padding: 7px 8px;
        border: 0;
        border-radius: 8px;
        background: transparent;
        color: var(--text);
        font: inherit;
        font-size: 0.94rem;
        text-align: left;
        cursor: pointer;
      }}
      .year-option:hover,
      .year-option.is-selected {{
        background: rgba(191, 63, 120, 0.12);
      }}
      .year-option.is-selected::after {{
        content: "Selected";
        color: var(--accent-dark);
        font-size: 0.72rem;
        text-transform: uppercase;
      }}
      .toggle-control {{
        display: inline-flex;
        gap: 8px;
        align-items: center;
        padding: 10px 12px;
        border: 1px solid var(--line);
        border-radius: 999px;
        background: #fffdf8;
        color: var(--text);
        font-size: 0.94rem;
        cursor: pointer;
      }}
      .toggle-control input {{
        accent-color: var(--accent-dark);
      }}
      #turnover-map {{
        width: 100%;
        min-height: 760px;
      }}
      @media (max-width: 1100px) {{
        .hero,
        .dashboard-grid {{
          grid-template-columns: 1fr;
        }}
        .method-card {{
          max-width: none;
        }}
        #turnover-map {{
          min-height: 560px;
        }}
      }}
      @media (max-width: 640px) {{
        .page {{
          padding: 24px 14px 34px;
        }}
        .metric-grid {{
          grid-template-columns: 1fr;
        }}
        .leaderboard-row {{
          grid-template-columns: 1fr;
          gap: 10px;
        }}
        .leaderboard-kpi {{
          text-align: left;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="page">
      <section class="hero">
        <div>
          <p class="eyebrow">Turnover Hotspot Explorer</p>
          <h1>See where subdivision turnover persists over time.</h1>
          <p class="lede">
            Choose one or more years to compare annual turnover rates. Click a subdivision
            on the map or a leaderboard row to inspect the yearly details and persistent
            hotspot summary.
          </p>
        </div>
        <aside class="method-card">
          <strong>How hotspots are defined</strong>
          <p>
            A subdivision is a hotspot in a year when its turnover rate is above the
            configured quantile threshold and it meets the minimum housing stock filter.
          </p>
        </aside>
      </section>

      <section class="dashboard-grid">
        <aside class="side-panel">
          <div>
            <div class="section-heading">
              <h2>Selected Subdivision</h2>
              <p>Click the map or leaderboard to update this panel.</p>
            </div>
            <div id="subdivision-detail" class="detail-card">
              {initial_detail}
            </div>
          </div>
          <div>
            <div class="section-heading">
              <h2>Top 5 Persistent Hotspots</h2>
              <p>Ranked by number of years in the hotspot set.</p>
            </div>
            <div class="leaderboard">
              {leaderboard_html}
            </div>
          </div>
        </aside>

        <section class="map-panel">
          <div class="map-controls" aria-label="Map filters">
            <select id="school-district-select" class="district-control" aria-label="School district">
              <option value="">All school districts</option>
            </select>
            <div class="year-filter">
              <button id="year-filter-button" class="year-dropdown-button" type="button" aria-haspopup="listbox" aria-expanded="false">
                All years
              </button>
              <div id="year-dropdown" class="year-dropdown" role="listbox" aria-label="Map years" aria-multiselectable="true" hidden></div>
            </div>
            <label class="toggle-control" for="hotspots-only-toggle">
              <input id="hotspots-only-toggle" type="checkbox">
              Show hotspots only
            </label>
          </div>
          {plot_html}
        </section>
      </section>
    </main>

    <script>
      const turnoverDetails = {json.dumps(detail_payload, allow_nan=False)};
      const mapRowsByYear = {json.dumps(map_rows_payload, allow_nan=False)};
      const schoolDistricts = {json.dumps(school_district_payload, allow_nan=False)};
      const defaultMapView = {json.dumps(default_map_view, allow_nan=False)};
      const detailPanel = document.getElementById("subdivision-detail");
      const mapDiv = document.getElementById("turnover-map");
      const hotspotsOnlyToggle = document.getElementById("hotspots-only-toggle");
      const schoolDistrictSelect = document.getElementById("school-district-select");
      const yearFilterButton = document.getElementById("year-filter-button");
      const yearDropdown = document.getElementById("year-dropdown");
      const availableMapYears = Object.keys(mapRowsByYear)
        .sort((left, right) => Number(left) - Number(right));
      const HIGHLIGHT_TRACE_INDEX = 1;
      const MAIN_TRACE_INDEX = 0;
      let selectedPlanid = null;
      let currentMapYear = getInitialMapYear();
      let selectedMapYears = new Set();
      let selectedSchoolDistrict = "";
      const yearDropdownOptions = buildYearDropdown();

      function metric(label, value) {{
        return `<div class="metric"><span>${{escapeHtml(label)}}</span><strong>${{escapeHtml(value ?? "-")}}</strong></div>`;
      }}

      function renderDetail(planid, selectedYear = currentMapYear) {{
        selectedPlanid = String(planid);
        const detail = turnoverDetails[String(planid)];
        if (!detail) {{
          return;
        }}
        highlightSubdivision(planid);
        const yearly = selectedYear
          ? detail.yearly.find((row) => String(row.transfer_year) === String(selectedYear))
          : detail.yearly[0];
        const displayYearly = yearly || detail.yearly[0];
        const summary = detail.summary;
        detailPanel.innerHTML = `
          <h3>${{escapeHtml(summary.subdivision_label)}}</h3>
          <p>${{summary.hotspot_year_count}} persistent hotspot year(s): ${{escapeHtml(summary.hotspot_year_ranges)}}</p>
          <div class="metric-grid">
            ${{metric("Map Year", displayYearly?.transfer_year)}}
            ${{metric("Turnover", displayYearly ? `${{displayYearly.turnover_pct}}%` : "-")}}
            ${{metric("Parcels Sold", displayYearly?.parcels_sold)}}
            ${{metric("Housing Stock", displayYearly?.housing_stock)}}
            ${{metric("Hotspot This Year", displayYearly?.is_hotspot ? "Yes" : "No")}}
            ${{metric("Year Threshold", displayYearly ? `${{displayYearly.hotspot_threshold_pct}}%` : "-")}}
            ${{metric("Avg Hotspot Turnover", `${{summary.avg_turnover_pct}}%`)}}
            ${{metric("Plan ID", planid)}}
          </div>
        `;
      }}

      function getInitialMapYear() {{
        return availableMapYears[0] ?? null;
      }}

      function populateSchoolDistrictSelect() {{
        if (!schoolDistrictSelect) {{
          return;
        }}
        Object.entries(schoolDistricts)
          .sort(([, left], [, right]) => left.label.localeCompare(right.label))
          .forEach(([district, config]) => {{
            const option = document.createElement("option");
            option.value = district;
            option.textContent = config.label;
            schoolDistrictSelect.append(option);
          }});
      }}

      function zoomToSchoolDistrict(district) {{
        const config = schoolDistricts[district];
        const view = config ?? defaultMapView;
        Plotly.relayout(mapDiv, {{
          "map.center.lat": view.center.lat,
          "map.center.lon": view.center.lon,
          "map.zoom": view.zoom,
        }});
      }}

      function buildYearDropdown() {{
        if (!yearDropdown) {{
          return [];
        }}
        return availableMapYears.map((year) => {{
          const option = document.createElement("button");
          option.className = "year-option";
          option.type = "button";
          option.dataset.year = year;
          option.setAttribute("role", "option");
          option.textContent = year;
          yearDropdown.append(option);
          return option;
        }});
      }}

      function setYearDropdownOpen(isOpen) {{
        if (!yearDropdown || !yearFilterButton) {{
          return;
        }}
        yearDropdown.hidden = !isOpen;
        yearFilterButton.setAttribute("aria-expanded", String(isOpen));
      }}

      function mapRowsForSelection() {{
        let rows = aggregateSelectedYearRows();
        if (selectedSchoolDistrict) {{
          rows = rows.filter((row) => row.school_district === selectedSchoolDistrict);
        }}
        if (hotspotsOnlyToggle?.checked) {{
          return rows.filter((row) => row.is_hotspot);
        }}
        return rows;
      }}

      function aggregateSelectedYearRows() {{
        const groups = new Map();
        const selectedYears = selectedYearValues();
        for (const year of selectedYears) {{
          for (const row of mapRowsByYear[String(year)] ?? []) {{
            const planid = String(row.planid);
            if (!groups.has(planid)) {{
              groups.set(planid, {{
                ...row,
                transfer_year: selectedYearsLabel(),
                parcels_sold: 0,
                turnover_pct: 0,
                hotspot_threshold_pct: 0,
                is_hotspot: false,
                is_hotspot_label: "No",
                selected_year_count: 0,
              }});
            }}
            const group = groups.get(planid);
            group.parcels_sold += Number(row.parcels_sold) || 0;
            group.turnover_pct += Number(row.turnover_pct) || 0;
            group.hotspot_threshold_pct += Number(row.hotspot_threshold_pct) || 0;
            group.is_hotspot = group.is_hotspot || Boolean(row.is_hotspot);
            group.selected_year_count += 1;
          }}
        }}
        return Array.from(groups.values()).map((row) => ({{
          ...row,
          turnover_pct: roundMetric(row.turnover_pct / row.selected_year_count),
          hotspot_threshold_pct: roundMetric(row.hotspot_threshold_pct / row.selected_year_count),
          is_hotspot_label: row.is_hotspot ? "Yes" : "No",
        }}));
      }}

      function selectedYearValues() {{
        const values = Array.from(selectedMapYears);
        return values.length ? values : availableMapYears;
      }}

      function selectedYearsLabel() {{
        const years = selectedYearValues();
        if (years.length === availableMapYears.length) {{
          return "All";
        }}
        return years.join(", ");
      }}

      function roundMetric(value) {{
        return Math.round((Number(value) || 0) * 100) / 100;
      }}

      function rowCustomdata(rows) {{
        return rows.map((row) => [
          row.planid,
          row.subdivision_label,
          selectedYearsLabel(),
          row.housing_stock,
          row.parcels_sold,
          row.turnover_pct,
          row.hotspot_threshold_pct,
          row.is_hotspot_label,
          row.hotspot_year_count,
          row.hotspot_years,
          row.avg_turnover_pct,
        ]);
      }}

      function refreshMapTrace() {{
        const rows = mapRowsForSelection();
        const range = turnoverRange(rows);
        Plotly.restyle(
          mapDiv,
          {{
            locations: [rows.map((row) => row.planid)],
            z: [rows.map((row) => row.turnover_pct)],
            customdata: [rowCustomdata(rows)],
            zmin: [range.min],
            zmax: [range.max],
          }},
          [MAIN_TRACE_INDEX]
        );
        if (selectedPlanid) {{
          highlightSubdivision(selectedPlanid);
        }}
      }}

      function turnoverRange(rows) {{
        const values = rows
          .map((row) => Number(row.turnover_pct))
          .filter((value) => Number.isFinite(value));
        if (!values.length) {{
          return {{min: 0, max: 1}};
        }}
        const min = Math.min(...values);
        const max = Math.max(...values);
        return min === max ? {{min, max: min + 1}} : {{min, max}};
      }}

      function syncYearDropdown() {{
        if (yearFilterButton) {{
          const label = selectedYearsLabel();
          yearFilterButton.textContent = label === "All" ? "All years" : label;
          yearFilterButton.title = label === "All" ? "All years" : `Selected years: ${{label}}`;
        }}
        for (const option of yearDropdownOptions) {{
          const isSelected = selectedMapYears.has(String(option.dataset.year));
          option.classList.toggle("is-selected", isSelected);
          option.setAttribute("aria-selected", String(isSelected));
        }}
      }}

      function setMapYear(year, selected = true) {{
        currentMapYear = year;
        if (selected) {{
          selectedMapYears.add(String(year));
        }} else {{
          selectedMapYears.delete(String(year));
        }}
        syncYearDropdown();
        refreshMapTrace();
        if (selectedPlanid) {{
          renderDetail(selectedPlanid, currentMapYear);
        }}
      }}

      function isPlanVisible(planid) {{
        return mapRowsForSelection().some(
          (row) => String(row.planid) === String(planid)
        );
      }}

      function highlightSubdivision(planid) {{
        if (!mapDiv.data || mapDiv.data.length <= HIGHLIGHT_TRACE_INDEX) {{
          return;
        }}
        if (!isPlanVisible(planid)) {{
          clearSubdivisionHighlight();
          return;
        }}
        Plotly.restyle(
          mapDiv,
          {{
            locations: [[String(planid)]],
            z: [[1]],
          }},
          [HIGHLIGHT_TRACE_INDEX]
        );
      }}

      function clearSubdivisionHighlight() {{
        Plotly.restyle(
          mapDiv,
          {{
            locations: [[]],
            z: [[]],
          }},
          [HIGHLIGHT_TRACE_INDEX]
        );
      }}

      function escapeHtml(value) {{
        return String(value)
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      }}

      mapDiv.on("plotly_click", (event) => {{
        const point = event.points?.[0];
        if (!point || !point.customdata) {{
          return;
        }}
        renderDetail(point.customdata[0], currentMapYear);
      }});

      populateSchoolDistrictSelect();
      schoolDistrictSelect?.addEventListener("change", () => {{
        selectedSchoolDistrict = schoolDistrictSelect.value;
        refreshMapTrace();
        zoomToSchoolDistrict(selectedSchoolDistrict);
      }});
      hotspotsOnlyToggle?.addEventListener("change", refreshMapTrace);
      yearFilterButton?.addEventListener("click", () => {{
        setYearDropdownOpen(yearDropdown?.hidden !== false);
      }});
      document.addEventListener("click", (event) => {{
        if (!event.target.closest(".year-filter")) {{
          setYearDropdownOpen(false);
        }}
      }});
      for (const option of yearDropdownOptions) {{
        option.addEventListener("click", () => {{
          setMapYear(option.dataset.year, !selectedMapYears.has(String(option.dataset.year)));
        }});
      }}
      syncYearDropdown();
      refreshMapTrace();

      for (const row of document.querySelectorAll("[data-planid]")) {{
        row.addEventListener("click", () => renderDetail(row.dataset.planid, currentMapYear));
      }}
    </script>
  </body>
</html>
"""


def _build_detail_payload(yearly_wgs84: gpd.GeoDataFrame) -> dict[str, dict[str, object]]:
    """Create compact JSON used by the dashboard detail panel."""
    details = {}
    for planid, group in yearly_wgs84.sort_values("transfer_year").groupby("planid"):
        first = group.iloc[0]
        details[str(planid)] = {
            "summary": {
                "subdivision_label": str(first["subdivision_label"]),
                "hotspot_year_count": int(first["hotspot_year_count"]),
                "hotspot_years": str(first["hotspot_years"]),
                "hotspot_year_ranges": _format_year_ranges(first["hotspot_years"]),
                "avg_turnover_pct": _json_number(first["avg_turnover_pct"]),
            },
            "yearly": [
                {
                    "transfer_year": int(row["transfer_year"]),
                    "housing_stock": int(row["housing_stock"]),
                    "parcels_sold": int(row["parcels_sold"]),
                    "turnover_pct": _json_number(row["turnover_pct"]),
                    "hotspot_threshold_pct": _json_number(row["hotspot_threshold_pct"]),
                    "is_hotspot": bool(row["is_hotspot"]),
                }
                for _, row in group.iterrows()
            ],
        }
    return details


def _build_map_rows_payload(yearly_wgs84: gpd.GeoDataFrame) -> dict[str, list[dict[str, object]]]:
    """Create year-keyed map rows used by the hotspot-only toggle."""
    rows_by_year: dict[str, list[dict[str, object]]] = {}
    for year, group in yearly_wgs84.sort_values(["transfer_year", "planid"]).groupby("transfer_year"):
        rows_by_year[str(int(year))] = [
            {
                "planid": str(row["planid"]),
                "subdivision_label": str(row["subdivision_label"]),
                "school_district": _school_district(row),
                "transfer_year": int(row["transfer_year"]),
                "housing_stock": int(row["housing_stock"]),
                "parcels_sold": int(row["parcels_sold"]),
                "turnover_pct": _json_number(row["turnover_pct"]),
                "hotspot_threshold_pct": _json_number(row["hotspot_threshold_pct"]),
                "is_hotspot_label": str(row["is_hotspot_label"]),
                "is_hotspot": bool(row["is_hotspot"]),
                "hotspot_year_count": int(row["hotspot_year_count"]),
                "hotspot_years": str(row["hotspot_years"]),
                "avg_turnover_pct": _json_number(row["avg_turnover_pct"]),
            }
            for _, row in group.iterrows()
        ]
    return rows_by_year


def _build_school_district_payload(yearly_wgs84: gpd.GeoDataFrame) -> dict[str, dict[str, object]]:
    """Create school-district map centers and zoom levels for the district dropdown."""
    if "school_district" not in yearly_wgs84.columns:
        return {}

    district_rows = yearly_wgs84.dropna(subset=["school_district"]).copy()
    if district_rows.empty:
        return {}

    district_rows["school_district"] = district_rows["school_district"].astype(str).str.strip()
    district_rows = district_rows[district_rows["school_district"] != ""]
    if district_rows.empty:
        return {}

    payload: dict[str, dict[str, object]] = {}
    for district, group in district_rows.groupby("school_district"):
        district_geometries = group.drop_duplicates("planid")
        min_lon, min_lat, max_lon, max_lat = district_geometries.total_bounds
        center = district_geometries.geometry.union_all().centroid
        payload[str(district)] = {
            "label": str(district),
            "center": {
                "lat": _json_coordinate(center.y),
                "lon": _json_coordinate(center.x),
            },
            "zoom": _estimate_map_zoom(min_lon, min_lat, max_lon, max_lat),
        }
    return payload


def _build_default_map_view(fig: go.Figure) -> dict[str, object]:
    """Return the map view used when clearing school-district filtering."""
    try:
        center = fig.layout.map.center
        zoom = fig.layout.map.zoom
        lat = center.lat
        lon = center.lon
    except AttributeError:
        lat = 0
        lon = 0
        zoom = 10.5

    return {
        "center": {
            "lat": _json_coordinate(lat),
            "lon": _json_coordinate(lon),
        },
        "zoom": _json_number(zoom if zoom is not None else 10.5),
    }


def _estimate_map_zoom(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> float:
    """Estimate a Plotly map zoom that frames a WGS84 bounding box."""
    span = max(abs(max_lon - min_lon), abs(max_lat - min_lat), 0.001)
    zoom = np.log2(360 / span) - 2.2
    return round(float(np.clip(zoom, 9, 13.5)), 2)


def _build_initial_detail_html(
        hotspot_persistence_wgs84: gpd.GeoDataFrame,
        ) -> str:
    """Render the initial detail card content."""
    if hotspot_persistence_wgs84.empty:
        return """
          <h3>No persistent hotspots</h3>
          <p>No subdivision matched the current hotspot criteria.</p>
          <div class="metric-grid">
            <div class="metric"><span>Try</span><strong>Lower threshold</strong></div>
            <div class="metric"><span>Or</span><strong>Broader years</strong></div>
          </div>
        """

    top = (
        hotspot_persistence_wgs84
        .sort_values(["hotspot_year_count", "avg_turnover_pct"], ascending=[False, False])
        .iloc[0]
    )
    label = escape(_subdivision_label(top))
    compact_years = escape(_format_year_ranges(top["hotspot_years"]))
    return f"""
      <h3>{label}</h3>
      <p>{int(top['hotspot_year_count'])} persistent hotspot year(s): {compact_years}</p>
      <div class="metric-grid">
        <div class="metric"><span>Avg Hotspot Turnover</span><strong>{float(top['avg_turnover_pct']):.2f}%</strong></div>
        <div class="metric"><span>Plan ID</span><strong>{escape(str(top['planid']))}</strong></div>
      </div>
    """


def _build_leaderboard_html(
        hotspot_persistence_wgs84: gpd.GeoDataFrame,
        *,
        limit: int = 5,
        ) -> str:
    """Render ranked persistent hotspots for the dashboard side panel."""
    if hotspot_persistence_wgs84.empty:
        return """
          <div class="leaderboard-row">
            <strong class="leaderboard-name">No hotspots found</strong>
            <span class="leaderboard-kpi">
              <strong>-</strong>
              <span>avg turnover</span>
            </span>
          </div>
        """

    ranked = (
        hotspot_persistence_wgs84
        .sort_values(["hotspot_year_count", "avg_turnover_pct"], ascending=[False, False])
        .head(limit)
    )
    rows = []
    for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
        planid = escape(str(row['planid']))
        label = escape(_subdivision_label(row))
        rows.append(
            f"""
            <button class="leaderboard-row" type="button" data-planid="{planid}">
              <strong class="leaderboard-name">{label}</strong>
              <span class="leaderboard-kpi">
                <strong>{float(row['avg_turnover_pct']):.2f}%</strong>
                <span>avg turnover</span>
              </span>
            </button>
            """
        )
    return "\n".join(rows)


def _format_year_ranges(hotspot_years) -> str:
    """Compact comma-separated years into ranges for dense UI cards."""
    if hotspot_years is None or pd.isna(hotspot_years):
        return "None"

    years = []
    for year in str(hotspot_years).split(","):
        year = year.strip()
        if not year:
            continue
        try:
            years.append(int(year))
        except ValueError:
            return str(hotspot_years)

    if not years:
        return "None"

    years = sorted(set(years))
    ranges = []
    start = previous = years[0]
    for year in years[1:]:
        if year == previous + 1:
            previous = year
            continue
        ranges.append(_format_year_range(start, previous))
        start = previous = year
    ranges.append(_format_year_range(start, previous))
    return ", ".join(ranges)


def _format_year_range(start: int, end: int) -> str:
    if start == end:
        return str(start)
    return f"{start}-{end}"


def _subdivision_label(row) -> str:
    name = _subdivision_name(row)
    if name:
        return name
    return f"Subdivision {row.get('planid')}"


def _subdivision_name(row) -> str | None:
    value = row.get("subdivision_name") if hasattr(row, "get") else None
    if value is None or pd.isna(value):
        return None
    name = str(value).strip()
    return name or None


def _school_district(row) -> str:
    value = row.get("school_district") if hasattr(row, "get") else None
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _json_number(value) -> float:
    """Return finite floats for JSON serialization."""
    if value is None or pd.isna(value):
        return 0.0
    return round(float(value), 2)


def _json_coordinate(value) -> float:
    """Return finite coordinate floats without over-rounding map centers."""
    if value is None or pd.isna(value):
        return 0.0
    return round(float(value), 6)

def main():
    """Build the hotspot persistence dataset end to end and export the map."""
    config = load_config(
        start_year=2020, 
        end_year=2025, 
        use='510',
        min_housing_stock=30,
        hotspot_quantile=0.90,
        output_path="persistent_hotspots_map.html"
        )
    
    # Get Data
    parcel_sales_gdf = query_supabase(
        query=build_parcel_sales_query(
            use=config.use, 
            start_year=config.start_year, 
            end_year=config.end_year
            ), 
        database_url=config.database_url, 
        geom_col="centroid"
        )

    all_parcels_gdf = query_supabase(
        query=build_all_parcel_query(use=config.use), 
        database_url=config.database_url, 
        geom_col="centroid"
        )

    # Prepare Data
    parcel_sales_gdf = prepare_sales_data(parcel_sales_gdf, int64_list)

    # Creating subdivision grid for plotting visuals
    subdivision_grid_gdf = build_subdivision_grid(
        gdf=parcel_sales_gdf, 
        subdivision_id_col = "planid",
        gpd_cols=["planid","subdivision_name","school_district","subdivision_geom"],
        geom_col="subdivision_geom"
        )

    # Reducing the GeoDataFrame to just the columns needed.
    parcel_sales_points_gdf = gpd.GeoDataFrame(
        parcel_sales_gdf[core_cols], 
        geometry='centroid', 
        crs='4326'
        )

    # Combining the reduced sales GeoDataFrame with the 
    all_parcels_points_grid_gdf = gpd.sjoin(
        all_parcels_gdf,
        subdivision_grid_gdf,
        how="left",
        predicate="within",
    )

    # Getting the counts of all the sold parcels
    all_parcel_counts = get_counts(
        gdf = all_parcels_points_grid_gdf,
        group_list = ["planid"],
        counting_col="parcelid",
        count_col_name="housing_stock")

    # Adding the counts of the subdivisions.
    subdivision_grid_gdf = (
        subdivision_grid_gdf
        .merge(all_parcel_counts,
            on="planid", 
                how="left")
        )

    # Filling all nan's with 0 and making them integer types.
    subdivision_grid_gdf["housing_stock"] = (
        subdivision_grid_gdf["housing_stock"]
        .fillna(0)
        .astype(int)
    )

    sales_stock_by_year = create_sales_stock_by_year(
        parcel_sales_points_gdf, 
        subdivision_grid_gdf, 
        config.hotspot_quantile,
        config.min_housing_stock,
        )

    hotspot_persistence_wgs84, center = create_hotspot_persistence_wgs84(sales_stock_by_year)

    create_persistence_map(
        hotspot_persistence_wgs84,
        center,
        config.output_path,
        sales_stock_by_year,
    )

if __name__ == "__main__":
    main()
