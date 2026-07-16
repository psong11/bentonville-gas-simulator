"""
Tests for the ChatOps agent: tool executors over real state, tool registry
consistency, and the API-key guard. The Claude call itself is not tested here
(covered by manual end-to-end verification) — these tests run offline.
"""

import pytest
from fastapi.testclient import TestClient

import api.agent as agent
from api.main import app, app_state


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_every_declared_tool_has_an_executor():
    declared = {t["name"] for t in agent.TOOLS}
    assert declared == set(agent.TOOL_EXECUTORS.keys())


def test_tool_schemas_are_closed_objects():
    for t in agent.TOOLS:
        assert t["input_schema"]["type"] == "object"
        assert t["input_schema"].get("additionalProperties") is False, t["name"]


def test_network_status_shape(client):
    s = agent.tool_get_network_status(app_state, {})
    assert s["nodes"] > 0 and s["pipes"] > 0
    assert s["pressure_kpa"]["min"] <= s["pressure_kpa"]["mean"] <= s["pressure_kpa"]["max"]


def test_inspection_candidates_ranked_and_highlightable(client):
    r = agent.tool_list_inspection_candidates(app_state, {"top_k": 5})
    scores = [c["score"] for c in r["candidates"]]
    assert scores == sorted(scores, reverse=True)
    assert len(r["highlight"]["pipe_ids"]) == len(r["candidates"])
    assert all(c["street"] for c in r["candidates"])


def test_flood_exposed_old_pipe_outranks_new_dry_pipe(client):
    r = agent.tool_list_inspection_candidates(app_state, {"top_k": 15})
    top = r["candidates"][0]
    # the top candidate should be meaningfully old or flood-exposed
    assert top["factors"]["flood_zone"] is not None or top["factors"]["age"]["year_installed"] < 1990


def test_run_scenario_clamps_inputs(client):
    r = agent.tool_run_scenario(app_state, {"source_pressure": 9999, "demand_multiplier": 0.01})
    assert r["applied"]["source_pressure"] == 800.0
    assert r["applied"]["demand_multiplier"] == 0.5
    # restore defaults for other tests
    agent.tool_run_scenario(app_state, {"source_pressure": 400, "demand_multiplier": 1.0})


def test_inject_and_clear_leaks_roundtrip(client):
    r = agent.tool_inject_leaks(app_state, {"count": 2})
    assert len(r["injected"]) == 2
    assert app_state.current_active_leaks
    agent.tool_clear_leaks(app_state, {})
    assert not app_state.current_active_leaks


def test_sensor_placement_highlight(client):
    r = agent.tool_place_sensors(app_state, {"budget": 4})
    assert len(r["sensors"]) == 4
    assert r["coverage_percentage"] > 0
    assert r["highlight"]["node_ids"]


def test_agent_endpoint_guards_missing_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.post("/api/agent", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 503


def test_agent_endpoint_validates_roles(client):
    resp = client.post("/api/agent", json={"messages": [{"role": "system", "content": "x"}]})
    assert resp.status_code == 422
