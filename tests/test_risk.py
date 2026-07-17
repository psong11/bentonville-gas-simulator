"""
Risk-engine tests: physical-ordering properties, normalization sanity,
caching, and the API contract.
"""

import copy

import pytest
from fastapi.testclient import TestClient

import risk
from api.main import app, app_state


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def result(client):
    return risk.score_pipes(app_state)


def test_scores_cover_all_pipes_and_are_normalized(result):
    assert len(result["scores"]) == len(app_state.pipes)
    vals = [p["risk"] for p in result["pipes"]]
    assert min(vals) >= 0.0 and max(vals) <= 1.0
    # percentile normalization must produce a real spread, not a point mass
    assert max(vals) - min(vals) > 0.9


def test_output_sorted_by_risk(result):
    vals = [p["risk"] for p in result["pipes"]]
    assert vals == sorted(vals, reverse=True)


def test_static_cache_reused(result):
    cache_before = getattr(app_state, risk._CACHE_ATTR)
    risk.score_pipes(app_state)
    assert getattr(app_state, risk._CACHE_ATTR) is cache_before


def test_bridge_isolation_demand_is_plausible(result):
    iso = [p for p in result["pipes"] if p["factors"]["isolates_demand_m3h"] > 0]
    assert iso, "street networks always contain bridges"
    total_demand = sum(n.base_demand for n in app_state.nodes)
    for p in iso[:50]:
        assert p["factors"]["isolates_demand_m3h"] < total_demand


def test_flood_and_age_raise_p_fail(result):
    """Among pipes of the same material/class, flood-zone + older should rank
    higher on p_fail on average than dry + newer."""
    steel = [p for p in result["pipes"] if p["factors"]["material"] == "steel"]
    flooded_old = [p["p_fail"] for p in steel
                   if p["factors"]["flood_zone"] and p["factors"]["year_installed"] < 2000]
    dry_new = [p["p_fail"] for p in steel
               if not p["factors"]["flood_zone"] and p["factors"]["year_installed"] >= 2010]
    assert flooded_old and dry_new
    assert sum(flooded_old) / len(flooded_old) > sum(dry_new) / len(dry_new)


def test_facility_proximity_raises_consequence(result):
    """A pipe near a critical facility should out-rank an otherwise similar
    pipe on consequence, all else equal on average."""
    near = [p["consequence"] for p in result["pipes"] if p["factors"]["near_critical_facility"]]
    far = [p["consequence"] for p in result["pipes"] if not p["factors"]["near_critical_facility"]]
    assert near and far
    assert sum(near) / len(near) > sum(far) / len(far)


def test_deterministic(result):
    again = risk.score_pipes(app_state)
    assert [p["pipe_id"] for p in again["pipes"][:20]] == [p["pipe_id"] for p in result["pipes"][:20]]


def test_percentiles_degenerate_distribution():
    flat = risk._percentiles({i: 5.0 for i in range(10)})
    assert all(v == 0.0 for v in flat.values())  # no blow-ups on zero spread


def test_api_contract(client):
    resp = client.get("/api/risk/weakpoints?top_k=7")
    assert resp.status_code == 200
    d = resp.json()
    assert len(d["top"]) == 7
    assert d["top"][0]["street"]
    assert "factors" in d["top"][0]
    assert len(d["scores"]) == len(app_state.pipes)


def test_top_k_clamped(client):
    assert len(client.get("/api/risk/weakpoints?top_k=9999").json()["top"]) == 50
    assert len(client.get("/api/risk/weakpoints?top_k=0").json()["top"]) == 1
