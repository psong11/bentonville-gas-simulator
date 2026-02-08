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


class TestOptimalSensorEndpoint:
    """Tests for /api/sensors/optimal endpoint."""

    def test_optimal_sensors_returns_placements(self, client):
        """Optimal sensor endpoint should return sensor IDs and coverage."""
        client.get("/api/network")

        response = client.post("/api/sensors/optimal", json={"num_sensors": 3})
        assert response.status_code == 200
        data = response.json()

        assert "sensor_node_ids" in data
        assert "coverage_percentage" in data
        assert "algorithm" in data
        assert len(data["sensor_node_ids"]) <= 3
        assert 0 <= data["coverage_percentage"] <= 100
        assert data["algorithm"] == "greedy_dominating_set"

    def test_optimal_sensors_validates_count(self, client):
        """Optimal sensor request should validate num_sensors range."""
        client.get("/api/network")

        # Too many sensors
        response = client.post("/api/sensors/optimal", json={"num_sensors": 25})
        assert response.status_code == 422

    def test_optimal_sensors_coverage_increases(self, client):
        """More sensors should cover more or equal network."""
        client.get("/api/network")

        resp_few = client.post("/api/sensors/optimal", json={"num_sensors": 2})
        resp_many = client.post("/api/sensors/optimal", json={"num_sensors": 10})

        assert resp_few.status_code == 200
        assert resp_many.status_code == 200

        assert resp_many.json()["coverage_percentage"] >= resp_few.json()["coverage_percentage"]


class TestSimulationStateEndpoint:
    """Tests for /api/simulation/state endpoint."""

    def test_get_state_before_any_simulation(self, client):
        """Getting simulation state should work even before any explicit simulation."""
        # Fetching the network auto-generates one if needed, which runs an initial sim
        client.get("/api/network")

        response = client.get("/api/simulation/state")
        assert response.status_code == 200
        data = response.json()

        assert "node_pressures" in data
        assert "pipe_flow_rates" in data
        assert "active_leaks" in data

    def test_state_reflects_last_simulation(self, client):
        """State endpoint should return results matching the last simulation."""
        client.get("/api/network")

        # Run simulation with specific pressure
        client.post("/api/simulate", json={"source_pressure": 500})

        state = client.get("/api/simulation/state").json()
        assert len(state["node_pressures"]) > 0


class TestLeakLifecycle:
    """Tests for the complete leak inject -> verify -> detect -> clear lifecycle."""

    def test_inject_leaks_by_node_ids(self, client):
        """Inject leaks using explicit node IDs."""
        network = client.get("/api/network").json()
        # Pick two non-source node IDs
        non_source_ids = [
            n["id"] for n in network["nodes"] if n["node_type"] != "source"
        ][:2]

        response = client.post(
            "/api/leaks/inject",
            json={"node_ids": non_source_ids},
        )
        assert response.status_code == 200
        data = response.json()

        assert set(data["injected_node_ids"]) == set(non_source_ids)

    def test_injected_leaks_appear_in_simulation_state(self, client):
        """After injecting leaks, simulation state should reflect active_leaks."""
        network = client.get("/api/network").json()
        non_source_ids = [
            n["id"] for n in network["nodes"] if n["node_type"] != "source"
        ][:2]

        # Inject leaks (this runs simulation internally)
        client.post("/api/leaks/inject", json={"node_ids": non_source_ids})

        # Get state WITHOUT re-running simulate (which would reset active_leaks
        # via its default active_leaks=[] parameter)
        state = client.get("/api/simulation/state").json()
        active_leak_ids = [int(k) for k in state["active_leaks"].keys()]

        for nid in non_source_ids:
            assert nid in active_leak_ids, f"Node {nid} should be an active leak"

    def test_clear_leaks_removes_all_active_leaks(self, client):
        """After clearing, active_leaks should be empty."""
        network = client.get("/api/network").json()
        non_source_ids = [
            n["id"] for n in network["nodes"] if n["node_type"] != "source"
        ][:3]

        # Inject then clear
        client.post("/api/leaks/inject", json={"node_ids": non_source_ids})
        clear_resp = client.post("/api/leaks/clear")
        assert clear_resp.status_code == 200

        # Re-run simulation and check state
        client.post("/api/simulate", json={"source_pressure": 400})
        state = client.get("/api/simulation/state").json()

        assert len(state["active_leaks"]) == 0

    def test_inject_replace_existing_leaks(self, client):
        """A new inject call should replace previous leaks, not add to them."""
        network = client.get("/api/network").json()
        non_source = [
            n["id"] for n in network["nodes"] if n["node_type"] != "source"
        ]

        first_ids = non_source[:2]
        second_ids = non_source[5:7]

        client.post("/api/leaks/inject", json={"node_ids": first_ids})
        client.post("/api/leaks/inject", json={"node_ids": second_ids})

        # Get state directly (inject runs simulation internally)
        state = client.get("/api/simulation/state").json()
        active_ids = set(int(k) for k in state["active_leaks"].keys())

        # Only second set should be active
        for nid in second_ids:
            assert nid in active_ids
        for nid in first_ids:
            assert nid not in active_ids

    def test_detect_leaks_with_explicit_sensor_ids(self, client):
        """Detect leaks using explicit sensor_node_ids."""
        network = client.get("/api/network").json()
        non_source = [
            n["id"] for n in network["nodes"] if n["node_type"] != "source"
        ]

        # Inject a leak
        leak_id = non_source[10]
        client.post("/api/leaks/inject", json={"node_ids": [leak_id]})
        client.post("/api/simulate", json={"source_pressure": 400})

        # Detect using explicit sensor nodes (neighbors of the leak)
        sensor_ids = non_source[:5]
        response = client.post(
            "/api/leaks/detect",
            json={
                "strategy": "combined",
                "sensor_node_ids": sensor_ids,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "suspected_leaks" in data
        assert "sensor_placements" in data
        assert "detection_rate" in data
        assert set(data["sensor_placements"]) == set(sensor_ids)

    def test_optimal_sensors_into_detection(self, client):
        """Use optimal sensor placements to run leak detection."""
        network = client.get("/api/network").json()
        non_source = [
            n["id"] for n in network["nodes"] if n["node_type"] != "source"
        ]

        # Inject a leak
        leak_id = non_source[15]
        client.post("/api/leaks/inject", json={"node_ids": [leak_id]})
        client.post("/api/simulate", json={"source_pressure": 400})

        # Get optimal sensor placements
        opt_resp = client.post("/api/sensors/optimal", json={"num_sensors": 5})
        assert opt_resp.status_code == 200
        sensor_ids = opt_resp.json()["sensor_node_ids"]

        # Use those sensors for detection
        detect_resp = client.post(
            "/api/leaks/detect",
            json={
                "strategy": "combined",
                "sensor_node_ids": sensor_ids,
            },
        )
        assert detect_resp.status_code == 200
        data = detect_resp.json()

        assert "detection_rate" in data
        assert "false_positive_rate" in data


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

    def test_websocket_set_demand_multiplier(self, client):
        """WebSocket should handle SET_DEMAND_MULTIPLIER message."""
        client.get("/api/network")

        with client.websocket_connect("/ws") as websocket:
            # Receive initial state
            websocket.receive_json()

            # Send demand multiplier update
            websocket.send_json({
                "type": "SET_DEMAND_MULTIPLIER",
                "payload": {"value": 1.5}
            })

            # Should receive simulation update
            data = websocket.receive_json()
            assert data["type"] == "SIMULATION_UPDATE"

    def test_websocket_inject_leak(self, client):
        """WebSocket should handle INJECT_LEAK message."""
        client.get("/api/network")

        with client.websocket_connect("/ws") as websocket:
            # Receive initial state
            websocket.receive_json()

            # Send inject leak
            websocket.send_json({
                "type": "INJECT_LEAK",
                "payload": {"count": 1}
            })

            # Should receive LEAK_ALERT then SIMULATION_UPDATE
            msg1 = websocket.receive_json()
            msg2 = websocket.receive_json()
            types = {msg1["type"], msg2["type"]}
            assert "LEAK_ALERT" in types
            assert "SIMULATION_UPDATE" in types

    def test_websocket_clear_leaks(self, client):
        """WebSocket should handle CLEAR_LEAKS message."""
        client.get("/api/network")

        with client.websocket_connect("/ws") as websocket:
            # Receive initial state
            websocket.receive_json()

            # First inject a leak
            websocket.send_json({
                "type": "INJECT_LEAK",
                "payload": {"count": 1}
            })
            # Consume the LEAK_ALERT and SIMULATION_UPDATE
            websocket.receive_json()
            websocket.receive_json()

            # Now clear leaks
            websocket.send_json({
                "type": "CLEAR_LEAKS",
                "payload": {}
            })

            # Should receive simulation update with no leaks
            data = websocket.receive_json()
            assert data["type"] == "SIMULATION_UPDATE"
            assert len(data["payload"]["active_leaks"]) == 0

    def test_websocket_unknown_type_returns_error(self, client):
        """WebSocket should return ERROR for unknown message types."""
        client.get("/api/network")

        with client.websocket_connect("/ws") as websocket:
            # Receive initial state
            websocket.receive_json()

            websocket.send_json({
                "type": "NONEXISTENT_TYPE",
                "payload": {}
            })

            data = websocket.receive_json()
            assert data["type"] == "ERROR"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
