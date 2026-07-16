# Bentonville Gas Simulator — 3-Day Revamp Plan (gas-focused)

> **STATUS (2026-07-16):** Day 1 (street-true network + map) ✅ shipped.
> The Claude agent was pulled FORWARD of the math phase (user call: first-glance
> value) and ✅ shipped with 8 tools + map-reactive highlights + first-impression
> polish. Remaining = the Day-2 math below (risk engine, leak-signature matrix,
> submodular placement + gain curve, Risk/Sensor map layers); the agent's
> `list_inspection_candidates` heuristic gets replaced in place by the risk
> engine. See CLAUDE.md for run commands and paid-for gotchas.

**Goal:** Turn the abstract-graph simulator into a real-Bentonville **gas** digital twin with three
demo moments, in ~3 focused days:

1. **A real map** — street-true synthetic gas distribution network over actual Bentonville, with
   real hazard overlays. (Toy → credible.)
2. **Sensor placement that proves math chops** — greedy submodular optimizer + marginal-gain
   curve: *"8 sensors detect 92% of leak scenarios."*
3. **A Claude ChatOps agent that drives the map** — ask *"where are the weak points we should
   inspect?"* and watch it call tools and highlight the answer. (The Claude Corps showcase.)

Everything else is cut, deferred, or reused as-is. The bar for keeping anything: does a reviewer
*see* it in a 3-minute demo, or does the agent *need* it to answer the flagship question?

**Ruthlessness rules applied:**
- Physics stays mostly as-is (adapter onto the new network, sanity fixes only). A Newton nodal
  solver is invisible in a demo.
- No synthetic SCADA time series, no EWMA/CUSUM, no time scrubber. Existing leak inject/detect
  is kept and re-pointed at the new network.
- Water/electric layers dropped (gas focus). No story mode, no 3D tiles, no DB work.
- The two "splurge" items that take the page to the next level and are worth going over budget:
  **deck.gl animated flow particles** (makes the network feel alive) and **map-reactive agent
  tool calls** (agent cites pipes → they pulse on the map).

---

## Data (all verified live, 2026-07-15; pulled once by ETL, committed as static GeoJSON)

| Source | Layer | Use |
|---|---|---|
| City ArcGIS (`gis.bentonvillear.com/arcgis/rest/services`) | `Transportation/NewWorldCenterlines18` | Network skeleton — mains follow streets |
| City ArcGIS | `Planning/Land_Use_2025/FeatureServer` | Nodal demand class (res/com/ind) |
| City ArcGIS | `Stormwater/FEMA_DATA` layers 44 (SFHA) + 62 (500-yr) | Flood exposure per pipe → risk factor + map overlay |
| City ArcGIS | `Planning/2025_Traffic_Counts` | Third-party-strike (excavation) risk proxy |
| Census ACS + TIGER (free API) | Block-group median year-built, population | Pipe-vintage prior (cast-iron/bare-steel eras) + consequence weighting |
| PHMSA NPMS Public Viewer (manual, one county view) | Gas transmission corridor through Benton County | Hand-digitize 2–3 plausible city-gate/source nodes near real corridor crossings |
| FEMA NRI (one CSV download) | Benton County tract scores: tornado, hail, ice, earthquake | `get_hazard_context` tool + hazard panel |

**Honest framing (UI footer + agent system prompt):** real gas distribution maps are non-public
for security. This network is *synthetic but street-true* — real streets, real demand drivers,
real hazards, plausible-not-actual pipes. Not an operational tool; call 811. This framing is a
feature, not a caveat — it shows judgment.

Coordinate note: city layers are EPSG 3433 (AR North, feet) → reproject to 4326 in ETL.

---

## Day 1 — Real city, real map

**ETL (`etl/build_city.py`, run once, artifacts committed to `data/`):**
1. Fetch centerlines, land use, SFHA, traffic counts (ArcGIS REST `query?f=geojson`, paginated);
   ACS year-built + population via Census API; reproject to 4326; clip to city limits.
2. Build street-true network (replaces random geometric graph in `city_gen.py`):
   centerlines → planar NetworkX graph → simplify to ~300–500 junction nodes; 2–3 source nodes at
   NPMS-corridor-informed city gates; hierarchical diameters (arterial feeders → collector mains →
   local services, using traffic-count road class); nodal demand = land-use class × address/pop
   density; pipe `install_era`/material sampled from surrounding block-group median year-built.
3. Emit `data/bentonville_network.geojson` (nodes + pipes with all attributes) and
   `data/overlays/*.geojson` (SFHA, 500-yr). Adapter so the existing physics/leak-detect API
   serves the new network unchanged (IDs, demand fields).

**Frontend — replace Plotly `NetworkMap` with MapLibre GL + deck.gl:**
- Dark ops-center basemap (free vector tiles), pipes as PathLayer colored by pressure,
  nodes/sources as ScatterplotLayer, flood overlay toggle.
- **Splurge:** deck.gl `TripsLayer` animated particles along flow direction.
- Keep ControlPanel/StatusBar/charts wired as today (pressure slider, demand multiplier,
  inject/clear leaks all still work — same API).

**End-of-day proof:** screenshot — pressure-colored gas network on real Bentonville streets with
flood zones. Sanity-check pressures are monotonically reasonable from gates outward (fix physics
only if visibly wrong).

## Day 2 — The math: weak points + sensor placement

**Risk engine (`risk.py`) — static per-pipe score, cheap to compute, powers the agent's flagship
answer:**
`Risk = P(fail) × Consequence`
- `P(fail)`: vintage/material prior (PHMSA national incident rates by era — hardcoded table with
  citation) × flood-zone exposure × traffic/excavation intensity × pressure utilization.
- `Consequence`: downstream population served (graph traversal × block-group pop) + critical
  facilities within buffer (schools, hospital, Walmart Home Office, downtown square — small
  hand-made GeoJSON, ~10 points) + edge betweenness (does losing this pipe island customers?).
- Endpoint `GET /api/risk/weakpoints?top_k=` → ranked pipes **with street names** (from
  centerline attributes — this is what makes agent answers feel real).

**Sensor placement (`placement.py`) — the flagship math:**
- Leak-signature matrix: existing physics engine, leak injected on each of ~150 sampled pipes
  (risk-weighted sample) → pressure deviation at every candidate node. Cache as `.npz`.
- Greedy submodular maximization of risk-weighted detection coverage (Krause et al.,
  (1−1/e)-optimal). Skip the D-optimal localization objective — coverage + gain curve is 90% of
  the demo at 40% of the effort.
- Endpoint `POST /api/sensors/optimal {budget}` → ranked sites, per-step marginal gain, %
  scenarios covered.

**Frontend:** layer toggles Pressure | Risk | Sensors; risk view = red-scale pipes + top-10 list
in right panel; sensor view = ranked markers + coverage halo + **gain-curve chart with the elbow
annotated** ("8 sensors → 92%"). Budget slider re-runs placement live (greedy on cached matrix is
fast).

**End-of-day proof:** toggle through the three layers; move budget slider; gain curve updates.

## Day 3 — Claude agent + ship it

**Backend `POST /api/agent` (FastAPI + Anthropic Python SDK, `claude-sonnet-5`, SSE streaming):**
- Tool-use loop over thin wrappers of existing endpoints:
  `get_network_status`, `rank_weak_points(top_k)`, `recommend_sensor_plan(budget)`,
  `run_scenario(pressure, demand_multiplier)`, `inject_leak / detect_leaks`,
  `get_hazard_context()` (static NRI + SFHA-intersection summary — no live calls).
- System prompt: network summary, data provenance, synthetic-network framing, "answer with street
  names and cite which tool produced each claim."
- Stream both text tokens and tool-call events to the client. `ANTHROPIC_API_KEY` server-side only.

**Frontend — chat bar pinned at top (the first thing a reviewer sees):**
- Collapsed input → expands to thread; streaming text; inline chips ("⚙ rank_weak_points…").
- **Splurge:** tool-call results carry pipe/node IDs → map highlights/pulses them and pans to fit.
  The agent *visibly operates the map*. This is the demo moment; protect time for it.
- 3 suggested prompts seeded in the empty state, including the flagship:
  *"How does gas pressure look today, and where should we run quality tests?"* → agent chains
  `get_network_status` + `rank_weak_points` + `get_hazard_context`, names streets, highlights them.

**Ship:** deploy (Vercel FE + Railway BE w/ env key), README rewrite (hero GIF of the agent
highlighting weak points, architecture diagram, data-provenance table, math section), end-to-end
verification pass (browser → agent → tools → map), record demo GIF.

---

## Deferred (v2 candidates, deliberately cut)
- Newton nodal solve validated vs pandapipes; diurnal SCADA + EWMA/CUSUM anomaly streams;
  D-optimal sensor localization; time scrubber; story mode; real water-leak layer
  (5,899-record `Water_System/Water_Leaks_Layer_for_Dashboard` — great data, wrong utility for
  this pitch); Google Photorealistic 3D tiles; DB persistence.

## Risks
- **Day-1 network gen rabbit hole** — timebox graph simplification to half a day; a slightly
  coarse network is fine, ugly topology is not. Keep old generator behind a flag as fallback.
- **Leak-signature matrix cost** — 150 sampled pipes × existing solver; if slow, drop to 80.
- **Agent latency** — greedy-on-cache + static hazard context keeps every tool <1s; stream early.
- City endpoints change → ETL is one-shot; app never calls the city at runtime.
