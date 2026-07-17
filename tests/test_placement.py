"""
Sensor-placement tests: submodularity signature, greedy quality, determinism,
artifact-hash guard, and the API contract. Skipped when the signature artifact
hasn't been built.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import placement
from api.main import app

pytestmark = pytest.mark.skipif(
    not Path(placement.SIGNATURES_PATH).exists(),
    reason="leak_signatures.npz not built (python -m etl.build_signatures)",
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_marginal_gains_non_increasing():
    gains = [s["marginal_weight"] for s in placement.plan(15)["curve"]]
    assert all(gains[i] >= gains[i + 1] - 1e-9 for i in range(len(gains) - 1)), (
        "non-increasing marginal gains are the signature of a correctly "
        "implemented submodular greedy — this failing means the math is wrong"
    )


def test_coverage_monotone_in_budget():
    covs = [placement.plan(k)["coverage_pct"] for k in (2, 5, 10, 20)]
    assert covs == sorted(covs)


def test_greedy_beats_random_baseline():
    r = placement.plan(10)
    assert r["coverage_pct"] > r["baseline_random_pct"] * 1.3


def test_deterministic():
    assert placement.plan(8)["sensor_node_ids"] == placement.plan(8)["sensor_node_ids"]


def test_budget_clamped():
    assert len(placement.plan(9999)["sensor_node_ids"]) <= 25
    assert len(placement.plan(-3)["sensor_node_ids"]) == 1


def test_coverage_never_exceeds_ceiling():
    r = placement.plan(25)
    assert r["coverage_pct"] <= r["ceiling_pct"] + 1e-6


def test_hash_guard_rejects_stale_artifact(monkeypatch, tmp_path):
    fake_network = tmp_path / "network.json"
    fake_network.write_text("{}")
    monkeypatch.setattr(placement, "NETWORK_PATH", fake_network)
    placement.reset_cache()
    with pytest.raises(placement.SignaturesUnavailable):
        placement.plan(5)
    monkeypatch.undo()
    placement.reset_cache()


def test_api_contract(client):
    resp = client.post("/api/sensors/plan", json={"num_sensors": 8})
    assert resp.status_code == 200
    d = resp.json()
    assert len(d["sensors"]) == 8
    assert d["sensors"][0]["street"]
    assert len(d["curve"]) == 8
    assert d["coverage_pct"] > d["baseline_random_pct"]
    assert "submodular" in d["method"]
