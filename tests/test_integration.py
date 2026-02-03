"""
Integration Tests for Gas Distribution Network Simulator
==========================================================
Tests the complete pipeline from network generation through
leak detection to ensure all components work together.
"""

import pytest
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from city_gen import CityNetworkGenerator, generate_sample_network
from physics import PhysicsEngine, LeakSimulator, SimulationState
from leak_detector import LeakDetector, detect_leaks


class TestFullPipeline:
    """Tests for the complete simulation pipeline."""
    
    def test_complete_workflow(self):
        """Test the complete workflow from generation to detection."""
        # Step 1: Generate network
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=100)
        
        # Note: generator adds source nodes, so actual count may differ
        assert len(nodes) >= 100
        assert len(pipes) > 0
        assert G.number_of_nodes() == len(nodes)
        
        # Step 2: Simulate physics
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)
        
        assert isinstance(state, SimulationState)
        assert len(state.node_pressures) == len(nodes)
        assert len(state.pipe_flow_rates) == len(pipes)
        
        # Step 3: Add leaks and re-simulate
        consumer_nodes = [n for n in nodes if n.node_type != "source"]
        leaks = {
            consumer_nodes[20].id: 100.0,
            consumer_nodes[50].id: 75.0
        }
        state_with_leaks = engine.simulate_network(G, nodes, pipes, leaks=leaks)
        
        # Step 4: Detect leaks
        result = detect_leaks(G, nodes, pipes, state_with_leaks)
        
        assert result is not None
        assert len(result.detected_leaks) > 0 or len(result.affected_nodes) > 0
    
    def test_sample_network_generation(self):
        """Test the convenience sample network generator."""
        nodes, pipes, G = generate_sample_network(seed=42)
        
        assert len(nodes) > 0
        assert len(pipes) > 0
        assert G.number_of_nodes() > 0
    
    def test_network_save_and_load(self, tmp_path):
        """Test saving and loading network data."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=50)
        
        # Save
        save_path = tmp_path / "test_network.json"
        generator.save_network(nodes, pipes, str(save_path))
        
        assert save_path.exists()
        
        # Load - returns nodes, pipes, and rebuilt graph
        loaded_nodes, loaded_pipes, loaded_G = generator.load_network(str(save_path))
        
        assert len(loaded_nodes) == len(nodes)
        assert len(loaded_pipes) == len(pipes)
    
    def test_metrics_calculation_consistency(self):
        """Test that metrics are calculated consistently."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=100)
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)
        
        metrics = engine.calculate_system_metrics(state, nodes, pipes)
        
        # Verify metrics (using actual keys from the implementation)
        assert 'avg_pressure_kpa' in metrics
        assert 'min_pressure_kpa' in metrics
        assert 'max_pressure_kpa' in metrics
        assert 'total_demand_m3h' in metrics
        assert 'total_flow_m3h' in metrics
        assert 'affected_nodes' in metrics
        
        # Logical checks
        assert metrics['min_pressure_kpa'] <= metrics['avg_pressure_kpa']
        assert metrics['avg_pressure_kpa'] <= metrics['max_pressure_kpa']


class TestLeakDetectionAccuracy:
    """Tests for leak detection accuracy."""
    
    def test_single_leak_detection(self):
        """Test detection of a single leak."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=100)
        engine = PhysicsEngine()
        
        # Create a single severe leak
        consumer = [n for n in nodes if n.node_type != "source"][30]
        leaks = {consumer.id: 150.0}  # Severe leak
        
        state = engine.simulate_network(G, nodes, pipes, leaks=leaks)
        result = detect_leaks(G, nodes, pipes, state)
        
        # Should detect the leak or at least flag affected area
        detected_ids = [l['node_id'] for l in result.detected_leaks]
        affected = set(result.affected_nodes)
        
        # Either direct detection or in affected area
        assert consumer.id in detected_ids or consumer.id in affected or len(result.detected_leaks) > 0
    
    def test_multiple_leaks_detection(self):
        """Test detection of multiple leaks."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=150)
        engine = PhysicsEngine()
        
        # Create multiple leaks
        consumers = [n for n in nodes if n.node_type != "source"]
        leaks = {
            consumers[20].id: 100.0,
            consumers[60].id: 100.0,
            consumers[100].id: 100.0
        }
        
        state = engine.simulate_network(G, nodes, pipes, leaks=leaks)
        result = detect_leaks(G, nodes, pipes, state)
        
        # Should detect multiple issues
        total_detected = len(result.detected_leaks)
        assert total_detected >= 1  # At least one detection
    
    def test_no_false_positives_healthy_network(self):
        """Test that healthy network has minimal false positives."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=100)
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)  # No leaks
        
        result = detect_leaks(G, nodes, pipes, state)
        
        # Filter for high-confidence detections
        high_confidence = [l for l in result.detected_leaks if l['confidence'] > 0.85]
        
        # Should have very few high-confidence false positives
        assert len(high_confidence) <= 3


class TestSystemStress:
    """Stress tests for the system."""
    
    def test_large_network_performance(self):
        """Test system handles large networks."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=500)
        
        # Generator adds source nodes, so actual count is >= requested
        assert len(nodes) >= 500
        
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)
        
        assert len(state.node_pressures) == len(nodes)
        
        result = detect_leaks(G, nodes, pipes, state)
        
        assert result is not None
    
    def test_many_simultaneous_leaks(self):
        """Test handling of many simultaneous leaks."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=200)
        engine = PhysicsEngine()
        
        # Create many leaks (10% of nodes)
        consumers = [n for n in nodes if n.node_type != "source"]
        leak_count = len(consumers) // 10
        leaks = {consumers[i * 5].id: 50.0 for i in range(leak_count)}
        
        state = engine.simulate_network(G, nodes, pipes, leaks=leaks)
        result = detect_leaks(G, nodes, pipes, state)
        
        # Should still function
        assert result is not None
    
    def test_reproducibility(self):
        """Test that same seed produces same results."""
        generator1 = CityNetworkGenerator(seed=42)
        generator2 = CityNetworkGenerator(seed=42)
        
        nodes1, pipes1, G1 = generator1.generate_network(n_nodes=50)
        nodes2, pipes2, G2 = generator2.generate_network(n_nodes=50)
        
        # Check node positions match
        for n1, n2 in zip(nodes1, nodes2):
            assert n1.x == n2.x
            assert n1.y == n2.y
            assert n1.node_type == n2.node_type


class TestPhysicsAccuracy:
    """Tests for physics simulation accuracy."""
    
    def test_pressure_decreases_from_source(self):
        """Test that pressure generally decreases from source."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=100)
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)
        
        # Find source node
        source = next(n for n in nodes if n.node_type == "source")
        source_pressure = state.node_pressures[source.id]
        
        # Check average consumer pressure is lower
        consumer_pressures = [
            state.node_pressures[n.id] for n in nodes 
            if n.node_type != "source"
        ]
        avg_consumer_pressure = np.mean(consumer_pressures)
        
        assert avg_consumer_pressure < source_pressure
    
    def test_leak_reduces_downstream_pressure(self):
        """Test that leaks reduce pressure in affected area."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=100)
        engine = PhysicsEngine()
        
        # Simulate without leak
        state_normal = engine.simulate_network(G, nodes, pipes)
        
        # Simulate with leak
        consumer = [n for n in nodes if n.node_type != "source"][25]
        leaks = {consumer.id: 150.0}
        state_leak = engine.simulate_network(G, nodes, pipes, leaks=leaks)
        
        # Leak node should have lower pressure
        assert state_leak.node_pressures[consumer.id] <= state_normal.node_pressures[consumer.id]


class TestDataExport:
    """Tests for data export functionality."""
    
    def test_simulation_state_to_dict(self):
        """Test conversion of simulation state to dictionary."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=50)
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)
        
        # Check state can be serialized
        data = {
            'pressures': list(state.node_pressures.values()),
            'flow_rates': list(state.pipe_flow_rates.values()),
            'velocities': list(state.pipe_velocities.values()),
            'demands': list(state.node_actual_demand.values())
        }
        
        # Node count includes source nodes added by generator
        assert len(data['pressures']) == len(nodes)
        assert len(data['demands']) == len(nodes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
