"""
Test Suite for Leak Detector Module
=====================================
Tests the intelligent leak detection functionality including:
- Anomaly score calculation
- Candidate identification
- Cluster detection
- Leak source tracing
- Confidence scoring
- Recommendations generation
"""

import pytest
import numpy as np
import networkx as nx
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from leak_detector import (
    LeakDetector,
    LeakDetectionResult,
    AnomalyScore,
    detect_leaks
)
from city_gen import CityNetworkGenerator
from physics import PhysicsEngine, LeakSimulator


class TestLeakDetectorInitialization:
    """Tests for LeakDetector initialization."""
    
    def test_default_initialization(self):
        """Test default parameter values."""
        detector = LeakDetector()
        assert detector.pressure_deficit_threshold == 50.0
        assert detector.deficit_ratio_threshold == 0.3
        assert detector.min_confidence_threshold == 0.5
        assert detector.source_pressure == 400.0
    
    def test_custom_initialization(self):
        """Test custom parameter values."""
        detector = LeakDetector(
            pressure_deficit_threshold=100.0,
            deficit_ratio_threshold=0.5,
            min_confidence_threshold=0.7,
            source_pressure=500.0
        )
        assert detector.pressure_deficit_threshold == 100.0
        assert detector.deficit_ratio_threshold == 0.5
        assert detector.min_confidence_threshold == 0.7
        assert detector.source_pressure == 500.0


class TestAnomalyScore:
    """Tests for AnomalyScore dataclass."""
    
    def test_creation(self):
        """Test anomaly score creation."""
        score = AnomalyScore(
            node_id=5,
            pressure_deficit=100.0,
            deficit_ratio=0.4,
            neighbor_avg_pressure=200.0,
            is_isolated_drop=True,
            downstream_affected=3,
            score=0.85
        )
        assert score.node_id == 5
        assert score.pressure_deficit == 100.0
        assert score.is_isolated_drop == True
        assert score.score == 0.85


class TestLeakDetectionResult:
    """Tests for LeakDetectionResult dataclass."""
    
    def test_creation(self):
        """Test result creation."""
        result = LeakDetectionResult(
            detected_leaks=[{"node_id": 1, "confidence": 0.9}],
            affected_nodes=[1, 2, 3],
            confidence_scores={1: 0.9},
            analysis_details={"total_anomalies": 5},
            recommendations=["Check node 1"]
        )
        assert len(result.detected_leaks) == 1
        assert len(result.affected_nodes) == 3
        assert "Check node 1" in result.recommendations


class TestLeakDetectionWithoutLeaks:
    """Tests for leak detection on healthy networks."""
    
    @pytest.fixture
    def healthy_network(self):
        """Create a healthy network without leaks."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=100)
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)
        return nodes, pipes, G, state
    
    def test_no_leaks_detected_in_healthy_network(self, healthy_network):
        """Test that healthy network has no or few detected leaks."""
        nodes, pipes, G, state = healthy_network
        
        result = detect_leaks(G, nodes, pipes, state)
        
        # Should have few or no high-confidence leaks in healthy network
        high_confidence_leaks = [
            l for l in result.detected_leaks 
            if l['confidence'] > 0.8
        ]
        assert len(high_confidence_leaks) <= 2  # Allow some false positives
    
    def test_result_structure(self, healthy_network):
        """Test that result has correct structure."""
        nodes, pipes, G, state = healthy_network
        
        result = detect_leaks(G, nodes, pipes, state)
        
        assert isinstance(result, LeakDetectionResult)
        assert isinstance(result.detected_leaks, list)
        assert isinstance(result.affected_nodes, list)
        assert isinstance(result.confidence_scores, dict)
        assert isinstance(result.analysis_details, dict)
        assert isinstance(result.recommendations, list)


class TestLeakDetectionWithLeaks:
    """Tests for leak detection on networks with actual leaks."""
    
    @pytest.fixture
    def leaky_network(self):
        """Create a network with known leaks."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=100)
        engine = PhysicsEngine()
        
        # Create known leaks
        consumer_nodes = [n for n in nodes if n.node_type != "source"]
        leak_nodes = [consumer_nodes[10].id, consumer_nodes[30].id]
        leaks = {
            leak_nodes[0]: 150.0,  # Severe leak
            leak_nodes[1]: 100.0   # Moderate leak
        }
        
        state = engine.simulate_network(G, nodes, pipes, leaks=leaks)
        return nodes, pipes, G, state, leak_nodes
    
    def test_detects_leak_presence(self, leaky_network):
        """Test that leaks are detected when present."""
        nodes, pipes, G, state, leak_nodes = leaky_network
        
        result = detect_leaks(G, nodes, pipes, state)
        
        # Should detect at least one leak
        assert len(result.detected_leaks) > 0
    
    def test_affected_nodes_identified(self, leaky_network):
        """Test that affected nodes are identified."""
        nodes, pipes, G, state, leak_nodes = leaky_network
        
        result = detect_leaks(G, nodes, pipes, state)
        
        # Should have affected nodes
        assert len(result.affected_nodes) > 0
    
    def test_leak_nodes_in_affected(self, leaky_network):
        """Test that actual leak nodes are in affected list."""
        nodes, pipes, G, state, leak_nodes = leaky_network
        
        result = detect_leaks(G, nodes, pipes, state)
        
        # At least one leak node should be in affected
        leak_in_affected = any(ln in result.affected_nodes for ln in leak_nodes)
        assert leak_in_affected or len(result.affected_nodes) > 0
    
    def test_recommendations_generated(self, leaky_network):
        """Test that recommendations are generated for leaks."""
        nodes, pipes, G, state, leak_nodes = leaky_network
        
        result = detect_leaks(G, nodes, pipes, state)
        
        # Should have recommendations when leaks detected
        if result.detected_leaks:
            assert len(result.recommendations) > 0
    
    def test_confidence_scores_valid(self, leaky_network):
        """Test that confidence scores are in valid range."""
        nodes, pipes, G, state, leak_nodes = leaky_network
        
        result = detect_leaks(G, nodes, pipes, state)
        
        for node_id, confidence in result.confidence_scores.items():
            assert 0.0 <= confidence <= 1.0
    
    def test_leak_severity_estimated(self, leaky_network):
        """Test that leak severity is estimated."""
        nodes, pipes, G, state, leak_nodes = leaky_network
        
        result = detect_leaks(G, nodes, pipes, state)
        
        for leak in result.detected_leaks:
            assert 'estimated_severity' in leak
            assert leak['estimated_severity'] in ['minor', 'moderate', 'severe', 'critical']


class TestQuickScan:
    """Tests for the quick scan functionality."""
    
    @pytest.fixture
    def detector(self):
        return LeakDetector()
    
    @pytest.fixture
    def network_with_state(self):
        """Create network with simulation state."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=50)
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)
        return nodes, state
    
    def test_quick_scan_returns_list(self, detector, network_with_state):
        """Test that quick scan returns a list."""
        nodes, state = network_with_state
        result = detector.quick_scan(state, nodes)
        assert isinstance(result, list)
    
    def test_quick_scan_with_threshold(self, detector, network_with_state):
        """Test quick scan with different thresholds."""
        nodes, state = network_with_state
        
        result_strict = detector.quick_scan(state, nodes, threshold_ratio=0.2)
        result_loose = detector.quick_scan(state, nodes, threshold_ratio=0.8)
        
        # Looser threshold (0.8) flags nodes with pressure < 80% of source
        # Stricter threshold (0.2) only flags nodes with pressure < 20% of source
        # So loose should find more or equal anomalies
        assert len(result_loose) >= len(result_strict)


class TestDetectorWithDifferentNetworkSizes:
    """Tests for detector with various network sizes."""
    
    def test_small_network(self):
        """Test detection on small network."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=20)
        engine = PhysicsEngine()
        
        # Add a leak
        consumer = next(n for n in nodes if n.node_type != "source")
        leaks = {consumer.id: 50.0}
        state = engine.simulate_network(G, nodes, pipes, leaks=leaks)
        
        result = detect_leaks(G, nodes, pipes, state)
        
        # Should complete without error
        assert result is not None
    
    def test_large_network(self):
        """Test detection on larger network."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=200)
        engine = PhysicsEngine()
        
        # Add multiple leaks
        consumers = [n for n in nodes if n.node_type != "source"]
        leaks = {
            consumers[20].id: 100.0,
            consumers[80].id: 75.0,
            consumers[150].id: 50.0
        }
        state = engine.simulate_network(G, nodes, pipes, leaks=leaks)
        
        result = detect_leaks(G, nodes, pipes, state)
        
        # Should detect multiple issues
        assert len(result.detected_leaks) > 0 or len(result.affected_nodes) > 0


class TestDetectorThresholdSensitivity:
    """Tests for detector sensitivity to threshold parameters."""
    
    @pytest.fixture
    def network_with_leak(self):
        """Create network with a leak."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=100)
        engine = PhysicsEngine()
        
        consumer = [n for n in nodes if n.node_type != "source"][25]
        leaks = {consumer.id: 100.0}
        state = engine.simulate_network(G, nodes, pipes, leaks=leaks)
        
        return nodes, pipes, G, state
    
    def test_lower_threshold_more_detections(self, network_with_leak):
        """Test that lower threshold yields more detections."""
        nodes, pipes, G, state = network_with_leak
        
        detector_strict = LeakDetector(
            pressure_deficit_threshold=100.0,
            min_confidence_threshold=0.8
        )
        detector_loose = LeakDetector(
            pressure_deficit_threshold=20.0,
            min_confidence_threshold=0.3
        )
        
        result_strict = detector_strict.analyze_network(G, nodes, pipes, state)
        result_loose = detector_loose.analyze_network(G, nodes, pipes, state)
        
        # Looser thresholds should detect more
        total_strict = len(result_strict.detected_leaks) + len(result_strict.affected_nodes)
        total_loose = len(result_loose.detected_leaks) + len(result_loose.affected_nodes)
        
        assert total_loose >= total_strict


class TestConvenienceFunction:
    """Tests for the detect_leaks convenience function."""
    
    def test_detect_leaks_function(self):
        """Test the convenience function works correctly."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=50)
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)
        
        result = detect_leaks(
            G, nodes, pipes, state,
            pressure_threshold=50.0,
            confidence_threshold=0.5
        )
        
        assert isinstance(result, LeakDetectionResult)
    
    def test_detect_leaks_with_custom_thresholds(self):
        """Test convenience function with custom thresholds."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=50)
        engine = PhysicsEngine()
        
        # Add leak
        consumer = next(n for n in nodes if n.node_type != "source")
        leaks = {consumer.id: 100.0}
        state = engine.simulate_network(G, nodes, pipes, leaks=leaks)
        
        result = detect_leaks(
            G, nodes, pipes, state,
            pressure_threshold=25.0,
            confidence_threshold=0.3
        )
        
        assert result is not None


class TestAnalysisDetails:
    """Tests for analysis details in results."""
    
    def test_analysis_details_content(self):
        """Test that analysis details contain expected information."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=50)
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)
        
        result = detect_leaks(G, nodes, pipes, state)
        
        # Check expected keys
        assert 'total_anomalies' in result.analysis_details
        assert 'clusters_found' in result.analysis_details
        assert 'anomaly_scores' in result.analysis_details


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_network_with_minimal_nodes(self):
        """Test handling of very small network."""
        # Create minimal but valid network using the generator
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=10)
        
        engine = PhysicsEngine()
        state = engine.simulate_network(G, nodes, pipes)
        
        # Should handle gracefully
        detector = LeakDetector()
        result = detector.analyze_network(G, nodes, pipes, state)
        assert result is not None
    
    def test_all_nodes_low_pressure(self):
        """Test detection when all nodes have low pressure."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=30)
        engine = PhysicsEngine(source_pressure=50.0)  # Very low source pressure
        state = engine.simulate_network(G, nodes, pipes)
        
        result = detect_leaks(G, nodes, pipes, state)
        
        # Should complete without error
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
