"""
Fetch all raw source data for the Bentonville digital twin.

Sources (all public, verified 2026-07-15):
  - City of Bentonville ArcGIS Server: street centerlines, land use,
    FEMA flood hazard, traffic counts
  - US Census: ACS 5-year block-group median year built + population,
    TIGERweb block-group geometries

Outputs raw GeoJSON to data/raw/ (gitignored cache). Run:
    python -m etl.fetch
"""

import json
import os
from pathlib import Path

import httpx

from etl.arcgis import fetch_layer_geojson, save_geojson

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
CITY = "https://gis.bentonvillear.com/arcgis/rest/services"

# Study-area envelope: Bentonville + margin (WGS84)
BBOX = (-94.35, 36.26, -94.10, 36.46)

# name -> (layer_url, out_fields, bbox_or_None)
CITY_LAYERS = {
    "centerlines": (
        f"{CITY}/Transportation/NewWorldCenterlines18/MapServer/0",
        "OBJECTID,FullStreetName,StreetName,FUNC_CLASS,ROAD_DESIGN,MPH,LANES,OWNERSHIP,LPostalCity",
        None,  # county dispatch layer; clipped later during network build
    ),
    "land_use": (
        f"{CITY}/Planning/Land_Use_2025/FeatureServer/0",
        "OBJECTID,MapLabel,subtyplabel",
        None,
    ),
    # Current (March 2022) FEMA layers hosted by the city. Envelope filter keeps
    # these county-wide queries cheap — the unfiltered 500-yr query overloads the
    # city's web adaptor, which then serves HTML error pages.
    "flood_sfha": (f"{CITY}/Stormwater/FEMA_DATA/MapServer/44", "*", BBOX),
    "flood_500yr": (f"{CITY}/Stormwater/FEMA_DATA/MapServer/62", "*", BBOX),
    "traffic_counts": (
        f"{CITY}/Planning/2025_Traffic_Counts/MapServer/0",
        "OBJECTID,MostRecentADT,FunctionalClass,Route,TruckPercent",
        BBOX,  # statewide ARDOT layer
    ),
    "addresses": (
        f"{CITY}/Planning/Bentonville_Addresses23/FeatureServer/2",
        "OBJECTID",
        BBOX,  # geometry-only: used as service-connection density for demand
    ),
}

# Benton County, AR
STATE_FIPS = "05"
COUNTY_FIPS = "007"
ACS_YEAR = 2023
ACS_URL = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
# TIGERweb current block groups (layer id verified at runtime)
TIGERWEB_BG = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer"


def fetch_city_layers() -> None:
    for name, (url, fields, bbox) in CITY_LAYERS.items():
        out = RAW_DIR / f"{name}.geojson"
        if out.exists():
            print(f"  {name}: cached, skipping")
            continue
        print(f"  fetching {name} ...")
        fc = fetch_layer_geojson(url, out_fields=fields, bbox=bbox)
        save_geojson(fc, out)


def _find_block_group_layer(client: httpx.Client) -> str:
    """Locate the Block Groups layer id in TIGERweb (ids shift between releases)."""
    resp = client.get(f"{TIGERWEB_BG}?f=json")
    resp.raise_for_status()
    for layer in resp.json().get("layers", []):
        if layer["name"].strip().lower() == "census block groups":
            return f"{TIGERWEB_BG}/{layer['id']}"
    raise RuntimeError("Census Block Groups layer not found in TIGERweb service")


def fetch_acs_block_groups() -> None:
    """Block-group geometries joined with ACS median year built + population.

    Requires CENSUS_API_KEY (free: https://api.census.gov/data/key_signup.html).
    The Census API no longer serves keyless requests. When the key is absent the
    network builder falls back to a distance-from-downtown vintage heuristic.
    """
    out = RAW_DIR / "acs_block_groups.geojson"
    if out.exists():
        print("  acs_block_groups: cached, skipping")
        return
    api_key = os.environ.get("CENSUS_API_KEY")
    if not api_key:
        print("  ⚠️ CENSUS_API_KEY not set — skipping ACS (vintage heuristic will be used)")
        return

    with httpx.Client(timeout=60.0) as client:
        # 1. ACS attributes: B25035_001E = median year structure built,
        #    B01003_001E = total population
        print("  fetching ACS attributes ...")
        resp = client.get(
            ACS_URL,
            params={
                "get": "B25035_001E,B01003_001E",
                "for": "block group:*",
                "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS} tract:*",
                "key": api_key,
            },
        )
        resp.raise_for_status()
        rows = resp.json()
        header, data_rows = rows[0], rows[1:]
        idx = {name: i for i, name in enumerate(header)}
        acs: dict[str, dict] = {}
        for r in data_rows:
            geoid = (
                r[idx["state"]] + r[idx["county"]] + r[idx["tract"]] + r[idx["block group"]]
            )
            year_built = float(r[idx["B25035_001E"]] or 0)
            acs[geoid] = {
                # ACS uses 0 / negative sentinels for suppressed values
                "median_year_built": int(year_built) if year_built > 1900 else None,
                "population": int(float(r[idx["B01003_001E"]] or 0)),
            }
        print(f"  ACS rows: {len(acs)}")

        # 2. Geometries from TIGERweb
        bg_layer = _find_block_group_layer(client)
        print(f"  fetching block-group geometries from {bg_layer} ...")

    fc = fetch_layer_geojson(
        bg_layer,
        where=f"STATE='{STATE_FIPS}' AND COUNTY='{COUNTY_FIPS}'",
        out_fields="GEOID,STATE,COUNTY,TRACT,BLKGRP",
    )
    # 3. Join
    matched = 0
    for feat in fc["features"]:
        geoid = feat["properties"].get("GEOID", "")
        attrs = acs.get(geoid)
        if attrs:
            feat["properties"].update(attrs)
            matched += 1
    print(f"  joined ACS attrs onto {matched}/{len(fc['features'])} block groups")
    save_geojson(fc, out)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("== City of Bentonville ArcGIS layers ==")
    fetch_city_layers()
    print("== Census ACS block groups ==")
    fetch_acs_block_groups()
    print("done.")


if __name__ == "__main__":
    main()
