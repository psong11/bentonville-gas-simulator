"""
Minimal ArcGIS REST client for the ETL pipeline.

Fetches complete layers as GeoJSON (WGS84) with resultOffset pagination.
No runtime dependency: this module is only used by the offline ETL scripts.
"""

import json
import random
import subprocess
import time
import urllib.parse
from pathlib import Path

import httpx

DEFAULT_TIMEOUT = 120.0
PAGE_SLEEP_S = 0.25  # be polite to the city's server
MAX_RETRIES = 2


def _get_json_with_retry(client: httpx.Client, url: str, params: dict) -> dict:
    """GET with retries; ArcGIS servers intermittently return HTML error pages."""
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except (json.JSONDecodeError, httpx.HTTPError) as e:
            last_err = e
            body = getattr(resp, "content", b"")[:200] if "resp" in dir() else b""
            wait = 5 * 2**attempt + random.uniform(0, 3)
            print(
                f"    retry {attempt + 1}/{MAX_RETRIES} after {wait:.0f}s "
                f"({type(e).__name__}; body starts: {body!r})"
            )
            time.sleep(wait)
    # Last resort: the city's web adaptor sometimes serves HTML error pages to
    # httpx while identical curl requests succeed. Shell out once before giving up.
    try:
        return _get_json_via_curl(url, params)
    except Exception:
        raise RuntimeError(f"Failed after {MAX_RETRIES} retries: {url}") from last_err


def _get_json_via_curl(url: str, params: dict) -> dict:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    print("    falling back to curl ...")
    out = subprocess.run(
        ["curl", "-sS", "--max-time", "180", full_url],
        capture_output=True,
        check=True,
    )
    return json.loads(out.stdout)


def fetch_layer_geojson(
    layer_url: str,
    where: str = "1=1",
    out_fields: str = "*",
    page_size: int = 500,
    max_features: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> dict:
    """Fetch every feature of an ArcGIS layer as a WGS84 GeoJSON FeatureCollection.

    layer_url: e.g. https://host/arcgis/rest/services/Folder/Service/MapServer/0
    bbox: optional (xmin, ymin, xmax, ymax) WGS84 envelope filter. Keeps queries
          cheap on layers that extend far beyond the study area.
    """
    features: list[dict] = []
    offset = 0
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        while True:
            params = {
                "where": where,
                "outFields": out_fields,
                "outSR": 4326,
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": page_size,
            }
            if bbox:
                params.update(
                    geometry=json.dumps(
                        {
                            "xmin": bbox[0],
                            "ymin": bbox[1],
                            "xmax": bbox[2],
                            "ymax": bbox[3],
                            "spatialReference": {"wkid": 4326},
                        }
                    ),
                    geometryType="esriGeometryEnvelope",
                    inSR=4326,
                    spatialRel="esriSpatialRelIntersects",
                )
            data = _get_json_with_retry(client, f"{layer_url}/query", params)
            if "error" in data:
                raise RuntimeError(f"ArcGIS error from {layer_url}: {data['error']}")
            page = data.get("features", [])
            features.extend(page)
            if max_features and len(features) >= max_features:
                features = features[:max_features]
                break
            # exceededTransferLimit is the reliable "more pages" signal
            if not (data.get("exceededTransferLimit") or data.get("properties", {}).get("exceededTransferLimit")):
                if len(page) < page_size:
                    break
            if not page:
                break
            offset += len(page)
            time.sleep(PAGE_SLEEP_S)
    return {"type": "FeatureCollection", "features": features}


def save_geojson(collection: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(collection, f)
    size_mb = path.stat().st_size / 1e6
    print(f"  wrote {path} ({len(collection['features'])} features, {size_mb:.1f} MB)")
