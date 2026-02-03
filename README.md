# Bentonville Gas Simulator

A real-time digital twin for simulating and analyzing the gas distribution network of Bentonville, Arkansas. Built with a modern React + FastAPI stack featuring WebSocket-driven updates, Darcy-Weisbach physics, and optional PostgreSQL persistence.

## 🚀 Quick Start

### Backend (FastAPI)
```bash
# Create virtual environment
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start API server
uvicorn api.main:app --reload --port 8000
```

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev    # Starts on http://localhost:5173
```

### Optional: PostgreSQL Persistence
```bash
# Option 1: Docker (recommended)
docker compose up -d
python scripts/setup_db.py
USE_DATABASE=true uvicorn api.main:app --reload

# Option 2: Local PostgreSQL
brew services start postgresql  # macOS
python scripts/setup_db.py
USE_DATABASE=true uvicorn api.main:app --reload
```

## 📁 Project Structure

```
bentonville_gas_simulator/
├── api/                        # FastAPI Backend
│   ├── main.py                 # REST + WebSocket endpoints
│   ├── schemas.py              # Pydantic models
│   ├── state.py                # Application state manager
│   ├── database.py             # SQLAlchemy async config
│   ├── models.py               # ORM models (Node, Pipe, Leak)
│   └── crud.py                 # Database operations
├── frontend/                   # React Frontend
│   ├── src/
│   │   ├── App.tsx             # Main application
│   │   ├── components/         # UI components
│   │   │   ├── NetworkMap.tsx      # Plotly network visualization
│   │   │   ├── FlowChart.tsx       # Pipe flow rates chart
│   │   │   ├── PressureHistogram.tsx
│   │   │   ├── ControlPanel.tsx    # Parameter controls
│   │   │   ├── LeakDetection.tsx   # Leak analysis UI
│   │   │   └── StatusBar.tsx       # System metrics
│   │   ├── hooks/
│   │   │   ├── useApi.ts           # TanStack Query hooks
│   │   │   └── useWebSocket.ts     # Real-time updates
│   │   └── types.ts            # TypeScript interfaces
│   ├── package.json
│   └── vite.config.ts
├── alembic/                    # Database migrations
│   └── versions/
├── scripts/
│   └── setup_db.py             # Database initialization
├── city_gen.py                 # Procedural network generator
├── physics.py                  # Darcy-Weisbach physics engine
├── leak_detector.py            # Intelligent leak detection
├── docker-compose.yml          # PostgreSQL container
├── requirements.txt
└── README.md
```

## 🔧 Features

### Modern Web Architecture
- **React 18** with TypeScript for type-safe UI development
- **TanStack Query** for server state management and caching
- **WebSocket** real-time updates (pressure/flow changes broadcast instantly)
- **Tailwind CSS v4** for utility-first styling
- **Plotly.js** for interactive network visualization

### FastAPI Backend
- Async REST API with automatic OpenAPI documentation
- WebSocket endpoint for bidirectional real-time communication
- Pydantic v2 for request/response validation
- Optional PostgreSQL persistence with SQLAlchemy 2.0 async

### Network Generation
- Procedurally generates realistic gas distribution networks
- Supports 50-500+ nodes (residential, commercial, industrial)
- Random Geometric Graph algorithm for realistic topology
- Configurable to use real GeoJSON coordinates

### Physics Simulation (Darcy-Weisbach)
- Accurate pressure drop calculations using the Darcy-Weisbach equation
- Swamee-Jain approximation for friction factor
- Compressible gas flow modeling
- Iterative solver for network-wide pressure distribution
- Real-time recalculation on parameter changes

### Leak Detection
- Multi-strategy detection algorithm:
  - Pressure deficit analysis
  - Spatial clustering of anomalies
  - Graph-based propagation tracing
- Confidence scoring for detected leaks
- Actionable recommendations

## 🖥️ API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/network` | GET | Get network topology |
| `/api/network/generate` | POST | Generate new network |
| `/api/simulate` | POST | Run physics simulation |
| `/api/simulation/state` | GET | Get current state |
| `/api/leaks/detect` | POST | Run leak detection |
| `/api/leaks/inject` | POST | Inject test leaks |
| `/api/leaks/clear` | POST | Clear all leaks |
| `/ws` | WebSocket | Real-time updates |

### WebSocket Messages

**Client → Server:**
```json
{"type": "SET_PRESSURE", "payload": {"value": 500}}
{"type": "SET_DEMAND_MULTIPLIER", "payload": {"value": 1.5}}
{"type": "INJECT_LEAK", "payload": {"count": 2}}
{"type": "CLEAR_LEAKS", "payload": {}}
```

**Server → Client:**
```json
{"type": "SIMULATION_UPDATE", "payload": {...}}
{"type": "NETWORK_UPDATE", "payload": {...}}
{"type": "LEAK_ALERT", "payload": {"injected_node_ids": [...]}}
```

## 🎛️ Controls

| Control | Description |
|---------|-------------|
| **Source Pressure** | Adjust main supply pressure (200-600 kPa) |
| **Demand Multiplier** | Simulate peak demand periods (0.5x-2.0x) |
| **Generate Network** | Create new random network topology |
| **Inject Leaks** | Add random test leaks to network |
| **Clear Leaks** | Remove all active leaks |
| **Analyze Network** | Run leak detection algorithm |

## 📊 Metrics Dashboard

- **Total Nodes**: Consumer count in network
- **Total Pipes**: Distribution pipe count
- **Average Pressure**: System-wide pressure (kPa)
- **Active Leaks**: Current leak count and locations
- **WebSocket Status**: Real-time connection state

## 🔬 Technical Details

### Darcy-Weisbach Equation
```
ΔP = f × (L/D) × (ρ × v²/2)
```
Where:
- ΔP = pressure drop (Pa)
- f = Darcy friction factor (Swamee-Jain)
- L = pipe length (m)
- D = pipe diameter (m)
- ρ = gas density (kg/m³)
- v = flow velocity (m/s)

### Gas Properties (Natural Gas)
| Property | Value |
|----------|-------|
| Density | 0.72 kg/m³ |
| Dynamic Viscosity | 1.1×10⁻⁵ Pa·s |
| Specific Gravity | 0.60 |

### Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, TanStack Query, Tailwind CSS v4 |
| Backend | Python 3.11+, FastAPI, Pydantic v2, uvicorn |
| Real-time | WebSockets (native) |
| Database | PostgreSQL 15+ (optional), SQLAlchemy 2.0, Alembic |
| Visualization | Plotly.js, Lucide React Icons |

## 🗺️ Using Real Coordinates

To use real Bentonville coordinates instead of procedural generation:

1. Implement the `RealCoordinateProvider` class in `city_gen.py`
2. Load GeoJSON/Shapefile with building footprints
3. Pass the provider to `CityNetworkGenerator`

```python
from city_gen import RealCoordinateProvider, CityNetworkGenerator

provider = RealCoordinateProvider("bentonville_buildings.geojson")
generator = CityNetworkGenerator(coordinate_provider=provider)
nodes, pipes, graph = generator.generate_network()
```

## 🧪 Development

```bash
# Run backend tests
pytest tests/

# Type check frontend
cd frontend && npm run type-check

# Build frontend for production
cd frontend && npm run build
```

## 📜 License

MIT License - Built for educational and planning purposes.

## 🙏 Acknowledgments

Developed in response to infrastructure challenges in Bentonville, AR to help prevent future gas leakage incidents through better simulation and planning tools. Migrated from Streamlit to a modern React + FastAPI architecture for improved performance, real-time capabilities, and production readiness.
