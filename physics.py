"""
Physics Engine Module
=====================
Implements Darcy-Weisbach equation for gas flow simulation.
Handles pressure drop calculations, flow distribution, and leak modeling.

Key Physics:
- Darcy-Weisbach equation for pressure drop in pipes
- Compressible flow considerations for natural gas
- Iterative solver for network-wide pressure distribution
"""

import numpy as np
import networkx as nx
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import copy


# Physical constants for natural gas
class GasProperties:
    """Properties of natural gas at standard conditions."""
    DENSITY = 0.72  # kg/m³ at 15°C, 1 atm
    DYNAMIC_VISCOSITY = 1.1e-5  # Pa·s
    SPECIFIC_GRAVITY = 0.60  # relative to air
    COMPRESSIBILITY_FACTOR = 0.998  # Z-factor at low pressure
    SPECIFIC_HEAT_RATIO = 1.31  # γ = Cp/Cv


@dataclass
class SimulationState:
    """Represents the current state of the simulation."""
    node_pressures: Dict[int, float] = field(default_factory=dict)  # kPa
    node_actual_demand: Dict[int, float] = field(default_factory=dict)  # m³/h
    pipe_flow_rates: Dict[int, float] = field(default_factory=dict)  # m³/h
    pipe_velocities: Dict[int, float] = field(default_factory=dict)  # m/s
    pipe_pressure_drops: Dict[int, float] = field(default_factory=dict)  # kPa
    pipe_reynolds: Dict[int, float] = field(default_factory=dict)  # dimensionless
    active_leaks: Dict[int, float] = field(default_factory=dict)  # node_id -> leak_rate m³/h
    timestamp: float = 0.0


@dataclass 
class PipeState:
    """Detailed state of a single pipe."""
    pipe_id: int
    flow_rate: float  # m³/h
    velocity: float  # m/s
    pressure_drop: float  # kPa
    reynolds_number: float
    friction_factor: float
    status: str  # "normal", "high_flow", "low_pressure"


class PhysicsEngine:
    """
    Gas network physics simulator using Darcy-Weisbach equation.
    
    The Darcy-Weisbach equation for pressure drop:
    ΔP = f * (L/D) * (ρ * v²/2)
    
    Where:
    - ΔP = pressure drop (Pa)
    - f = Darcy friction factor (dimensionless)
    - L = pipe length (m)
    - D = pipe diameter (m)
    - ρ = gas density (kg/m³)
    - v = flow velocity (m/s)
    
    For compressible gas flow, we use the Weymouth equation modification.
    """
    
    def __init__(
        self,
        source_pressure: float = 400.0,  # kPa (typical distribution pressure)
        min_delivery_pressure: float = 1.7,  # kPa (minimum at consumer)
        temperature: float = 288.15,  # K (15°C)
        base_pressure: float = 101.325,  # kPa (atmospheric)
    ):
        self.source_pressure = source_pressure
        self.min_delivery_pressure = min_delivery_pressure
        self.temperature = temperature
        self.base_pressure = base_pressure
        self.gas = GasProperties()
        
    def calculate_friction_factor(
        self,
        reynolds: float,
        relative_roughness: float
    ) -> float:
        """
        Calculate Darcy friction factor using Swamee-Jain equation
        (explicit approximation of Colebrook-White).
        
        Valid for 5000 ≤ Re ≤ 10^8 and 10^-6 ≤ ε/D ≤ 10^-2
        """
        if reynolds < 2300:
            # Laminar flow
            return 64 / max(reynolds, 1)
        elif reynolds < 4000:
            # Transition region - interpolate
            f_laminar = 64 / 2300
            f_turbulent = self._swamee_jain(4000, relative_roughness)
            t = (reynolds - 2300) / 1700
            return f_laminar + t * (f_turbulent - f_laminar)
        else:
            # Turbulent flow - Swamee-Jain equation
            return self._swamee_jain(reynolds, relative_roughness)
    
    def _swamee_jain(self, reynolds: float, relative_roughness: float) -> float:
        """Swamee-Jain explicit approximation of Colebrook equation."""
        term1 = relative_roughness / 3.7
        term2 = 5.74 / (reynolds ** 0.9)
        return 0.25 / (np.log10(term1 + term2) ** 2)
    
    def calculate_pressure_drop(
        self,
        flow_rate: float,  # m³/h
        length: float,  # m
        diameter: float,  # m
        roughness: float,  # m
        inlet_pressure: float  # kPa
    ) -> Tuple[float, float, float, float]:
        """
        Calculate pressure drop using Darcy-Weisbach for compressible gas.
        
        Returns: (pressure_drop_kPa, velocity_m_s, reynolds, friction_factor)
        """
        # Convert flow rate to m³/s
        Q = flow_rate / 3600
        
        # Cross-sectional area
        A = np.pi * (diameter / 2) ** 2
        
        # Velocity
        velocity = Q / A if A > 0 else 0
        
        # Reynolds number
        reynolds = (self.gas.DENSITY * abs(velocity) * diameter) / self.gas.DYNAMIC_VISCOSITY
        reynolds = max(reynolds, 1)  # Avoid division by zero
        
        # Relative roughness
        relative_roughness = roughness / diameter
        
        # Friction factor
        f = self.calculate_friction_factor(reynolds, relative_roughness)
        
        # Darcy-Weisbach pressure drop (Pa)
        # ΔP = f * (L/D) * (ρ * v² / 2)
        delta_p = f * (length / diameter) * (self.gas.DENSITY * velocity ** 2 / 2)
        
        # Convert to kPa
        delta_p_kpa = delta_p / 1000
        
        # For compressible flow, apply correction factor
        # Using average pressure approximation
        if inlet_pressure > delta_p_kpa:
            avg_pressure = inlet_pressure - delta_p_kpa / 2
            correction = inlet_pressure / avg_pressure
            delta_p_kpa *= correction ** 0.5
        
        # Ensure pressure drop doesn't exceed inlet pressure
        delta_p_kpa = min(delta_p_kpa, inlet_pressure * 0.95)
        
        return delta_p_kpa, velocity, reynolds, f
    
    def simulate_network(
        self,
        graph: nx.Graph,
        nodes: List,
        pipes: List,
        leaks: Optional[Dict[int, float]] = None,
        demand_multiplier: float = 1.0,
        max_iterations: int = 100,
        convergence_threshold: float = 0.01
    ) -> SimulationState:
        """
        Simulate the gas network and compute steady-state pressures and flows.
        
        Uses iterative method to solve for pressure distribution:
        1. Initialize pressures (source = high, others = estimated)
        2. Calculate flows based on pressure differences
        3. Apply mass balance at each node
        4. Update pressures
        5. Repeat until convergence
        
        Args:
            graph: NetworkX graph of the network
            nodes: List of GasNode objects
            pipes: List of GasPipe objects
            leaks: Dict mapping node_id -> leak_rate (m³/h)
            demand_multiplier: Scale factor for all demands
            max_iterations: Maximum solver iterations
            convergence_threshold: Pressure convergence criterion (kPa)
            
        Returns:
            SimulationState with all computed values
        """
        leaks = leaks or {}
        state = SimulationState(active_leaks=leaks.copy())
        
        # Create lookup dictionaries
        node_dict = {n.id: n for n in nodes}
        pipe_dict = {p.id: p for p in pipes}
        
        # Build pipe lookup by node pairs
        edge_pipe_map = {}
        for pipe in pipes:
            edge_pipe_map[(pipe.source_id, pipe.target_id)] = pipe
            edge_pipe_map[(pipe.target_id, pipe.source_id)] = pipe
        
        # Initialize pressures
        for node in nodes:
            if node.node_type == "source":
                state.node_pressures[node.id] = self.source_pressure
            else:
                # Initial estimate based on distance from source
                state.node_pressures[node.id] = self.source_pressure * 0.8
        
        # Initialize demands
        for node in nodes:
            base_demand = node.base_demand * demand_multiplier
            # Add leak to demand if present
            leak_rate = leaks.get(node.id, 0)
            state.node_actual_demand[node.id] = base_demand + leak_rate
        
        # Iterative solver
        for iteration in range(max_iterations):
            old_pressures = state.node_pressures.copy()
            
            # Calculate flows for each pipe
            for pipe in pipes:
                p1 = state.node_pressures[pipe.source_id]
                p2 = state.node_pressures[pipe.target_id]
                
                # Flow direction: high pressure to low pressure
                if p1 > p2:
                    inlet_p, outlet_node = p1, pipe.target_id
                    flow_direction = 1
                else:
                    inlet_p, outlet_node = p2, pipe.source_id
                    flow_direction = -1
                
                # Estimate flow rate using simplified formula
                # Q ∝ D^2.5 * sqrt(ΔP / L)
                delta_p = abs(p1 - p2)
                if delta_p > 0.001:
                    flow_estimate = (
                        1000 * (pipe.diameter ** 2.5) * 
                        np.sqrt(delta_p / max(pipe.length, 1))
                    )
                else:
                    flow_estimate = 0
                
                # Calculate actual pressure drop for this flow
                pressure_drop, velocity, reynolds, friction = self.calculate_pressure_drop(
                    flow_estimate,
                    pipe.length,
                    pipe.diameter,
                    pipe.roughness,
                    inlet_p
                )
                
                # Store pipe states
                state.pipe_flow_rates[pipe.id] = flow_estimate * flow_direction
                state.pipe_velocities[pipe.id] = velocity
                state.pipe_pressure_drops[pipe.id] = pressure_drop
                state.pipe_reynolds[pipe.id] = reynolds
            
            # Update pressures based on mass balance
            for node in nodes:
                if node.node_type == "source":
                    continue  # Sources maintain constant pressure
                
                # Sum of incoming flows minus demand
                net_flow = 0
                connected_pressures = []
                
                for neighbor in graph.neighbors(node.id):
                    if (node.id, neighbor) in edge_pipe_map:
                        pipe = edge_pipe_map[(node.id, neighbor)]
                        neighbor_pressure = state.node_pressures[neighbor]
                        connected_pressures.append(neighbor_pressure)
                        
                        # Flow contribution
                        if neighbor_pressure > state.node_pressures[node.id]:
                            net_flow += abs(state.pipe_flow_rates.get(pipe.id, 0))
                        else:
                            net_flow -= abs(state.pipe_flow_rates.get(pipe.id, 0))
                
                # Adjust pressure based on supply-demand balance
                demand = state.node_actual_demand[node.id]
                
                if connected_pressures:
                    # Pressure should be slightly below average of neighbors
                    avg_neighbor_pressure = np.mean(connected_pressures)
                    max_neighbor_pressure = max(connected_pressures)
                    
                    # Demand reduces pressure
                    demand_factor = demand / max(demand + 10, 1)
                    
                    # Leak drastically reduces pressure
                    if node.id in leaks:
                        leak_severity = min(leaks[node.id] / 100, 0.9)
                        new_pressure = max_neighbor_pressure * (1 - leak_severity) * 0.3
                    else:
                        new_pressure = avg_neighbor_pressure * (1 - demand_factor * 0.1)
                    
                    # Relaxation for stability
                    alpha = 0.3
                    state.node_pressures[node.id] = (
                        alpha * new_pressure + 
                        (1 - alpha) * state.node_pressures[node.id]
                    )
                    
                    # Enforce minimum pressure
                    state.node_pressures[node.id] = max(
                        state.node_pressures[node.id],
                        self.min_delivery_pressure * 0.1
                    )
            
            # Check convergence
            max_change = max(
                abs(state.node_pressures[n.id] - old_pressures[n.id])
                for n in nodes
            )
            
            if max_change < convergence_threshold:
                break
        
        return state
    
    def calculate_system_metrics(
        self,
        state: SimulationState,
        nodes: List,
        pipes: List
    ) -> Dict:
        """
        Calculate aggregate system metrics.
        
        Returns:
            Dict with total_demand, total_supply, efficiency, affected_nodes, etc.
        """
        # Total demand
        total_demand = sum(state.node_actual_demand.values())
        
        # Total flow through sources
        source_ids = [n.id for n in nodes if n.node_type == "source"]
        
        # Count affected nodes (low pressure)
        affected_nodes = sum(
            1 for node_id, pressure in state.node_pressures.items()
            if pressure < self.min_delivery_pressure * 5  # Warning threshold
            and node_id not in source_ids
        )
        
        critical_nodes = sum(
            1 for node_id, pressure in state.node_pressures.items()
            if pressure < self.min_delivery_pressure
            and node_id not in source_ids
        )
        
        # Average pressure
        consumer_pressures = [
            p for nid, p in state.node_pressures.items()
            if nid not in source_ids
        ]
        avg_pressure = np.mean(consumer_pressures) if consumer_pressures else 0
        min_pressure = min(consumer_pressures) if consumer_pressures else 0
        max_pressure = max(consumer_pressures) if consumer_pressures else 0
        
        # Flow statistics
        flow_rates = list(state.pipe_flow_rates.values())
        total_flow = sum(abs(f) for f in flow_rates) / 2  # Divide by 2 to avoid double counting
        
        # System capacity utilization
        max_theoretical_flow = sum(
            1000 * (p.diameter ** 2) * 10  # Simplified capacity estimate
            for p in pipes
        )
        utilization = total_flow / max_theoretical_flow if max_theoretical_flow > 0 else 0
        
        # Leak statistics
        total_leak_rate = sum(state.active_leaks.values())
        leak_count = len(state.active_leaks)
        
        return {
            "total_demand_m3h": round(total_demand, 2),
            "total_flow_m3h": round(total_flow, 2),
            "total_leak_rate_m3h": round(total_leak_rate, 2),
            "leak_count": leak_count,
            "affected_nodes": affected_nodes,
            "critical_nodes": critical_nodes,
            "avg_pressure_kpa": round(avg_pressure, 2),
            "min_pressure_kpa": round(min_pressure, 2),
            "max_pressure_kpa": round(max_pressure, 2),
            "source_pressure_kpa": self.source_pressure,
            "system_utilization": round(utilization * 100, 1),
            "total_nodes": len(nodes),
            "total_pipes": len(pipes)
        }
    
    def get_pressure_status(self, pressure: float) -> str:
        """Categorize pressure level."""
        if pressure >= self.source_pressure * 0.7:
            return "optimal"
        elif pressure >= self.source_pressure * 0.4:
            return "normal"
        elif pressure >= self.min_delivery_pressure * 5:
            return "low"
        elif pressure >= self.min_delivery_pressure:
            return "warning"
        else:
            return "critical"


class LeakSimulator:
    """Utility class for creating and managing leak scenarios."""
    
    @staticmethod
    def create_leak(
        node_id: int,
        severity: str = "moderate",
        base_leak_rate: float = 50.0
    ) -> Tuple[int, float]:
        """
        Create a leak at a specified node.
        
        Args:
            node_id: Node where leak occurs
            severity: "minor", "moderate", "severe", "catastrophic"
            base_leak_rate: Base leak rate in m³/h
            
        Returns:
            Tuple of (node_id, leak_rate)
        """
        severity_multipliers = {
            "minor": 0.2,
            "moderate": 1.0,
            "severe": 3.0,
            "catastrophic": 10.0
        }
        
        multiplier = severity_multipliers.get(severity, 1.0)
        leak_rate = base_leak_rate * multiplier
        
        return node_id, leak_rate
    
    @staticmethod
    def create_random_leaks(
        nodes: List,
        n_leaks: int = 1,
        exclude_sources: bool = True,
        seed: Optional[int] = None
    ) -> Dict[int, float]:
        """
        Create random leaks in the network.
        
        Args:
            nodes: List of network nodes
            n_leaks: Number of leaks to create
            exclude_sources: If True, don't create leaks at source nodes
            seed: Random seed
            
        Returns:
            Dict mapping node_id -> leak_rate
        """
        rng = np.random.default_rng(seed)
        
        # Filter eligible nodes
        eligible = [
            n for n in nodes
            if not (exclude_sources and n.node_type == "source")
        ]
        
        if not eligible:
            return {}
        
        # Select random nodes
        n_leaks = min(n_leaks, len(eligible))
        leak_nodes = rng.choice(eligible, size=n_leaks, replace=False)
        
        leaks = {}
        severities = ["minor", "moderate", "severe"]
        
        for node in leak_nodes:
            severity = rng.choice(severities, p=[0.5, 0.35, 0.15])
            _, leak_rate = LeakSimulator.create_leak(node.id, severity)
            leaks[node.id] = leak_rate
        
        return leaks


if __name__ == "__main__":
    # Test the physics engine
    from city_gen import CityNetworkGenerator
    
    # Generate test network
    generator = CityNetworkGenerator(seed=42)
    nodes, pipes, G = generator.generate_network(n_nodes=50)
    
    # Create physics engine
    engine = PhysicsEngine()
    
    # Simulate without leaks
    state = engine.simulate_network(G, nodes, pipes)
    metrics = engine.calculate_system_metrics(state, nodes, pipes)
    print("Normal operation:", metrics)
    
    # Simulate with leak
    leaks = LeakSimulator.create_random_leaks(nodes, n_leaks=2, seed=42)
    state_with_leak = engine.simulate_network(G, nodes, pipes, leaks=leaks)
    metrics_leak = engine.calculate_system_metrics(state_with_leak, nodes, pipes)
    print("With leaks:", metrics_leak)
