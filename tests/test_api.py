"""
Tests for FastAPI Backend
=========================
Tests all API endpoints to ensure correct behavior.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_returns_ok(self, client):
        """Health check should return status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestNetworkEndpoints:
    """Tests for /api/network endpoints."""
    
    def test_get_network_returns_nodes_and_pipes(self, client):
        """Get network should return nodes and pipes."""
        response = client.get("/api/network")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "pipes" in data
        assert len(data["nodes"]) > 0
        assert len(data["pipes"]) > 0
    
    def test_node_has_required_fields(self, client):
        """Each node should have required fields."""
        response = client.get("/api/network")
        data = response.json()
        node = data["nodes"][0]
        
        required_fields = ["id", "node_type", "x", "y", "base_demand", "elevation", "name"]
        for field in required_fields:
            assert field in node, f"Node missing field: {field}"
    
    def test_pipe_has_required_fields(self, client):
        """Each pipe should have required fields."""
        response = client.get("/api/network")
        data = response.json()
        pipe = data["pipes"][0]
        
        required_fields = ["id", "source_id", "target_id", "length", "diameter", "roughness", "material"]
        for field in required_fields:
            assert field in pipe, f"Pipe missing field: {field}"
    
    def test_generate_network_with_custom_count(self, client):
        """Generate network should create specified number of nodes."""
        response = client.post("/api/network/generate", json={"node_count": 30})
        assert response.status_code == 200
        data = response.json()
        # Note: actual count may differ slightly due to source nodes
        assert len(data["nodes"]) >= 30
    
    def test_generate_network_validates_count(self, client):
        """Generate network should validate node count range."""
        # Too few nodes
        response = client.post("/api/network/generate", json={"node_count": 5})
        assert response.status_code == 422  # Validation error
        
        # Too many nodes
        response = client.post("/api/network/generate", json={"node_count": 500})
        assert response.status_code == 422


class TestSimulationEndpoints:
    """Tests for /api/simulate endpoints."""
    
    def test_simulate_returns_pressures_and_flows(self, client):
        """Simulation should return node pressures and pipe flows."""
        # First ensure we have a network
        client.get("/api/network")
        
        response = client.post("/api/simulate", json={"source_pressure": 400})
        assert response.status_code == 200
        data = response.json()
        
        assert "node_pressures" in data
        assert "pipe_flow_rates" in data
        assert "node_actual_demand" in data
        assert len(data["node_pressures"]) > 0
    
    def test_simulate_respects_source_pressure(self, client):
        """Simulation should use provided source pressure."""
        client.get("/api/network")
        
        # Low pressure
        response_low = client.post("/api/simulate", json={"source_pressure": 200})
        data_low = response_low.json()
        
        # High pressure
        response_high = client.post("/api/simulate", json={"source_pressure": 600})
        data_high = response_high.json()
        
        # Pick a non-source node to compare
        # Pressures should be different
        low_pressures = list(data_low["node_pressures"].values())
        high_pressures = list(data_high["node_pressures"].values())
        
        assert max(high_pressures) > max(low_pressures)
    
    def test_simulate_with_demand_multiplier(self, client):
        """Simulation should apply demand multiplier."""
        client.get("/api/network")
        
        response = client.post("/api/simulate", json={
            "source_pressure": 400,
            "demand_multiplier": 1.5
        })
        assert response.status_code == 200
    
    def test_get_simulation_state(self, client):
        """Get simulation state should return current state."""
        # First run a simulation
        client.get("/api/network")
        client.post("/api/simulate", json={"source_pressure": 400})
        
        response = client.get("/api/simulation/state")
        assert response.status_code == 200
        data = response.json()
        assert "node_pressures" in data


class TestLeakEndpoints:
    """Tests for /api/leaks endpoints."""
    
    def test_inject_leaks(self, client):
        """Inject leaks should return injected node IDs."""
        client.get("/api/network")
        
        response = client.post("/api/leaks/inject", json={"count": 2})
        assert response.status_code == 200
        data = response.json()
        
        assert "injected_node_ids" in data
        assert len(data["injected_node_ids"]) == 2
    
    def test_detect_leaks(self, client):
        """Detect leaks should return detection results."""
        client.get("/api/network")
        client.post("/api/simulate", json={"source_pressure": 400})
        
        response = client.post("/api/leaks/detect", json={"strategy": "combined"})
        assert response.status_code == 200
        data = response.json()
        
        assert "suspected_leaks" in data
        assert "strategy_used" in data
        assert "detection_time_ms" in data
        assert data["strategy_used"] == "combined"
    
    def test_clear_leaks(self, client):
        """Clear leaks should remove all active leaks."""
        client.get("/api/network")
        client.post("/api/leaks/inject", json={"count": 3})
        
        response = client.post("/api/leaks/clear")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestWebSocket:
    """Tests for WebSocket endpoint."""
    
    def test_websocket_connects(self, client):
        """WebSocket should accept connections."""
        with client.websocket_connect("/ws") as websocket:
            # Should receive initial state
            data = websocket.receive_json()
            assert data["type"] == "SIMULATION_UPDATE"
    
    def test_websocket_set_pressure(self, client):
        """WebSocket should handle SET_PRESSURE message."""
        # First ensure network exists
        client.get("/api/network")
        
        with client.websocket_connect("/ws") as websocket:
            # Receive initial state
            websocket.receive_json()
            
            # Send pressure update
            websocket.send_json({
                "type": "SET_PRESSURE",
                "payload": {"value": 500}
            })
            
            # Should receive simulation update
            data = websocket.receive_json()
            assert data["type"] == "SIMULATION_UPDATE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
