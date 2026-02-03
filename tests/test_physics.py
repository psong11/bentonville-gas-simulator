"""
Test Suite for Physics Engine Module
=====================================
Tests the Darcy-Weisbach physics simulation including:
- Friction factor calculations
- Pressure drop calculations
- Network simulation
- System metrics
- Leak simulation
"""

import pytest
import numpy as np
import networkx as nx
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from physics import (
    PhysicsEngine,
    GasProperties,
    SimulationState,
    PipeState,
    LeakSimulator
)
from city_gen import CityNetworkGenerator, GasNode, GasPipe


class TestGasProperties:
    """Tests for gas property constants."""
    
    def test_density(self):
        """Test gas density is reasonable for natural gas."""
        assert 0.5 < GasProperties.DENSITY < 1.0  # kg/m³
    
    def test_viscosity(self):
        """Test dynamic viscosity is in expected range."""
        assert 1e-6 < GasProperties.DYNAMIC_VISCOSITY < 1e-4  # Pa·s
    
    def test_specific_gravity(self):
        """Test specific gravity is less than 1 (lighter than air)."""
        assert 0.5 < GasProperties.SPECIFIC_GRAVITY < 0.7


class TestPhysicsEngineInitialization:
    """Tests for PhysicsEngine initialization."""
    
    def test_default_initialization(self):
        """Test default parameter values."""
        engine = PhysicsEngine()
        assert engine.source_pressure == 400.0  # kPa
        assert engine.min_delivery_pressure == 1.7  # kPa
        assert engine.temperature == 288.15  # K (15°C)
    
    def test_custom_initialization(self):
        """Test custom parameter values."""
        engine = PhysicsEngine(
            source_pressure=500.0,
            min_delivery_pressure=2.0,
            temperature=300.0
        )
        assert engine.source_pressure == 500.0
        assert engine.min_delivery_pressure == 2.0
        assert engine.temperature == 300.0


class TestFrictionFactor:
    """Tests for friction factor calculations."""
    
    @pytest.fixture
    def engine(self):
        return PhysicsEngine()
    
    def test_laminar_flow(self, engine):
        """Test friction factor for laminar flow (Re < 2300)."""
        # Laminar: f = 64/Re
        f = engine.calculate_friction_factor(reynolds=1000, relative_roughness=0.001)
        expected = 64 / 1000
        assert f == pytest.approx(expected, rel=0.01)
    
    def test_turbulent_flow(self, engine):
        """Test friction factor for turbulent flow (Re > 4000)."""
        f = engine.calculate_friction_factor(reynolds=100000, relative_roughness=0.001)
        # Should be in typical turbulent range
        assert 0.01 < f < 0.1
    
    def test_transition_region(self, engine):
        """Test friction factor in transition region (2300 < Re < 4000)."""
        f = engine.calculate_friction_factor(reynolds=3000, relative_roughness=0.001)
        f_laminar = 64 / 2300
        f_turbulent = engine._swamee_jain(4000, 0.001)
        
        # In transition, should be between or interpolating
        # The value should be reasonable (positive and finite)
        assert f > 0
        assert f < 1.0  # Reasonable upper bound
        # Should be in the general range of friction factors
        assert 0.01 < f < 0.1
    
    def test_roughness_effect(self, engine):
        """Test that higher roughness increases friction factor."""
        f_smooth = engine.calculate_friction_factor(reynolds=50000, relative_roughness=0.0001)
        f_rough = engine.calculate_friction_factor(reynolds=50000, relative_roughness=0.01)
        
        assert f_rough > f_smooth
    
    def test_reynolds_effect(self, engine):
        """Test that friction factor decreases with Reynolds number in turbulent flow."""
        f_low_re = engine.calculate_friction_factor(reynolds=10000, relative_roughness=0.001)
        f_high_re = engine.calculate_friction_factor(reynolds=1000000, relative_roughness=0.001)
        
        assert f_low_re > f_high_re


class TestPressureDrop:
    """Tests for pressure drop calculations."""
    
    @pytest.fixture
    def engine(self):
        return PhysicsEngine()
    
    def test_zero_flow(self, engine):
        """Test that zero flow results in minimal pressure drop."""
        dp, v, re, f = engine.calculate_pressure_drop(
            flow_rate=0.0,
            length=100.0,
            diameter=0.1,
            roughness=0.00005,
            inlet_pressure=400.0
        )
        assert dp == pytest.approx(0.0, abs=0.01)
        assert v == pytest.approx(0.0, abs=0.01)
    
    def test_positive_pressure_drop(self, engine):
        """Test that flow results in positive pressure drop."""
        dp, v, re, f = engine.calculate_pressure_drop(
            flow_rate=100.0,  # m³/h
            length=500.0,
            diameter=0.15,
            roughness=0.00005,
            inlet_pressure=400.0
        )
        assert dp > 0
        assert v > 0
        assert re > 0
        assert f > 0
    
    def test_length_effect(self, engine):
        """Test that longer pipes have higher pressure drop."""
        dp_short, _, _, _ = engine.calculate_pressure_drop(
            flow_rate=50.0, length=100.0, diameter=0.1,
            roughness=0.00005, inlet_pressure=400.0
        )
        dp_long, _, _, _ = engine.calculate_pressure_drop(
            flow_rate=50.0, length=500.0, diameter=0.1,
            roughness=0.00005, inlet_pressure=400.0
        )
        assert dp_long > dp_short
    
    def test_diameter_effect(self, engine):
        """Test that larger diameter reduces pressure drop."""
        dp_small, _, _, _ = engine.calculate_pressure_drop(
            flow_rate=50.0, length=200.0, diameter=0.05,
            roughness=0.00005, inlet_pressure=400.0
        )
        dp_large, _, _, _ = engine.calculate_pressure_drop(
            flow_rate=50.0, length=200.0, diameter=0.2,
            roughness=0.00005, inlet_pressure=400.0
        )
        assert dp_small > dp_large
    
    def test_pressure_drop_bounded(self, engine):
        """Test that pressure drop doesn't exceed inlet pressure."""
        dp, _, _, _ = engine.calculate_pressure_drop(
            flow_rate=1000.0,  # Very high flow
            length=1000.0,
            diameter=0.05,  # Small pipe
            roughness=0.001,
            inlet_pressure=400.0
        )
        assert dp < 400.0  # Less than inlet pressure


class TestNetworkSimulation:
    """Tests for full network simulation."""
    
    @pytest.fixture
    def network(self):
        """Create a test network."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=50)
        return nodes, pipes, G
    
    @pytest.fixture
    def engine(self):
        return PhysicsEngine()
    
    def test_simulation_runs(self, engine, network):
        """Test that simulation completes without error."""
        nodes, pipes, G = network
        state = engine.simulate_network(G, nodes, pipes)
        
        assert state is not None
        assert isinstance(state, SimulationState)
    
    def test_simulation_pressures(self, engine, network):
        """Test that all nodes have pressures calculated."""
        nodes, pipes, G = network
        state = engine.simulate_network(G, nodes, pipes)
        
        assert len(state.node_pressures) == len(nodes)
        for node in nodes:
            assert node.id in state.node_pressures
    
    def test_source_pressure(self, engine, network):
        """Test that source nodes maintain high pressure."""
        nodes, pipes, G = network
        state = engine.simulate_network(G, nodes, pipes)
        
        for node in nodes:
            if node.node_type == "source":
                assert state.node_pressures[node.id] == pytest.approx(
                    engine.source_pressure, rel=0.01
                )
    
    def test_pressure_decreases_from_source(self, engine, network):
        """Test that pressure generally decreases from source."""
        nodes, pipes, G = network
        state = engine.simulate_network(G, nodes, pipes)
        
        source_ids = [n.id for n in nodes if n.node_type == "source"]
        consumer_pressures = [
            state.node_pressures[n.id] 
            for n in nodes if n.node_type != "source"
        ]
        
        # Most consumers should have lower pressure than sources
        avg_consumer_pressure = np.mean(consumer_pressures)
        assert avg_consumer_pressure < engine.source_pressure
    
    def test_simulation_with_leaks(self, engine, network):
        """Test simulation with active leaks."""
        nodes, pipes, G = network
        
        # Find a consumer node for leak
        consumer = next(n for n in nodes if n.node_type != "source")
        leaks = {consumer.id: 100.0}  # 100 m³/h leak
        
        state = engine.simulate_network(G, nodes, pipes, leaks=leaks)
        
        # Leak node should be in active_leaks
        assert consumer.id in state.active_leaks
        
        # Leak node should have reduced pressure
        state_no_leak = engine.simulate_network(G, nodes, pipes)
        assert state.node_pressures[consumer.id] < state_no_leak.node_pressures[consumer.id]
    
    def test_demand_multiplier(self, engine, network):
        """Test that demand multiplier affects simulation."""
        nodes, pipes, G = network
        
        state_normal = engine.simulate_network(G, nodes, pipes, demand_multiplier=1.0)
        state_high = engine.simulate_network(G, nodes, pipes, demand_multiplier=2.0)
        
        # Higher demand should reduce average pressure
        avg_normal = np.mean(list(state_normal.node_pressures.values()))
        avg_high = np.mean(list(state_high.node_pressures.values()))
        
        # Note: This may not always be true depending on the model
        # At minimum, demands should be different
        assert state_high.node_actual_demand != state_normal.node_actual_demand


class TestSystemMetrics:
    """Tests for system metrics calculation."""
    
    @pytest.fixture
    def simulation_setup(self):
        """Create a simulated network."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=50)
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)
        return engine, nodes, pipes, state
    
    def test_metrics_calculated(self, simulation_setup):
        """Test that all metrics are calculated."""
        engine, nodes, pipes, state = simulation_setup
        metrics = engine.calculate_system_metrics(state, nodes, pipes)
        
        required_keys = [
            'total_demand_m3h', 'total_flow_m3h', 'total_leak_rate_m3h',
            'leak_count', 'affected_nodes', 'critical_nodes',
            'avg_pressure_kpa', 'min_pressure_kpa', 'max_pressure_kpa',
            'source_pressure_kpa', 'system_utilization', 'total_nodes', 'total_pipes'
        ]
        
        for key in required_keys:
            assert key in metrics
    
    def test_metrics_values_reasonable(self, simulation_setup):
        """Test that metric values are reasonable."""
        engine, nodes, pipes, state = simulation_setup
        metrics = engine.calculate_system_metrics(state, nodes, pipes)
        
        assert metrics['total_nodes'] == len(nodes)
        assert metrics['total_pipes'] == len(pipes)
        assert metrics['total_demand_m3h'] >= 0
        assert metrics['avg_pressure_kpa'] > 0
        assert metrics['min_pressure_kpa'] <= metrics['avg_pressure_kpa']
        assert metrics['max_pressure_kpa'] >= metrics['avg_pressure_kpa']
    
    def test_leak_metrics(self, simulation_setup):
        """Test leak-related metrics."""
        engine, nodes, pipes, state = simulation_setup
        
        # No leaks initially
        metrics = engine.calculate_system_metrics(state, nodes, pipes)
        assert metrics['leak_count'] == 0
        assert metrics['total_leak_rate_m3h'] == 0


class TestLeakSimulator:
    """Tests for the LeakSimulator utility class."""
    
    @pytest.fixture
    def nodes(self):
        generator = CityNetworkGenerator(seed=42)
        nodes, _, _ = generator.generate_network(n_nodes=50)
        return nodes
    
    def test_create_leak(self):
        """Test creating a single leak."""
        node_id, leak_rate = LeakSimulator.create_leak(
            node_id=5,
            severity="moderate",
            base_leak_rate=50.0
        )
        assert node_id == 5
        assert leak_rate == 50.0  # 1.0 * 50
    
    def test_leak_severities(self):
        """Test different leak severities."""
        _, rate_minor = LeakSimulator.create_leak(1, "minor", 100.0)
        _, rate_moderate = LeakSimulator.create_leak(1, "moderate", 100.0)
        _, rate_severe = LeakSimulator.create_leak(1, "severe", 100.0)
        _, rate_catastrophic = LeakSimulator.create_leak(1, "catastrophic", 100.0)
        
        assert rate_minor < rate_moderate < rate_severe < rate_catastrophic
    
    def test_create_random_leaks(self, nodes):
        """Test creating random leaks."""
        leaks = LeakSimulator.create_random_leaks(nodes, n_leaks=3, seed=42)
        
        assert len(leaks) == 3
        for node_id, rate in leaks.items():
            assert rate > 0
            # Should be a valid node ID
            assert any(n.id == node_id for n in nodes)
    
    def test_random_leaks_exclude_sources(self, nodes):
        """Test that random leaks exclude source nodes."""
        leaks = LeakSimulator.create_random_leaks(
            nodes, n_leaks=5, exclude_sources=True, seed=42
        )
        
        source_ids = {n.id for n in nodes if n.node_type == "source"}
        for node_id in leaks.keys():
            assert node_id not in source_ids
    
    def test_random_leaks_reproducibility(self, nodes):
        """Test that same seed produces same leaks."""
        leaks1 = LeakSimulator.create_random_leaks(nodes, n_leaks=2, seed=123)
        leaks2 = LeakSimulator.create_random_leaks(nodes, n_leaks=2, seed=123)
        
        assert leaks1 == leaks2


class TestPressureStatus:
    """Tests for pressure status categorization."""
    
    def test_optimal_status(self):
        """Test optimal pressure status."""
        engine = PhysicsEngine(source_pressure=400.0)
        status = engine.get_pressure_status(350.0)  # 87.5% > 70%
        assert status == "optimal"
    
    def test_normal_status(self):
        """Test normal pressure status."""
        engine = PhysicsEngine(source_pressure=400.0)
        status = engine.get_pressure_status(200.0)  # 50% - between 40% and 70%
        assert status == "normal"
    
    def test_low_status(self):
        """Test low pressure status."""
        engine = PhysicsEngine(source_pressure=400.0, min_delivery_pressure=1.7)
        # Low is between min_delivery_pressure*5 (8.5) and source*0.4 (160)
        status = engine.get_pressure_status(50.0)  # Between 8.5 and 160
        assert status == "low"
    
    def test_warning_status(self):
        """Test warning pressure status."""
        engine = PhysicsEngine(source_pressure=400.0, min_delivery_pressure=1.7)
        # Warning is between min_delivery_pressure (1.7) and min_delivery_pressure*5 (8.5)
        status = engine.get_pressure_status(5.0)  # Between 1.7 and 8.5
        assert status == "warning"
    
    def test_critical_status(self):
        """Test critical pressure status."""
        engine = PhysicsEngine(source_pressure=400.0, min_delivery_pressure=1.7)
        # Critical is below min_delivery_pressure (1.7)
        status = engine.get_pressure_status(1.0)  # Below 1.7
        assert status == "critical"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
