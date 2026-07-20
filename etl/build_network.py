"""
Build the street-true Bentonville gas distribution network from raw GIS data.

Input:  data/raw/*.geojson  (produced by `python -m etl.fetch`)
Output: data/network.json   (GasNode/GasPipe schema consumed by the API)
        data/overlays/flood.geojson (map overlay, clipped + thinned)

The network is SYNTHETIC BUT STREET-TRUE: real gas distribution maps are
non-public for security reasons, so mains are routed along real street
centerlines with demand derived from real land use and address density,
and attributes (diameter, material, vintage) assigned from documented
heuristics. It is a planning/simulation artifact, not utility as-builts.

Run: python -m etl.build_network
"""

import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
OUT_NETWORK = Path(__file__).parent.parent / "data" / "network.json"
OUT_OVERLAYS = Path(__file__).parent.parent / "data" / "overlays"

DOWNTOWN_SQUARE = (-94.20882, 36.37285)  # Bentonville square
BBOX = (-94.35, 36.26, -94.10, 36.46)
SEED = 42

# Approximate city-gate supply points (transmission -> distribution).
# Placed near arterial corridors at the city periphery; real city gate
# locations are not public. See docs/REVAMP_PLAN.md.
CITY_GATES = [
    {"near": (-94.2000, 36.3330), "name": "City Gate South (approx.)"},
    {"near": (-94.1850, 36.3950), "name": "City Gate Northeast (approx.)"},
    {"near": (-94.2600, 36.3700), "name": "City Gate West (approx.)"},
]

SNAP_DECIMALS = 5          # ~1.1 m endpoint snapping
LEAF_PRUNE_M = 120.0       # drop dead-end stubs shorter than this
MIN_EDGE_M = 12.0          # contract micro-edges (traffic-circle connectors)
MIN_MPH_KEEP = 15          # drop alleys / parking aisles (MPH 5/10) unless named arterialish


# ---------------------------------------------------------------- geometry --

def haversine_m(a: tuple, b: tuple) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(h))


def path_length_m(path: list) -> float:
    return sum(haversine_m(path[i], path[i + 1]) for i in range(len(path) - 1))


def point_in_ring(x: float, y: float, ring: list) -> bool:
    """Even-odd ray casting for one linear ring."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


class PolygonIndex:
    """Point-in-polygon over a GeoJSON FeatureCollection with bbox prefilter."""

    def __init__(self, collection: dict, label_fn):
        self.entries = []
        for feat in collection["features"]:
            geom = feat.get("geometry")
            if not geom:
                continue
            polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            label = label_fn(feat["properties"])
            for rings in polys:
                xs = [p[0] for p in rings[0]]
                ys = [p[1] for p in rings[0]]
                self.entries.append((min(xs), min(ys), max(xs), max(ys), rings, label))

    def query(self, x: float, y: float):
        for xmin, ymin, xmax, ymax, rings, label in self.entries:
            if not (xmin <= x <= xmax and ymin <= y <= ymax):
                continue
            # even-odd across all rings handles holes
            crossings = sum(point_in_ring(x, y, ring) for ring in rings)
            if crossings % 2 == 1:
                return label
        return None


# ------------------------------------------------------------ street graph --

def road_class(props: dict) -> str:
    mph = props.get("MPH") or 25
    if props.get("ROAD_DESIGN") == "Dual Carriageway" or mph >= 40 or (props.get("LANES") or 2) >= 4:
        return "arterial"
    if mph >= 30:
        return "collector"
    return "local"


def load_street_graph() -> nx.Graph:
    data = json.load(open(RAW_DIR / "centerlines.geojson"))
    def in_bbox(coords):
        return all(
            BBOX[0] <= x <= BBOX[2] and BBOX[1] <= y <= BBOX[3]
            for x, y in (coords[0], coords[-1])
        )

    segments = [
        f for f in data["features"]
        if f["properties"].get("LPostalCity") == "BENTONVILLE"
        and f.get("geometry")
        and (f["properties"].get("MPH") or 25) >= MIN_MPH_KEEP
        and in_bbox(f["geometry"]["coordinates"])
    ]
    G = nx.Graph()
    for f in segments:
        coords = f["geometry"]["coordinates"]
        props = f["properties"]
        a = (round(coords[0][0], SNAP_DECIMALS), round(coords[0][1], SNAP_DECIMALS))
        b = (round(coords[-1][0], SNAP_DECIMALS), round(coords[-1][1], SNAP_DECIMALS))
        if a == b:
            continue
        length = path_length_m(coords)
        cls = road_class(props)
        street = (props.get("FullStreetName") or "Unnamed").strip() or "Unnamed"
        if G.has_edge(a, b):
            continue
        G.add_edge(a, b, path=[list(c) for c in coords], length=length, street=street, cls=cls)

    # largest connected component only
    G = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    return G


CLASS_RANK = {"arterial": 0, "collector": 1, "local": 2}


def contract_degree2(G: nx.Graph) -> nx.Graph:
    """Merge chains through degree-2 nodes, preserving path geometry."""
    changed = True
    while changed:
        changed = False
        for node in list(G.nodes):
            if G.degree(node) != 2:
                continue
            (n1, d1), (n2, d2) = ((nbr, G.edges[node, nbr]) for nbr in G.neighbors(node))
            if n1 == n2 or G.has_edge(n1, n2):
                continue
            p1 = d1["path"] if d1["path"][-1] == list(node) else d1["path"][::-1]
            p2 = d2["path"] if d2["path"][0] == list(node) else d2["path"][::-1]
            # dominant street name = the longer piece; class = higher rank
            street = d1["street"] if d1["length"] >= d2["length"] else d2["street"]
            cls = min((d1["cls"], d2["cls"]), key=lambda c: CLASS_RANK[c])
            G.add_edge(
                n1, n2,
                path=p1 + p2[1:],
                length=d1["length"] + d2["length"],
                street=street,
                cls=cls,
            )
            G.remove_node(node)
            changed = True
    return G


def contract_micro_edges(G: nx.Graph, min_len: float) -> nx.Graph:
    """Merge endpoints of edges shorter than min_len (roundabout connectors)."""
    changed = True
    while changed:
        changed = False
        for a, b, d in list(G.edges(data=True)):
            if d["length"] >= min_len or not (G.has_node(a) and G.has_node(b)):
                continue
            if not G.has_edge(a, b):
                continue
            G = nx.contracted_nodes(G, a, b, self_loops=False, copy=False)
            changed = True
    # contracted_nodes stores merge history in a 'contraction' attr; drop it
    for _, data in G.nodes(data=True):
        data.pop("contraction", None)
    for _, _, data in G.edges(data=True):
        data.pop("contraction", None)
    return G


def prune_stubs(G: nx.Graph, min_len: float) -> nx.Graph:
    changed = True
    while changed:
        changed = False
        for node in list(G.nodes):
            if G.degree(node) == 1:
                nbr = next(iter(G.neighbors(node)))
                if G.edges[node, nbr]["length"] < min_len:
                    G.remove_node(node)
                    changed = True
    return G


# ------------------------------------------------------------- attribution --

LANDUSE_TO_TYPE = [
    ("Industry", "industrial"),
    ("Center", "commercial"),
    ("Corridor", "commercial"),
    ("Civic", "commercial"),
    ("Neighborhood", "residential"),
]


def landuse_type(label: str | None) -> str:
    if label:
        for key, ntype in LANDUSE_TO_TYPE:
            if key in label:
                return ntype
    return "residential"


def load_acs_index() -> "PolygonIndex | None":
    """ACS block groups (median year built), present when fetched with a key."""
    path = RAW_DIR / "acs_block_groups.geojson"
    if not path.exists():
        return None
    return PolygonIndex(
        json.load(open(path)), lambda p: p.get("median_year_built")
    )


def vintage_year(node_xy: tuple, rng: random.Random, acs: "PolygonIndex | None" = None) -> int:
    """Pipe vintage: ACS block-group median year built (±6 yr noise) when
    available, else growth-ring heuristic (Bentonville grew outward from
    the square)."""
    if acs is not None:
        median = acs.query(*node_xy)
        if median:
            return max(1935, min(2024, int(rng.gauss(median, 6))))
    d_km = haversine_m(node_xy, DOWNTOWN_SQUARE) / 1000
    if d_km < 1.2:
        base, spread = 1958, 14
    elif d_km < 2.5:
        base, spread = 1977, 12
    elif d_km < 4.5:
        base, spread = 1996, 10
    else:
        base, spread = 2010, 8
    return max(1935, min(2024, int(rng.gauss(base, spread))))


def material_for_year(year: int, rng: random.Random) -> str:
    if year < 1970:
        return rng.choices(["steel", "ductile_iron"], [0.7, 0.3])[0]
    if year < 1995:
        return rng.choices(["steel", "polyethylene"], [0.5, 0.5])[0]
    return rng.choices(["polyethylene", "steel"], [0.9, 0.1])[0]


ROUGHNESS = {"steel": 4.5e-05, "ductile_iron": 2.5e-05, "polyethylene": 7e-06, "pvc": 5e-06}
DIAMETER_BY_CLASS = {"arterial": (0.30, 0.40), "collector": (0.15, 0.25), "local": (0.08, 0.12)}


class GridCounter:
    """Counts points near a location using coarse spatial binning."""

    def __init__(self, points: list, cell_deg: float = 0.002):
        self.cell = cell_deg
        self.bins: dict = defaultdict(int)
        for x, y in points:
            self.bins[(int(x / cell_deg), int(y / cell_deg))] += 1

    def count_near(self, x: float, y: float) -> int:
        cx, cy = int(x / self.cell), int(y / self.cell)
        return sum(self.bins.get((cx + dx, cy + dy), 0) for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def demand_for(ntype: str, n_addr: int, rng: random.Random) -> float:
    if ntype == "industrial":
        return round(rng.uniform(80, 250), 2)
    if ntype == "commercial":
        return round(max(2, n_addr) * rng.uniform(1.5, 4.0), 2)
    return round(max(1, n_addr) * rng.uniform(0.4, 0.9), 2)


# -------------------------------------------------------------------- main --

def build() -> dict:
    rng = random.Random(SEED)
    print("loading street graph ...")
    G = load_street_graph()
    print(f"  raw junction graph: {G.number_of_nodes()} nodes / {G.number_of_edges()} edges")
    G = contract_micro_edges(G, MIN_EDGE_M)
    G = contract_degree2(G)
    G = prune_stubs(G, LEAF_PRUNE_M)
    G = contract_degree2(G)
    G = contract_micro_edges(G, MIN_EDGE_M)
    G = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    print(f"  simplified: {G.number_of_nodes()} nodes / {G.number_of_edges()} edges")

    print("loading attribution layers ...")
    landuse = PolygonIndex(
        json.load(open(RAW_DIR / "land_use.geojson")), lambda p: p.get("MapLabel")
    )
    sfha = PolygonIndex(json.load(open(RAW_DIR / "flood_sfha.geojson")), lambda p: "100yr")
    f500 = PolygonIndex(json.load(open(RAW_DIR / "flood_500yr.geojson")), lambda p: "500yr")
    addr_pts = []
    for f in json.load(open(RAW_DIR / "addresses.geojson"))["features"]:
        if f.get("geometry"):
            addr_pts.append(tuple(f["geometry"]["coordinates"][:2]))
    addr_grid = GridCounter(addr_pts)
    traffic = [
        (tuple(f["geometry"]["coordinates"][:2]), f["properties"].get("MostRecentADT") or 0)
        for f in json.load(open(RAW_DIR / "traffic_counts.geojson"))["features"]
        if f.get("geometry")
    ]
    acs = load_acs_index()
    print(f"  vintage source: {'ACS median year built' if acs else 'growth-ring heuristic'}")

    # --- nodes ---
    print("attributing nodes ...")
    node_ids = {xy: i for i, xy in enumerate(G.nodes)}
    nodes = []
    for xy, nid in node_ids.items():
        lu = landuse.query(*xy)
        ntype = landuse_type(lu)
        n_addr = addr_grid.count_near(*xy)
        street_names = [G.edges[e]["street"] for e in G.edges(xy)]
        main_street = Counter(s for s in street_names if s != "Unnamed").most_common(1)
        label = main_street[0][0] if main_street else "Unnamed"
        nodes.append({
            "id": nid,
            "node_type": ntype,
            "x": xy[0],
            "y": xy[1],
            "base_demand": demand_for(ntype, n_addr, rng),
            "elevation": round(rng.uniform(390, 410), 1),
            "name": f"{label} junction",
            "street": label,
            "land_use": lu,
            "n_addresses": n_addr,
        })

    # --- city gates: convert nearest arterial-touching node to a source ---
    for gate in CITY_GATES:
        candidates = [
            xy for xy in G.nodes
            if any(G.edges[e]["cls"] in ("arterial", "collector") for e in G.edges(xy))
        ]
        nearest = min(candidates, key=lambda xy: haversine_m(xy, gate["near"]))
        n = nodes[node_ids[nearest]]
        n["node_type"] = "source"
        n["base_demand"] = 0.0
        n["name"] = gate["name"]

    # --- pipes ---
    print("attributing pipes ...")
    pipes = []
    for pid, (a, b) in enumerate(G.edges):
        d = G.edges[a, b]
        mid = d["path"][len(d["path"]) // 2]
        year = vintage_year(tuple(mid), rng, acs)
        material = material_for_year(year, rng)
        age_factor = 1 + (2026 - year) * 0.01
        dia = rng.uniform(*DIAMETER_BY_CLASS[d["cls"]])
        flood = sfha.query(mid[0], mid[1]) or f500.query(mid[0], mid[1])
        adt = 0
        if d["cls"] in ("arterial", "collector"):
            near = [(haversine_m(tuple(mid), pt), val) for pt, val in traffic]
            near = [(dist, val) for dist, val in near if dist < 800]
            if near:
                adt = int(min(near)[1])
        pipes.append({
            "id": pid,
            "source_id": node_ids[a],
            "target_id": node_ids[b],
            "length": round(d["length"], 1),
            "diameter": round(dia, 3),
            "roughness": round(ROUGHNESS[material] * age_factor, 7),
            "material": material,
            "year_installed": year,
            "street": d["street"],
            "road_class": d["cls"],
            "flood_zone": flood,
            "adt": adt,
            "path": [[round(x, 6), round(y, 6)] for x, y in d["path"]],
        })

    return {
        "metadata": {
            "version": "2.0",
            "generator": "etl.build_network (street-true)",
            "n_nodes": len(nodes),
            "n_pipes": len(pipes),
            "seed": SEED,
            "sources": "City of Bentonville GIS (centerlines, land use, FEMA flood, addresses, ARDOT traffic)",
            "disclaimer": "Synthetic street-true network; not utility as-builts.",
        },
        "nodes": nodes,
        "pipes": pipes,
    }


OVERLAY_BBOX = (-94.32, 36.30, -94.14, 36.44)  # tight city extent for the map
OVERLAY_TOL_DEG = 0.0002  # ~22 m vertex decimation — plenty for a hazard overlay


def _thin_ring(ring: list) -> list:
    """Drop vertices closer than OVERLAY_TOL_DEG to the last kept vertex."""
    kept = [ring[0]]
    for pt in ring[1:-1]:
        if abs(pt[0] - kept[-1][0]) + abs(pt[1] - kept[-1][1]) >= OVERLAY_TOL_DEG:
            kept.append(pt)
    kept.append(ring[-1])
    return [[round(x, 5), round(y, 5)] for x, y in kept]


def write_flood_overlay() -> None:
    """Clipped, coordinate-thinned flood overlay for the frontend."""
    OUT_OVERLAYS.mkdir(parents=True, exist_ok=True)
    features = []
    for fname, zone in (("flood_sfha.geojson", "100yr"), ("flood_500yr.geojson", "500yr")):
        for f in json.load(open(RAW_DIR / fname))["features"]:
            geom = f.get("geometry")
            if not geom:
                continue
            polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            kept = []
            for rings in polys:
                xs = [p[0] for p in rings[0]]
                ys = [p[1] for p in rings[0]]
                if (max(xs) < OVERLAY_BBOX[0] or min(xs) > OVERLAY_BBOX[2]
                        or max(ys) < OVERLAY_BBOX[1] or min(ys) > OVERLAY_BBOX[3]):
                    continue
                thinned = [_thin_ring(ring) for ring in rings]
                thinned = [r for r in thinned if len(r) >= 4]
                if thinned:
                    kept.append(thinned)
            if kept:
                features.append({
                    "type": "Feature",
                    "properties": {"zone": zone},
                    "geometry": {"type": "MultiPolygon", "coordinates": kept},
                })
    out = OUT_OVERLAYS / "flood.geojson"
    with open(out, "w") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh)
    print(f"wrote {out} ({len(features)} features, {out.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    network = build()
    with open(OUT_NETWORK, "w") as fh:
        json.dump(network, fh)
    size = OUT_NETWORK.stat().st_size / 1e6
    print(f"wrote {OUT_NETWORK} ({network['metadata']['n_nodes']} nodes, "
          f"{network['metadata']['n_pipes']} pipes, {size:.1f} MB)")
    types = Counter(n["node_type"] for n in network["nodes"])
    classes = Counter(p["road_class"] for p in network["pipes"])
    flood = Counter(p["flood_zone"] for p in network["pipes"])
    print("node types:", dict(types))
    print("pipe classes:", dict(classes))
    print("flood exposure:", dict(flood))
    write_flood_overlay()


if __name__ == "__main__":
    main()
