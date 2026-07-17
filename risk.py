"""
Risk Engine
===========
Per-pipe risk score for the street-true network:

    risk = P(fail) x consequence

P(fail) — relative likelihood a segment fails, from attributes the ETL derived
from public data:
  - material/age prior (PHMSA national incident patterns: bare/older steel and
    cast iron dominate distribution incidents; modern PE is far safer)
  - FEMA flood-zone exposure (corrosion, washout, support loss)
  - excavation intensity (nearest ARDOT traffic count — third-party strikes
    are the leading cause of distribution damage)
  - pressure utilization (simulated pressure drop — hard-working segments)

Consequence — what is lost if the segment fails:
  - isolated demand: if the pipe is a graph bridge, the demand cut off from
    every city gate when it is removed
  - flow carried in the current simulation (loop pipes never isolate anyone
    but a failure still interrupts what they carry)
  - edge betweenness (sampled): structural criticality in the network
  - proximity to critical facilities (approximate landmark list)

All factors are combined multiplicatively and normalized to percentile ranks
so degenerate distributions (e.g. uniform vintages) cannot blow up any term.
Static graph work (bridges, betweenness, facility proximity) is computed once
per network and cached on the AppState instance; simulation-dependent terms
are recomputed per call.
"""

import math
from bisect import bisect_left

import networkx as nx

# Relative failure-rate priors by material (PHMSA distribution-incident
# patterns; relative weights, not absolute rates).
MATERIAL_PRIOR = {"steel": 1.0, "ductile_iron": 0.8, "pvc": 0.5, "polyethylene": 0.35}
FLOOD_FACTOR = {"100yr": 1.6, "500yr": 1.25, None: 1.0}

# Approximate landmark locations (public knowledge; used only as a
# consequence weighting, labeled approximate everywhere they surface).
CRITICAL_FACILITIES = [
    {"name": "Downtown Square (approx.)", "lon": -94.2088, "lat": 36.3729},
    {"name": "Bentonville High School (approx.)", "lon": -94.2196, "lat": 36.3861},
    {"name": "Walmart Home Office campus (approx.)", "lon": -94.1986, "lat": 36.3665},
    {"name": "NW Medical Center area (approx.)", "lon": -94.2530, "lat": 36.3450},
    {"name": "Crystal Bridges Museum (approx.)", "lon": -94.2027, "lat": 36.3833},
]
FACILITY_RADIUS_M = 350.0
FACILITY_BONUS = 1.5

BETWEENNESS_SAMPLES = 200
_CACHE_ATTR = "_risk_static_cache"


def _haversine_m(lon1, lat1, lon2, lat2) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (lon1, lat1, lon2, lat2))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6_371_000 * 2 * math.asin(math.sqrt(h))


def _percentiles(values: dict) -> dict:
    """value -> percentile rank in [0, 1]; robust to ties/degenerate spreads."""
    ordered = sorted(values.values())
    n = max(len(ordered) - 1, 1)
    return {k: bisect_left(ordered, v) / n for k, v in values.items()}


def _pipe_midpoint(pipe):
    if pipe.path:
        return pipe.path[len(pipe.path) // 2]
    return None


def _static_parts(state) -> dict:
    """Bridges/isolated demand, betweenness, facility proximity — once per network."""
    cached = getattr(state, _CACHE_ATTR, None)
    if cached is not None and cached["graph_id"] == id(state.graph):
        return cached

    G = state.graph
    demand = {n.id: n.base_demand for n in state.nodes}
    sources = {n.id for n in state.nodes if n.node_type == "source"}

    # Isolated demand for bridge pipes: BFS on G minus the edge, sum demand on
    # the side that can no longer reach any source.
    iso_demand: dict[int, float] = {}
    edge_to_pipe = {}
    for p in state.pipes:
        edge_to_pipe[(p.source_id, p.target_id)] = p.id
        edge_to_pipe[(p.target_id, p.source_id)] = p.id
    for u, v in nx.bridges(G):
        pid = edge_to_pipe.get((u, v))
        if pid is None:
            continue
        G.remove_edge(u, v)
        try:
            comp_u = nx.node_connected_component(G, u)
            cut_side = comp_u if not (comp_u & sources) else nx.node_connected_component(G, v)
            if not (cut_side & sources):
                iso_demand[pid] = sum(demand.get(n, 0.0) for n in cut_side)
        finally:
            G.add_edge(u, v)

    betweenness_raw = nx.edge_betweenness_centrality(
        G, k=min(BETWEENNESS_SAMPLES, G.number_of_nodes()), seed=42
    )
    betweenness = {}
    for (u, v), val in betweenness_raw.items():
        pid = edge_to_pipe.get((u, v))
        if pid is not None:
            betweenness[pid] = val

    near_facility: dict[int, str] = {}
    for p in state.pipes:
        mid = _pipe_midpoint(p)
        if not mid:
            continue
        for f in CRITICAL_FACILITIES:
            if _haversine_m(mid[0], mid[1], f["lon"], f["lat"]) <= FACILITY_RADIUS_M:
                near_facility[p.id] = f["name"]
                break

    cached = {
        "graph_id": id(state.graph),
        "iso_demand": iso_demand,
        "betweenness": betweenness,
        "near_facility": near_facility,
    }
    setattr(state, _CACHE_ATTR, cached)
    return cached


def score_pipes(state) -> dict:
    """Full risk assessment. Returns {"pipes": [per-pipe dicts sorted by risk],
    "scores": {pipe_id: risk 0-1}, "method": str}."""
    static = _static_parts(state)
    sim = state.get_current_simulation_state()

    # --- P(fail) ---
    adt_pct = _percentiles({p.id: (p.adt or 0) for p in state.pipes})
    drop_pct = _percentiles(
        {p.id: abs(sim.pipe_pressure_drops.get(str(p.id), sim.pipe_pressure_drops.get(p.id, 0.0)))
         for p in state.pipes}
    )
    p_fail_raw = {}
    for p in state.pipes:
        age_years = max(0, 2026 - p.year_installed)
        material = MATERIAL_PRIOR.get(p.material, 0.7) * (1 + age_years / 40)
        flood = FLOOD_FACTOR.get(p.flood_zone, 1.0)
        excavation = 1 + 0.5 * adt_pct[p.id]
        utilization = 1 + 0.5 * drop_pct[p.id]
        p_fail_raw[p.id] = material * flood * excavation * utilization
    p_fail_pct = _percentiles(p_fail_raw)

    # --- consequence ---
    flow_pct = _percentiles(
        {p.id: abs(sim.pipe_flow_rates.get(str(p.id), sim.pipe_flow_rates.get(p.id, 0.0)))
         for p in state.pipes}
    )
    iso_norm = _percentiles(static["iso_demand"]) if static["iso_demand"] else {}
    btw_pct = _percentiles(static["betweenness"]) if static["betweenness"] else {}
    consequence_raw = {}
    for p in state.pipes:
        iso = 1 + 2.0 * iso_norm.get(p.id, 0.0) if p.id in static["iso_demand"] else 1.0
        flow = 1 + 0.5 * flow_pct[p.id]
        btw = 1 + 0.5 * btw_pct.get(p.id, 0.0)
        facility = FACILITY_BONUS if p.id in static["near_facility"] else 1.0
        consequence_raw[p.id] = iso * flow * btw * facility
    consequence_pct = _percentiles(consequence_raw)

    risk_raw = {pid: p_fail_pct[pid] * consequence_pct[pid] for pid in p_fail_pct}
    risk_pct = _percentiles(risk_raw)

    pipes_out = []
    for p in state.pipes:
        pid = p.id
        pipes_out.append({
            "pipe_id": pid,
            "street": getattr(p, "street", None) or "unnamed",
            "road_class": p.road_class,
            "risk": round(risk_pct[pid], 4),
            "p_fail": round(p_fail_pct[pid], 4),
            "consequence": round(consequence_pct[pid], 4),
            "factors": {
                "material": p.material,
                "year_installed": p.year_installed,
                "flood_zone": p.flood_zone,
                "excavation_adt": p.adt or 0,
                "pressure_drop_percentile": round(drop_pct[pid], 2),
                "isolates_demand_m3h": round(static["iso_demand"].get(pid, 0.0), 1),
                "betweenness_percentile": round(btw_pct.get(pid, 0.0), 2),
                "near_critical_facility": static["near_facility"].get(pid),
            },
        })
    pipes_out.sort(key=lambda d: -d["risk"])

    return {
        "method": (
            "risk = P(fail) x consequence, percentile-normalized. P(fail): material/age "
            "prior x flood exposure x excavation (ADT) x pressure utilization. "
            "Consequence: isolated demand (bridges) x flow carried x edge betweenness "
            "x critical-facility proximity (approximate landmarks)."
        ),
        "pipes": pipes_out,
        "scores": {str(pid): round(risk_pct[pid], 4) for pid in risk_pct},
    }
