"""
Invariant tests for the street-true network artifact (data/network.json).

These test the BUILT ARTIFACT, so they run in CI without the raw GIS cache.
If the artifact is missing the module is skipped (run `python -m etl.fetch`
then `python -m etl.build_network` to produce it).
"""

import json
from pathlib import Path

import networkx as nx
import pytest

ARTIFACT = Path(__file__).parent.parent / "data" / "network.json"

pytestmark = pytest.mark.skipif(not ARTIFACT.exists(), reason="network artifact not built")


@pytest.fixture(scope="module")
def network():
    return json.load(open(ARTIFACT))


@pytest.fixture(scope="module")
def graph(network):
    G = nx.Graph()
    for n in network["nodes"]:
        G.add_node(n["id"], **n)
    for p in network["pipes"]:
        G.add_edge(p["source_id"], p["target_id"], **p)
    return G


def test_metadata_declares_street_true_generator(network):
    assert network["metadata"]["generator"].startswith("etl.build_network")
    assert "disclaimer" in network["metadata"]


def test_network_is_connected(graph):
    assert nx.is_connected(graph)


def test_has_expected_scale(network):
    assert 300 <= len(network["nodes"]) <= 3000
    assert len(network["pipes"]) >= len(network["nodes"]) - 1


def test_sources_exist_and_have_zero_demand(network):
    sources = [n for n in network["nodes"] if n["node_type"] == "source"]
    assert len(sources) == 3
    assert all(n["base_demand"] == 0.0 for n in sources)


def test_all_consumers_have_positive_demand(network):
    consumers = [n for n in network["nodes"] if n["node_type"] != "source"]
    assert all(n["base_demand"] > 0 for n in consumers)


def test_every_node_reachable_from_a_source(graph, network):
    source_ids = [n["id"] for n in network["nodes"] if n["node_type"] == "source"]
    reachable = set()
    for sid in source_ids:
        reachable |= nx.node_connected_component(graph, sid)
    assert reachable == set(graph.nodes)


def test_coordinates_are_in_bentonville(network):
    for n in network["nodes"]:
        assert -94.35 <= n["x"] <= -94.10, n
        assert 36.26 <= n["y"] <= 36.46, n


def test_pipe_attributes_sane(network):
    for p in network["pipes"]:
        # upper bound: longest uninterrupted arterial run after degree-2 merging
        assert 10 <= p["length"] <= 8000, p["id"]
        assert 0.05 <= p["diameter"] <= 0.55, p["id"]
        assert p["roughness"] > 0
        assert 1935 <= p["year_installed"] <= 2026
        assert p["road_class"] in ("arterial", "collector", "local")
        assert p["flood_zone"] in (None, "100yr", "500yr")
        # path geometry endpoints must be present and plausible
        assert len(p["path"]) >= 2


def test_hierarchy_diameters_are_ordered(network):
    by_class = {"arterial": [], "collector": [], "local": []}
    for p in network["pipes"]:
        by_class[p["road_class"]].append(p["diameter"])
    avg = {c: sum(v) / len(v) for c, v in by_class.items() if v}
    assert avg["arterial"] > avg["collector"] > avg["local"]


def test_vintage_growth_rings(network):
    """Pipes near the downtown square should skew older than the periphery."""
    import math

    def dist_km(p):
        mid = p["path"][len(p["path"]) // 2]
        dx = (mid[0] - -94.20882) * 111 * math.cos(math.radians(36.37))
        dy = (mid[1] - 36.37285) * 111
        return math.hypot(dx, dy)

    inner = [p["year_installed"] for p in network["pipes"] if dist_km(p) < 1.2]
    outer = [p["year_installed"] for p in network["pipes"] if dist_km(p) > 4.5]
    assert inner and outer
    # ACS-derived vintages show a gentler gradient than the pure heuristic,
    # but downtown must still skew meaningfully older than the periphery.
    assert sum(inner) / len(inner) < sum(outer) / len(outer) - 5
