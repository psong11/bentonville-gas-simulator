# Bentonville Gas Simulator

A real-time simulation and analysis tool for the gas distribution network of Bentonville, Arkansas. Built to help civil engineers and planners understand and prevent infrastructure failures.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py
```

## 📁 Project Structure

```
bentonville_gas_simulator/
├── app.py              # Streamlit UI application
├── city_gen.py         # Procedural network generator
├── physics.py          # Darcy-Weisbach physics engine
├── leak_detector.py    # Intelligent leak detection
├── requirements.txt    # Python dependencies
├── data/
│   └── network_data.json  # Generated network data
└── README.md
```

## 🔧 Features

### Network Generation
- Procedurally generates realistic gas distribution networks
- Supports 50-500+ nodes (residential, commercial, industrial)
- Random Geometric Graph algorithm for realistic topology
- Modular design allows swapping in real coordinates

### Physics Simulation
- **Darcy-Weisbach equation** for accurate pressure drop calculations
- **Swamee-Jain approximation** for friction factor
- Compressible gas flow considerations
- Iterative solver for network-wide pressure distribution

### Leak Detection
- Multi-strategy detection algorithm:
  - Pressure deficit analysis
  - Spatial clustering of anomalies
  - Graph-based propagation tracing
- Confidence scoring for detected leaks
- Actionable recommendations

### Interactive UI
- Real-time network visualization on map
- Pressure color-coding (optimal → critical)
- Add/remove leaks interactively
- System metrics dashboard
- Data export to JSON

## 🎛️ Controls

| Control | Description |
|---------|-------------|
| **Generate New** | Create a new random network |
| **Load Existing** | Load saved network data |
| **Source Pressure** | Adjust main supply pressure (kPa) |
| **Demand Multiplier** | Simulate peak demand periods |
| **Add Leak** | Create a leak at selected node |
| **Analyze Network** | Run leak detection algorithm |
| **Export Data** | Download simulation data as JSON |

## 📊 Metrics

- **Total Nodes**: Number of consumers in network
- **Total Demand**: Current gas demand (m³/h)
- **Affected Nodes**: Nodes with low pressure
- **Average Pressure**: System-wide pressure average
- **Active Leaks**: Number and rate of simulated leaks

## 🔬 Technical Details

### Darcy-Weisbach Equation
```
ΔP = f × (L/D) × (ρ × v²/2)
```
Where:
- ΔP = pressure drop (Pa)
- f = Darcy friction factor
- L = pipe length (m)
- D = pipe diameter (m)
- ρ = gas density (kg/m³)
- v = flow velocity (m/s)

### Gas Properties (Natural Gas)
- Density: 0.72 kg/m³
- Dynamic Viscosity: 1.1×10⁻⁵ Pa·s
- Specific Gravity: 0.60

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

## 📜 License

MIT License - Built for educational and planning purposes.

## 🙏 Acknowledgments

Developed in response to infrastructure challenges in Bentonville, AR to help prevent future gas leakage incidents through better simulation and planning tools.
