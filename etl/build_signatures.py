"""
Build the leak-signature matrix for physics-based sensor placement.

For each of ~200 risk-weighted leak scenarios (a leak at a consumer node),
run the physics engine and record how much every node's pressure deviates
from the no-leak baseline. A sensor at node j "detects" scenario i when
|Δp[i, j]| >= DETECT_THRESHOLD_KPA (a realistic pressure-sensor noise floor —
tiny deviations are not observable in the field).

Output: data/leak_signatures.npz
  matrix          (S x N) float32, |Δp| in kPa
  scenario_nodes  (S,) node ids where the leak was injected
  scenario_weights(S,) risk weight of each scenario (max adjacent pipe risk)
  candidate_nodes (N,) node ids eligible to host a sensor (non-source)
  meta            JSON: threshold, leak rate, network md5, timings

Run: python -m etl.build_signatures      (~1 min)
"""

import hashlib
import json
import time
from pathlib import Path

import numpy as np

import risk
from city_gen import CityNetworkGenerator
from physics import PhysicsEngine

ROOT = Path(__file__).parent.parent
NETWORK_PATH = ROOT / "data" / "network.json"
OUT_PATH = ROOT / "data" / "leak_signatures.npz"

N_SCENARIOS = 200
LEAK_RATE_M3H = 50.0  # matches the app's injected-leak magnitude
DETECT_THRESHOLD_KPA = 2.0
SEED = 42


class _StateShim:
    """Just enough AppState surface for risk.score_pipes()."""

    def __init__(self, nodes, pipes, graph, sim):
        self.nodes, self.pipes, self.graph = nodes, pipes, graph
        self._sim = sim

    def get_current_simulation_state(self):
        return self._sim


def network_md5() -> str:
    return hashlib.md5(NETWORK_PATH.read_bytes()).hexdigest()


def main() -> None:
    rng = np.random.default_rng(SEED)
    nodes, pipes, graph = CityNetworkGenerator.load_network(str(NETWORK_PATH))
    engine = PhysicsEngine()

    print("baseline simulation ...")
    baseline = engine.simulate_network(graph=graph, nodes=nodes, pipes=pipes, leaks={})
    baseline2 = engine.simulate_network(graph=graph, nodes=nodes, pipes=pipes, leaks={})
    assert baseline.node_pressures == baseline2.node_pressures, (
        "physics engine is not deterministic — signature matrix would be noise"
    )

    candidates = np.array([n.id for n in nodes if n.node_type != "source"])
    base_p = np.array([baseline.node_pressures[c] for c in candidates])

    # Risk-weighted scenario sample: nodes touching risky pipes matter most,
    # but keep spatial coverage by sampling without replacement over weights.
    print("scoring pipes for scenario weights ...")
    shim = _StateShim(nodes, pipes, graph, baseline)
    pipe_risk = {p["pipe_id"]: p["risk"] for p in risk.score_pipes(shim)["pipes"]}
    by_node: dict[int, float] = {}
    for p in pipes:
        for nid in (p.source_id, p.target_id):
            by_node[nid] = max(by_node.get(nid, 0.0), pipe_risk[p.id])
    weights = np.array([by_node.get(c, 0.0) + 0.05 for c in candidates])  # +0.05 floor keeps every node possible
    probs = weights / weights.sum()
    n_scen = min(N_SCENARIOS, len(candidates))
    scenario_nodes = rng.choice(candidates, size=n_scen, replace=False, p=probs)

    print(f"running {n_scen} leak scenarios ...")
    t0 = time.time()
    matrix = np.zeros((n_scen, len(candidates)), dtype=np.float32)
    for i, leak_node in enumerate(scenario_nodes):
        sim = engine.simulate_network(
            graph=graph, nodes=nodes, pipes=pipes, leaks={int(leak_node): LEAK_RATE_M3H}
        )
        leaked_p = np.array([sim.node_pressures[c] for c in candidates])
        matrix[i] = np.abs(base_p - leaked_p)
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{n_scen} ({time.time() - t0:.0f}s)")

    detectable = (matrix >= DETECT_THRESHOLD_KPA).any(axis=1)
    print(f"scenarios detectable anywhere at {DETECT_THRESHOLD_KPA} kPa floor: "
          f"{int(detectable.sum())}/{n_scen}")
    if detectable.sum() < n_scen * 0.5:
        print("⚠️ under half the scenarios are detectable — consider raising LEAK_RATE_M3H")

    scenario_weights = np.array(
        [by_node.get(int(n), 0.0) + 0.05 for n in scenario_nodes], dtype=np.float32
    )
    meta = {
        "threshold_kpa": DETECT_THRESHOLD_KPA,
        "leak_rate_m3h": LEAK_RATE_M3H,
        "network_md5": network_md5(),
        "n_scenarios": int(n_scen),
        "seed": SEED,
        "build_seconds": round(time.time() - t0, 1),
    }
    np.savez_compressed(
        OUT_PATH,
        matrix=matrix,
        scenario_nodes=scenario_nodes.astype(np.int64),
        scenario_weights=scenario_weights,
        candidate_nodes=candidates.astype(np.int64),
        meta=json.dumps(meta),
    )
    print(f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1e6:.1f} MB) meta={meta}")


if __name__ == "__main__":
    main()
