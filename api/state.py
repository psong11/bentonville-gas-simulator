"""
Application State Manager
=========================
Manages in-memory state for network, simulation, and leaks.
This will be replaced by PostgreSQL queries in Phase 6.

Key Responsibility: Wraps existing Python modules (city_gen, physics, leak_detector)
and exposes them through a clean interface for the API.
"""

import time
from typing import List, Optional, Dict
from pathlib import Path
import random

# Import existing modules (they stay unchanged!)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from city_gen import CityNetworkGenerator, GasNode, GasPipe
from physics import PhysicsEngine, SimulationState
from leak_detector import LeakDetector

from api.schemas import (
    NetworkResponse,
    NodeSchema,
    PipeSchema,
    SimulationResponse,
    LeakDetectionResponse,
    InjectLeaksResponse,
    SuspectedLeak,
)


class AppState:
    """
    Centralized application state manager.
    
    Currently stores everything in memory.
    Phase 6 will replace this with PostgreSQL queries.
    """
    
    # Path to network data file (legacy, will be replaced by PostgreSQL)
    DATA_PATH = Path(__file__).parent.parent / "data" / "network.json"
    
    def __init__(self):
        self.nodes: List[GasNode] = []
        self.pipes: List[GasPipe] = []
        self.graph = None
        
        self.physics_engine = PhysicsEngine()
        self.leak_detector = LeakDetector()
        
        # Current simulation parameters (remembered between calls)
        self.current_source_pressure: float = 400.0
        self.current_demand_multiplier: float = 1.0
        self.current_active_leaks: List[int] = []
        
        # Cached simulation state
        self._simulation_state: Optional[SimulationState] = None
    
    def load_network_if_exists(self) -> bool:
        """Load existing network from file if available."""
        if self.DATA_PATH.exists():
            try:
                self.nodes, self.pipes, self.graph = CityNetworkGenerator.load_network(
                    str(self.DATA_PATH)
                )
                print(f"✅ Loaded network: {len(self.nodes)} nodes, {len(self.pipes)} pipes")
                # Run initial simulation
                self._run_simulation_internal()
                return True
            except Exception as e:
                print(f"⚠️ Failed to load network: {e}")
                return False
        return False
    
    def get_network(self) -> NetworkResponse:
        """Get current network configuration."""
        if not self.nodes:
            # Generate default network if none exists
            return self.generate_network(50)
        
        return NetworkResponse(
            nodes=[NodeSchema.model_validate(n.to_dict()) for n in self.nodes],
            pipes=[PipeSchema.model_validate(p.to_dict()) for p in self.pipes],
        )
    
    def generate_network(self, node_count: int) -> NetworkResponse:
        """Generate a new network with the specified number of nodes."""
        generator = CityNetworkGenerator()
        self.nodes, self.pipes, self.graph = generator.generate_network(n_nodes=node_count)
        
        # Save to file (legacy persistence)
        self.DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        generator.save_network(self.nodes, self.pipes, str(self.DATA_PATH))
        
        # Reset simulation state
        self.current_active_leaks = []
        self._simulation_state = None
        self._run_simulation_internal()
        
        print(f"✅ Generated network: {len(self.nodes)} nodes, {len(self.pipes)} pipes")
        
        return NetworkResponse(
            nodes=[NodeSchema.model_validate(n.to_dict()) for n in self.nodes],
            pipes=[PipeSchema.model_validate(p.to_dict()) for p in self.pipes],
        )
    
    def run_simulation(
        self,
        source_pressure: Optional[float] = None,
        demand_multiplier: Optional[float] = None,
        active_leaks: Optional[List[int]] = None,
    ) -> SimulationResponse:
        """
        Run physics simulation with given parameters.
        
        Parameters are sticky - if not provided, uses last value.
        This allows WebSocket clients to change one parameter at a time.
        """
        # Update parameters if provided
        if source_pressure is not None:
            self.current_source_pressure = source_pressure
            self.physics_engine.source_pressure = source_pressure
        
        if demand_multiplier is not None:
            self.current_demand_multiplier = demand_multiplier
        
        if active_leaks is not None:
            self.current_active_leaks = active_leaks
        
        return self._run_simulation_internal()
    
    def _run_simulation_internal(self) -> SimulationResponse:
        """Internal simulation runner."""
        if not self.nodes or not self.pipes:
            # Return empty state if no network
            return SimulationResponse(
                node_pressures={},
                node_actual_demand={},
                pipe_flow_rates={},
                pipe_velocities={},
                pipe_pressure_drops={},
                pipe_reynolds={},
                active_leaks={},
                warnings=["No network loaded"],
            )
        
        # Prepare leak rates dict
        leak_rates = {node_id: 50.0 for node_id in self.current_active_leaks}
        
        # Run simulation
        self._simulation_state = self.physics_engine.simulate_network(
            graph=self.graph,
            nodes=self.nodes,
            pipes=self.pipes,
            leaks=leak_rates,
            demand_multiplier=self.current_demand_multiplier,
        )
        
        # Collect warnings
        warnings = []
        for node_id, pressure in self._simulation_state.node_pressures.items():
            status = self.physics_engine.get_pressure_status(pressure)
            if status in ("critical", "low"):
                node = next((n for n in self.nodes if n.id == node_id), None)
                if node:
                    warnings.append(f"{status.title()} pressure at {node.name}: {pressure:.1f} kPa")
        
        return SimulationResponse(
            node_pressures={str(k): v for k, v in self._simulation_state.node_pressures.items()},
            node_actual_demand={str(k): v for k, v in self._simulation_state.node_actual_demand.items()},
            pipe_flow_rates={str(k): v for k, v in self._simulation_state.pipe_flow_rates.items()},
            pipe_velocities={str(k): v for k, v in self._simulation_state.pipe_velocities.items()},
            pipe_pressure_drops={str(k): v for k, v in self._simulation_state.pipe_pressure_drops.items()},
            pipe_reynolds={str(k): v for k, v in self._simulation_state.pipe_reynolds.items()},
            active_leaks={str(k): v for k, v in self._simulation_state.active_leaks.items()},
            warnings=warnings[:10],  # Limit to 10 warnings
        )
    
    def get_current_simulation_state(self) -> SimulationResponse:
        """Get current simulation state without re-running."""
        if self._simulation_state is None:
            return self.run_simulation()
        
        return SimulationResponse(
            node_pressures={str(k): v for k, v in self._simulation_state.node_pressures.items()},
            node_actual_demand={str(k): v for k, v in self._simulation_state.node_actual_demand.items()},
            pipe_flow_rates={str(k): v for k, v in self._simulation_state.pipe_flow_rates.items()},
            pipe_velocities={str(k): v for k, v in self._simulation_state.pipe_velocities.items()},
            pipe_pressure_drops={str(k): v for k, v in self._simulation_state.pipe_pressure_drops.items()},
            pipe_reynolds={str(k): v for k, v in self._simulation_state.pipe_reynolds.items()},
            active_leaks={str(k): v for k, v in self._simulation_state.active_leaks.items()},
            warnings=[],
        )
    
    def detect_leaks(self, strategy: str) -> LeakDetectionResponse:
        """Run leak detection with the specified strategy."""
        start_time = time.time()
        
        if self._simulation_state is None:
            self._run_simulation_internal()
        
        # Run detection using the analyze_network method
        result = self.leak_detector.analyze_network(
            graph=self.graph,
            nodes=self.nodes,
            pipes=self.pipes,
            simulation_state=self._simulation_state,
        )
        
        detection_time = (time.time() - start_time) * 1000
        
        # Convert to response schema
        suspected = []
        for leak in result.detected_leaks:
            suspected.append(SuspectedLeak(
                node_id=leak['node_id'],
                confidence=leak['confidence'],
                reason=leak.get('reason', f"Severity: {leak.get('estimated_severity', 'Unknown')}"),
                pressure=leak.get('pressure'),
                flow_imbalance=leak.get('flow_imbalance'),
            ))
        
        return LeakDetectionResponse(
            suspected_leaks=suspected,
            strategy_used=strategy,
            detection_time_ms=detection_time,
        )
    
    def inject_leaks(self, count: int) -> InjectLeaksResponse:
        """Inject random leaks into non-source nodes."""
        # Get eligible nodes (non-source)
        eligible = [n for n in self.nodes if n.node_type != "source"]
        
        if not eligible:
            return InjectLeaksResponse(injected_node_ids=[])
        
        # Select random nodes
        count = min(count, len(eligible))
        selected = random.sample(eligible, count)
        
        # Add to active leaks
        for node in selected:
            if node.id not in self.current_active_leaks:
                self.current_active_leaks.append(node.id)
        
        return InjectLeaksResponse(
            injected_node_ids=[n.id for n in selected]
        )
    
    def clear_leaks(self) -> None:
        """Clear all active leaks."""
        self.current_active_leaks = []
        if self._simulation_state:
            self._simulation_state.active_leaks = {}
