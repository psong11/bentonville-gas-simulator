"""
Bentonville Gas Simulator
=========================
Streamlit application for simulating and analyzing the gas distribution
network of Bentonville, Arkansas.

Features:
- Interactive network visualization
- Real-time leak simulation
- Intelligent leak detection
- System metrics dashboard
- Data export capabilities
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import networkx as nx
import json
from datetime import datetime
from pathlib import Path
import io

# Local imports
from city_gen import CityNetworkGenerator, GasNode, GasPipe
from physics import PhysicsEngine, LeakSimulator, SimulationState
from leak_detector import LeakDetector, detect_leaks

# Page configuration
st.set_page_config(
    page_title="Bentonville Gas Simulator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A5F;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-top: 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
    .status-optimal { color: #00C853; font-weight: bold; }
    .status-normal { color: #2196F3; font-weight: bold; }
    .status-warning { color: #FF9800; font-weight: bold; }
    .status-critical { color: #F44336; font-weight: bold; }
    
    /* Leak Detection Cards - Professional Design */
    .leak-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.75rem 0;
        border-left: 4px solid #e94560;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .leak-card-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .leak-card-title {
        color: #ffffff;
        font-size: 1.1rem;
        font-weight: 600;
        margin: 0;
    }
    .leak-card-subtitle {
        color: #a0a0a0;
        font-size: 0.85rem;
        margin: 0;
    }
    .leak-card-badges {
        display: flex;
        gap: 0.5rem;
        margin-top: 0.75rem;
        flex-wrap: wrap;
    }
    .badge {
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-type {
        background-color: #0f3460;
        color: #94a3b8;
    }
    .badge-confidence {
        background-color: #065f46;
        color: #6ee7b7;
    }
    .badge-severity-critical {
        background-color: #7f1d1d;
        color: #fca5a5;
    }
    .badge-severity-severe {
        background-color: #78350f;
        color: #fcd34d;
    }
    .badge-severity-moderate {
        background-color: #1e3a5f;
        color: #93c5fd;
    }
    .badge-severity-minor {
        background-color: #14532d;
        color: #86efac;
    }
    
    /* Alert Header */
    .alert-header {
        background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        box-shadow: 0 4px 12px rgba(220, 38, 38, 0.3);
    }
    .alert-header-icon {
        font-size: 1.5rem;
    }
    .alert-header-text {
        font-size: 1.25rem;
        font-weight: 700;
    }
    
    /* Success Alert */
    .success-alert {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3);
    }
    
    /* Recommendations */
    .recommendation-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        font-size: 0.9rem;
        color: #334155;
    }
    
    .stButton>button {
        width: 100%;
    }
    
    /* Sidebar button text - smaller to fit on one line */
    [data-testid="stSidebar"] .stButton>button {
        font-size: 0.8rem;
        padding: 0.4rem 0.5rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* Darker dividers in sidebar for clearer section separation */
    [data-testid="stSidebar"] hr {
        border-color: #4a5568;
        border-width: 2px;
        margin: 1rem 0;
    }
    
    /* Legend items - white text for dark theme visibility */
    .legend-item {
        color: #ffffff !important;
        font-size: 0.9rem;
        font-weight: 500;
    }
    
    /* Reduce top padding in sidebar */
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem;
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Constants
DATA_PATH = Path(__file__).parent / "data" / "network_data.json"
DEFAULT_NODES = 200


def initialize_session_state():
    """Initialize all session state variables."""
    if 'network_loaded' not in st.session_state:
        st.session_state.network_loaded = False
    if 'nodes' not in st.session_state:
        st.session_state.nodes = None
    if 'pipes' not in st.session_state:
        st.session_state.pipes = None
    if 'graph' not in st.session_state:
        st.session_state.graph = None
    if 'simulation_state' not in st.session_state:
        st.session_state.simulation_state = None
    if 'active_leaks' not in st.session_state:
        st.session_state.active_leaks = {}
    if 'detection_result' not in st.session_state:
        st.session_state.detection_result = None
    if 'physics_engine' not in st.session_state:
        st.session_state.physics_engine = PhysicsEngine()
    if 'demand_multiplier' not in st.session_state:
        st.session_state.demand_multiplier = 1.0


def load_or_generate_network(force_regenerate: bool = False, n_nodes: int = DEFAULT_NODES):
    """Load existing network or generate new one."""
    if not force_regenerate and DATA_PATH.exists():
        try:
            nodes, pipes, graph = CityNetworkGenerator.load_network(str(DATA_PATH))
            st.session_state.nodes = nodes
            st.session_state.pipes = pipes
            st.session_state.graph = graph
            st.session_state.network_loaded = True
            return True
        except Exception as e:
            st.warning(f"Could not load existing network: {e}")
    
    # Generate new network
    with st.spinner("🏗️ Generating new city network..."):
        seed = int(datetime.now().timestamp()) if force_regenerate else 42
        generator = CityNetworkGenerator(seed=seed)
        nodes, pipes, graph = generator.generate_network(n_nodes=n_nodes)
        generator.save_network(nodes, pipes, str(DATA_PATH))
        
        st.session_state.nodes = nodes
        st.session_state.pipes = pipes
        st.session_state.graph = graph
        st.session_state.network_loaded = True
        st.session_state.active_leaks = {}
        st.session_state.detection_result = None
        
    return True


def run_simulation():
    """Run the physics simulation with current state."""
    if not st.session_state.network_loaded:
        return None
    
    state = st.session_state.physics_engine.simulate_network(
        st.session_state.graph,
        st.session_state.nodes,
        st.session_state.pipes,
        leaks=st.session_state.active_leaks,
        demand_multiplier=st.session_state.demand_multiplier
    )
    st.session_state.simulation_state = state
    return state


def create_network_visualization(state: SimulationState) -> go.Figure:
    """Create interactive Plotly visualization of the network."""
    nodes = st.session_state.nodes
    pipes = st.session_state.pipes
    graph = st.session_state.graph
    engine = st.session_state.physics_engine
    
    # Create figure
    fig = go.Figure()
    
    # Color scale for pressure
    pressure_colorscale = [
        [0.0, '#d32f2f'],    # Critical - Red
        [0.25, '#f57c00'],   # Warning - Orange
        [0.5, '#fbc02d'],    # Low - Yellow
        [0.75, '#4caf50'],   # Normal - Green
        [1.0, '#1976d2']     # Optimal - Blue
    ]
    
    # Draw pipes (edges)
    edge_traces = []
    
    for pipe in pipes:
        source_node = next(n for n in nodes if n.id == pipe.source_id)
        target_node = next(n for n in nodes if n.id == pipe.target_id)
        
        # Get pressures at endpoints
        p1 = state.node_pressures.get(pipe.source_id, 0)
        p2 = state.node_pressures.get(pipe.target_id, 0)
        avg_pressure = (p1 + p2) / 2
        
        # Normalize pressure for color
        norm_pressure = min(avg_pressure / engine.source_pressure, 1.0)
        
        # Color based on pressure
        if norm_pressure > 0.7:
            color = '#1976d2'  # Blue - optimal
        elif norm_pressure > 0.5:
            color = '#4caf50'  # Green - normal
        elif norm_pressure > 0.3:
            color = '#fbc02d'  # Yellow - low
        elif norm_pressure > 0.1:
            color = '#f57c00'  # Orange - warning
        else:
            color = '#d32f2f'  # Red - critical
        
        # Line width based on pipe diameter
        width = max(1, pipe.diameter * 10)
        
        # Flow rate for hover
        flow = state.pipe_flow_rates.get(pipe.id, 0)
        
        fig.add_trace(go.Scattermap(
            mode='lines',
            lon=[source_node.x, target_node.x],
            lat=[source_node.y, target_node.y],
            line=dict(color=color, width=width),
            hoverinfo='text',
            hovertext=f"Pipe #{pipe.id}<br>"
                     f"Flow: {abs(flow):.1f} m³/h<br>"
                     f"Diameter: {pipe.diameter*1000:.0f}mm<br>"
                     f"Material: {pipe.material}<br>"
                     f"Pressure Drop: {state.pipe_pressure_drops.get(pipe.id, 0):.1f} kPa",
            showlegend=False
        ))
    
    # Separate nodes by type for different markers
    source_nodes = [n for n in nodes if n.node_type == "source"]
    consumer_nodes = [n for n in nodes if n.node_type != "source"]
    leak_node_ids = set(state.active_leaks.keys())
    
    # Consumer nodes
    consumer_lons = [n.x for n in consumer_nodes]
    consumer_lats = [n.y for n in consumer_nodes]
    consumer_pressures = [state.node_pressures.get(n.id, 0) for n in consumer_nodes]
    consumer_colors = [
        '#d32f2f' if n.id in leak_node_ids else 
        ('#f57c00' if state.node_pressures.get(n.id, 0) < engine.source_pressure * 0.3 else
         '#4caf50' if state.node_pressures.get(n.id, 0) > engine.source_pressure * 0.5 else
         '#fbc02d')
        for n in consumer_nodes
    ]
    consumer_sizes = [
        15 if n.id in leak_node_ids else
        (12 if n.node_type == "industrial" else 
         10 if n.node_type == "commercial" else 8)
        for n in consumer_nodes
    ]
    
    consumer_hover = [
        f"<b>{n.name}</b><br>"
        f"Type: {n.node_type.title()}<br>"
        f"Node ID: {n.id}<br>"
        f"Pressure: {state.node_pressures.get(n.id, 0):.1f} kPa<br>"
        f"Demand: {state.node_actual_demand.get(n.id, 0):.1f} m³/h<br>"
        f"Status: {engine.get_pressure_status(state.node_pressures.get(n.id, 0)).title()}"
        + (f"<br><b>⚠️ LEAK ACTIVE</b>" if n.id in leak_node_ids else "")
        for n in consumer_nodes
    ]
    
    fig.add_trace(go.Scattermap(
        mode='markers',
        lon=consumer_lons,
        lat=consumer_lats,
        marker=dict(
            size=consumer_sizes,
            color=consumer_colors,
            opacity=0.8
        ),
        hoverinfo='text',
        hovertext=consumer_hover,
        name='Consumers'
    ))
    
    # Source nodes (larger, distinct marker)
    if source_nodes:
        source_lons = [n.x for n in source_nodes]
        source_lats = [n.y for n in source_nodes]
        source_hover = [
            f"<b>{n.name}</b><br>"
            f"Type: Supply Source<br>"
            f"Pressure: {state.node_pressures.get(n.id, 0):.1f} kPa<br>"
            f"Status: Active"
            for n in source_nodes
        ]
        
        fig.add_trace(go.Scattermap(
            mode='markers',
            lon=source_lons,
            lat=source_lats,
            marker=dict(
                size=20,
                color='#1565c0',
                symbol='circle',
                opacity=1
            ),
            hoverinfo='text',
            hovertext=source_hover,
            name='Supply Sources'
        ))
    
    # Highlight detected leaks if analysis was run
    if st.session_state.detection_result and st.session_state.detection_result.detected_leaks:
        detected_ids = [l['node_id'] for l in st.session_state.detection_result.detected_leaks]
        detected_nodes = [n for n in nodes if n.id in detected_ids]
        
        if detected_nodes:
            # Use a larger marker with distinct color for detected leaks
            fig.add_trace(go.Scattermap(
                mode='markers',
                lon=[n.x for n in detected_nodes],
                lat=[n.y for n in detected_nodes],
                marker=dict(
                    size=30,
                    color='#ff1744',
                    symbol='circle',
                    opacity=0.7
                ),
                hoverinfo='text',
                hovertext=[f"🚨 Detected Leak at Node #{n.id}" for n in detected_nodes],
                name='Detected Leaks'
            ))
            
            # Add a second smaller marker for emphasis (pulsing effect simulation)
            fig.add_trace(go.Scattermap(
                mode='markers',
                lon=[n.x for n in detected_nodes],
                lat=[n.y for n in detected_nodes],
                marker=dict(
                    size=15,
                    color='#ffffff',
                    symbol='circle',
                    opacity=0.9
                ),
                hoverinfo='skip',
                showlegend=False
            ))
    
    # Layout
    center_lon = np.mean([n.x for n in nodes])
    center_lat = np.mean([n.y for n in nodes])
    
    fig.update_layout(
        map=dict(
            style="carto-positron",
            center=dict(lon=center_lon, lat=center_lat),
            zoom=12
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=600,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.95)",
            font=dict(color="black", size=12)
        )
    )
    
    return fig


def create_pressure_histogram(state: SimulationState) -> go.Figure:
    """Create histogram of node pressures."""
    engine = st.session_state.physics_engine
    nodes = st.session_state.nodes
    
    # Exclude source nodes
    pressures = [
        state.node_pressures.get(n.id, 0)
        for n in nodes
        if n.node_type != "source"
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=pressures,
        nbinsx=30,
        marker_color='#1976d2',
        opacity=0.7
    ))
    
    # Add threshold lines
    fig.add_vline(
        x=engine.min_delivery_pressure,
        line_dash="dash",
        line_color="red",
        annotation_text="Min Required",
        annotation_position="top"
    )
    fig.add_vline(
        x=engine.source_pressure * 0.5,
        line_dash="dash",
        line_color="orange",
        annotation_text="Warning",
        annotation_position="top"
    )
    
    fig.update_layout(
        title="Pressure Distribution",
        xaxis_title="Pressure (kPa)",
        yaxis_title="Number of Nodes",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    return fig


def create_flow_chart(state: SimulationState) -> go.Figure:
    """Create bar chart of top flow rates."""
    pipes = st.session_state.pipes
    
    # Get top 20 pipes by flow rate
    flow_data = [
        (p.id, abs(state.pipe_flow_rates.get(p.id, 0)), p.diameter)
        for p in pipes
    ]
    flow_data.sort(key=lambda x: x[1], reverse=True)
    top_flows = flow_data[:20]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=[f"Pipe {f[0]}" for f in top_flows],
        y=[f[1] for f in top_flows],
        marker_color=[f[2] * 1000 for f in top_flows],
        marker_colorscale='Blues',
        hovertemplate="Pipe ID: %{x}<br>Flow: %{y:.1f} m³/h<extra></extra>"
    ))
    
    fig.update_layout(
        title="Top 20 Pipes by Flow Rate",
        xaxis_title="Pipe ID",
        yaxis_title="Flow Rate (m³/h)",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis_tickangle=-45
    )
    
    return fig


def export_simulation_data() -> bytes:
    """Export current simulation data to JSON."""
    nodes = st.session_state.nodes
    pipes = st.session_state.pipes
    state = st.session_state.simulation_state
    engine = st.session_state.physics_engine
    
    # Calculate metrics
    metrics = engine.calculate_system_metrics(state, nodes, pipes)
    
    export_data = {
        "metadata": {
            "export_time": datetime.now().isoformat(),
            "version": "1.0",
            "simulation_type": "Darcy-Weisbach"
        },
        "configuration": {
            "source_pressure_kpa": engine.source_pressure,
            "min_delivery_pressure_kpa": engine.min_delivery_pressure,
            "demand_multiplier": st.session_state.demand_multiplier
        },
        "metrics": metrics,
        "nodes": [
            {
                **n.to_dict(),
                "current_pressure_kpa": state.node_pressures.get(n.id, 0),
                "current_demand_m3h": state.node_actual_demand.get(n.id, 0),
                "status": engine.get_pressure_status(state.node_pressures.get(n.id, 0)),
                "has_leak": n.id in state.active_leaks
            }
            for n in nodes
        ],
        "pipes": [
            {
                **p.to_dict(),
                "current_flow_m3h": state.pipe_flow_rates.get(p.id, 0),
                "current_velocity_ms": state.pipe_velocities.get(p.id, 0),
                "pressure_drop_kpa": state.pipe_pressure_drops.get(p.id, 0),
                "reynolds_number": state.pipe_reynolds.get(p.id, 0)
            }
            for p in pipes
        ],
        "active_leaks": [
            {
                "node_id": node_id,
                "leak_rate_m3h": rate
            }
            for node_id, rate in state.active_leaks.items()
        ],
        "detection_results": None
    }
    
    # Add detection results if available
    if st.session_state.detection_result:
        result = st.session_state.detection_result
        export_data["detection_results"] = {
            "detected_leaks": result.detected_leaks,
            "affected_nodes": result.affected_nodes,
            "recommendations": result.recommendations
        }
    
    return json.dumps(export_data, indent=2).encode('utf-8')


def main():
    """Main application entry point."""
    initialize_session_state()
    
    # Header
    col_title, col_export = st.columns([4, 1])
    with col_title:
        st.markdown('<h1 class="main-header">Bentonville Gas Simulator</h1>', 
                   unsafe_allow_html=True)
        st.markdown('<p class="sub-header">Real-time gas distribution network simulation & analysis</p>',
                   unsafe_allow_html=True)
    
    with col_export:
        st.write("")  # Spacing
        if st.session_state.simulation_state:
            export_data = export_simulation_data()
            st.download_button(
                label="Export Data",
                data=export_data,
                file_name=f"gas_sim_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
    
    # Sidebar controls
    with st.sidebar:
        st.header("Control Panel")
        
        # PRIMARY ACTION: Network Analysis at the top
        st.markdown("##### Primary Action")
        if st.button("Analyze Network", use_container_width=True, type="primary", key="analyze_main", help="Run intelligent leak detection algorithm to identify potential leaks in the network"):
            if st.session_state.simulation_state:
                with st.spinner("Analyzing network for leaks..."):
                    result = detect_leaks(
                        st.session_state.graph,
                        st.session_state.nodes,
                        st.session_state.pipes,
                        st.session_state.simulation_state
                    )
                    st.session_state.detection_result = result
                st.rerun()
        
        st.divider()
        
        # Network generation
        st.subheader("Network Generation")
        n_nodes = st.slider("Number of Nodes", 50, 500, DEFAULT_NODES, step=50)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Generate New", use_container_width=True, help="Create a new randomly generated gas distribution network"):
                load_or_generate_network(force_regenerate=True, n_nodes=n_nodes)
                st.session_state.active_leaks = {}
                st.session_state.detection_result = None
                run_simulation()
                st.rerun()
        
        with col2:
            if st.button("Load Previous", use_container_width=True, help="Load the previously saved network configuration"):
                load_or_generate_network(force_regenerate=False)
                run_simulation()
                st.rerun()
        
        st.divider()
        
        # Simulation controls
        st.subheader("Simulation Parameters")
        
        source_pressure = st.slider(
            "Source Pressure (kPa)",
            200.0, 600.0,
            st.session_state.physics_engine.source_pressure,
            step=10.0,
            key="source_pressure_slider"
        )
        if source_pressure != st.session_state.physics_engine.source_pressure:
            st.session_state.physics_engine.source_pressure = source_pressure
            st.session_state.simulation_state = None  # Force re-simulation
        
        demand_mult = st.slider(
            "Demand Multiplier",
            0.5, 2.0,
            st.session_state.demand_multiplier,
            step=0.1,
            help="Simulate peak demand periods",
            key="demand_multiplier_slider"
        )
        if demand_mult != st.session_state.demand_multiplier:
            st.session_state.demand_multiplier = demand_mult
            st.session_state.simulation_state = None  # Force re-simulation
        
        st.divider()
        
        # Leak controls
        st.subheader("Leak Simulation")
        
        if st.session_state.network_loaded:
            # Node selection for manual leak
            consumer_nodes = [
                n for n in st.session_state.nodes 
                if n.node_type != "source"
            ]
            node_options = {f"#{n.id} - {n.name}": n.id for n in consumer_nodes}
            
            selected_node = st.selectbox(
                "Select Node for Leak",
                options=list(node_options.keys())
            )
            
            leak_severity = st.select_slider(
                "Leak Severity",
                options=["Minor", "Moderate", "Severe", "Critical"],
                value="Moderate"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Add Leak", use_container_width=True, help="Create a leak at the selected node with specified severity"):
                    node_id = node_options[selected_node]
                    severity_rates = {
                        "Minor": 10,
                        "Moderate": 50,
                        "Severe": 150,
                        "Critical": 500
                    }
                    st.session_state.active_leaks[node_id] = severity_rates[leak_severity]
                    run_simulation()
                    st.rerun()
            
            with col2:
                if st.button("Clear Leaks", use_container_width=True, help="Remove all active leaks and reset the network"):
                    st.session_state.active_leaks = {}
                    st.session_state.detection_result = None
                    run_simulation()
                    st.rerun()
            
            # Random leak button
            if st.button("Add Random Leak", use_container_width=True, help="Add a random leak at a random location with random severity"):
                leaks = LeakSimulator.create_random_leaks(
                    st.session_state.nodes,
                    n_leaks=1,
                    seed=int(datetime.now().timestamp())
                )
                st.session_state.active_leaks.update(leaks)
                run_simulation()
                st.rerun()
            
            # Show active leaks
            if st.session_state.active_leaks:
                st.write("**Active Leaks:**")
                for node_id, rate in st.session_state.active_leaks.items():
                    node = next(n for n in st.session_state.nodes if n.id == node_id)
                    st.write(f"• Node #{node_id}: {rate:.0f} m³/h")
    
    # Main content area
    if not st.session_state.network_loaded:
        st.info("👆 Click 'Load Previous' or 'Generate New' in the sidebar to start.")
        load_or_generate_network()
        run_simulation()
        st.rerun()
    
    # Run simulation if needed
    if st.session_state.simulation_state is None:
        run_simulation()
    
    state = st.session_state.simulation_state
    engine = st.session_state.physics_engine
    metrics = engine.calculate_system_metrics(state, st.session_state.nodes, st.session_state.pipes)
    
    # Metrics row
    st.subheader("System Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Total Nodes",
            metrics['total_nodes'],
            help="Total number of consumers in the network"
        )
    
    with col2:
        st.metric(
            "Total Demand",
            f"{metrics['total_demand_m3h']:.0f} m³/h",
            help="Current total gas demand"
        )
    
    with col3:
        delta_color = "inverse" if metrics['affected_nodes'] > 0 else "normal"
        st.metric(
            "Affected Nodes",
            metrics['affected_nodes'],
            delta=f"{metrics['critical_nodes']} critical" if metrics['critical_nodes'] > 0 else None,
            delta_color=delta_color
        )
    
    with col4:
        st.metric(
            "Avg Pressure",
            f"{metrics['avg_pressure_kpa']:.0f} kPa",
            delta=f"Min: {metrics['min_pressure_kpa']:.0f}",
            delta_color="off"
        )
    
    with col5:
        st.metric(
            "Active Leaks",
            metrics['leak_count'],
            delta=f"{metrics['total_leak_rate_m3h']:.0f} m³/h lost" if metrics['leak_count'] > 0 else None,
            delta_color="inverse"
        )
    
    # Detection results
    if st.session_state.detection_result:
        result = st.session_state.detection_result
        
        if result.detected_leaks:
            # Professional alert header
            st.markdown(f"""
            <div class="alert-header">
                <span class="alert-header-icon">🚨</span>
                <span class="alert-header-text">{len(result.detected_leaks)} Potential Leak(s) Detected</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Recommendations section (before leak cards)
            if result.recommendations:
                st.subheader("Recommended Actions")
                for rec in result.recommendations:
                    st.markdown(f"""
                    <div class="recommendation-card">
                        {rec}
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown("---")
            
            # Leak cards in columns for better layout
            cols = st.columns(2)
            for idx, leak in enumerate(result.detected_leaks):
                severity = leak['estimated_severity'].lower()
                severity_class = f"badge-severity-{severity}"
                
                with cols[idx % 2]:
                    st.markdown(f"""
                    <div class="leak-card">
                        <div class="leak-card-header">
                            <span style="color: #e94560; font-size: 1.2rem;">⚠️</span>
                            <p class="leak-card-title">{leak['node_name']} (Node #{leak['node_id']})</p>
                        </div>
                        <div class="leak-card-badges">
                            <span class="badge badge-type">{leak['node_type']}</span>
                            <span class="badge badge-confidence">{leak['confidence']:.0%} confidence</span>
                            <span class="badge {severity_class}">{leak['estimated_severity']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="success-alert">
                <span style="font-size: 1.5rem;">✅</span>
                <span style="font-size: 1.1rem; font-weight: 600;">No significant leaks detected in the network</span>
            </div>
            """, unsafe_allow_html=True)
    
    # Visualization
    st.subheader("🗺️ Network Visualization")
    
    # Legend
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown('<span class="legend-item">🔵 <strong>Optimal</strong> (>70%)</span>', unsafe_allow_html=True)
    with col2:
        st.markdown('<span class="legend-item">🟢 <strong>Normal</strong> (50-70%)</span>', unsafe_allow_html=True)
    with col3:
        st.markdown('<span class="legend-item">🟡 <strong>Low</strong> (30-50%)</span>', unsafe_allow_html=True)
    with col4:
        st.markdown('<span class="legend-item">🟠 <strong>Warning</strong> (10-30%)</span>', unsafe_allow_html=True)
    with col5:
        st.markdown('<span class="legend-item">🔴 <strong>Critical</strong> (<10%)</span>', unsafe_allow_html=True)
    
    # Map
    fig = create_network_visualization(state)
    st.plotly_chart(fig, use_container_width=True)
    
    # Charts row
    col1, col2 = st.columns(2)
    
    with col1:
        fig_hist = create_pressure_histogram(state)
        st.plotly_chart(fig_hist, use_container_width=True)
    
    with col2:
        fig_flow = create_flow_chart(state)
        st.plotly_chart(fig_flow, use_container_width=True)
    
    # Node details table
    with st.expander("📋 Node Details"):
        node_data = []
        for node in st.session_state.nodes:
            pressure = state.node_pressures.get(node.id, 0)
            status = engine.get_pressure_status(pressure)
            node_data.append({
                "ID": node.id,
                "Name": node.name,
                "Type": node.node_type.title(),
                "Pressure (kPa)": round(pressure, 1),
                "Demand (m³/h)": round(state.node_actual_demand.get(node.id, 0), 1),
                "Status": status.title(),
                "Has Leak": "⚠️ Yes" if node.id in state.active_leaks else "No"
            })
        
        df = pd.DataFrame(node_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn(
                    "Status",
                    help="Pressure status category"
                )
            }
        )
    
    # Footer
    st.divider()
    st.caption(
        "Bentonville Gas Simulator v1.0 | "
        "Physics: Darcy-Weisbach | "
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


if __name__ == "__main__":
    main()
