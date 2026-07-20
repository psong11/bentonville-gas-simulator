# Bentonville Gas Simulator — agent notes

Street-true digital twin of Bentonville AR's gas network, built from public data
(City GIS, Census ACS, FEMA). Portfolio/demo project for the Claude Corps
application. The network is synthetic-but-street-true — real distribution maps
are non-public; keep that framing in UI copy and agent prompts.

## Run

```sh
# backend (FastAPI, port 8000; agent needs ANTHROPIC_API_KEY in gitignored .env)
.venv/bin/uvicorn api.main:app --reload --port 8000
# frontend (Vite; proxies /api and /ws to :8000, override via API_PROXY_TARGET)
cd frontend && npm run dev
# tests
.venv/bin/python -m pytest tests/ -q        # 141 backend
cd frontend && npm test && npx tsc -b       # 32 frontend + typecheck
# rebuild the network artifact from raw GIS (one-shot, cached in data/raw/)
.venv/bin/python -m etl.fetch && .venv/bin/python -m etl.build_network
```

## Architecture

- `etl/` — pulls City of Bentonville ArcGIS layers + Census ACS (needs
  CENSUS_API_KEY; falls back to a downtown-distance vintage heuristic) into
  `data/raw/` (gitignored), then builds `data/network.json` (1,240 nodes /
  1,597 pipes, committed) + `data/overlays/flood.geojson` (also copied to
  `frontend/public/overlays/`). App never calls city servers at runtime.
- `physics.py` / `leak_detector.py` — original engines, unchanged; they run on
  the street-true network via the extended `GasNode`/`GasPipe` dataclasses
  (optional fields: street, road_class, flood_zone, adt, path).
- `api/agent.py` — ChatOps agent: POST /api/agent streams SSE (text deltas +
  tool events). claude-opus-4-8 (override with AGENT_MODEL), 8 tools wrapping
  AppState. Tool results carry node/pipe ids → frontend highlights them.
- `frontend/src/components/NetworkMap.tsx` — MapLibre + deck.gl (carto
  dark-matter). Diverging pressure ramp around 300 kPa. `ChatOps.tsx` — chat
  bar; react-markdown + remark-gfm for agent output.
- "Generate Network" saves to `data/network_procedural.json` — never let
  anything overwrite the committed `data/network.json` artifact.

## Fixes we already paid for (don't regress)

- UI source-pressure default must match `PhysicsEngine` default (400 kPa).
  When it was 600, the histogram flagged 100% of nodes critical on load.
- Dev WebSocket goes same-origin through the Vite proxy (`/ws`). It used to
  hardcode :8000 and silently hit whatever server owned that port.
- Anthropic stream client uses timeout=600 + retries; adaptive thinking can
  pause the byte stream and a default ReadTimeout truncated answers mid-table.
- City ArcGIS: always envelope-filter (bbox) county-wide layers — unfiltered
  queries overload their web adaptor, which returns HTML error pages.
- Two Claude sessions once shared this checkout + branch: a push silently
  grew the other session's open PR. One session owns a branch/checkout at a
  time; check `git log`/`git status` for foreign commits before pushing.

## Deploy (Vercel, both halves)

- Frontend: project `bentonville-gas-sim` (root `frontend/`), static Vite build;
  `/api/*` rewrites to the backend project (same-origin, no CORS). WS is off in
  prod (`VITE_DISABLE_WS=1` in committed `.env.production`) — the app falls back
  to REST automatically.
- Backend: project `gas-sim-api`, FastAPI as a single Vercel Python function via
  `scripts/deploy_backend.sh` (staging dir dodges Vercel's api/ auto-scan
  colliding with our api/ package). Env: ANTHROPIC_API_KEY. Rate limit on
  /api/agent (per-IP + daily global, env-tunable AGENT_RATE_*).
- Live: https://bentonville-gas-sim.vercel.app · re-record the README GIF with
  `scripts/record_demo.py` after visual changes.

## Status (2026-07-16)

All planned phases shipped and deployed: street-true network + map, ChatOps
agent, risk engine + submodular sensor placement + Risk/Sensor UI. Branch
`revamp/real-city`; PR #14 tracks it (retitled to the revamp). 159 backend +
32 frontend tests.
