"""
Physics-based sensor placement over the leak-signature matrix.

Objective: choose K sensor locations maximizing the risk-weighted fraction of
leak scenarios detected, where a sensor at node j detects scenario i when
|Δp[i, j]| >= threshold (see etl/build_signatures.py).

Weighted max-coverage is monotone submodular, so greedy selection is
(1 - 1/e)-optimal (Nemhauser/Wolsey/Fisher; popularized for sensor placement
by Krause et al.). The greedy runs in milliseconds over the cached matrix, so
the API can re-plan live as the budget slider moves.
"""

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
SIGNATURES_PATH = ROOT / "data" / "leak_signatures.npz"
NETWORK_PATH = ROOT / "data" / "network.json"

_cache: dict | None = None


class SignaturesUnavailable(RuntimeError):
    pass


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if not SIGNATURES_PATH.exists():
        raise SignaturesUnavailable(
            "leak_signatures.npz missing — run `python -m etl.build_signatures`"
        )
    data = np.load(SIGNATURES_PATH, allow_pickle=False)
    meta = json.loads(str(data["meta"]))
    current_md5 = hashlib.md5(NETWORK_PATH.read_bytes()).hexdigest()
    if meta["network_md5"] != current_md5:
        raise SignaturesUnavailable(
            "leak_signatures.npz was built for a different network artifact — "
            "re-run `python -m etl.build_signatures`"
        )
    detect = data["matrix"] >= meta["threshold_kpa"]  # (S x N) bool
    weights = data["scenario_weights"].astype(np.float64)
    _cache = {
        "detect": detect,
        "weights": weights,
        "total_weight": float(weights.sum()),
        "scenario_nodes": data["scenario_nodes"],
        "candidate_nodes": data["candidate_nodes"],
        "meta": meta,
    }
    return _cache


def reset_cache() -> None:
    global _cache
    _cache = None


def plan(budget: int, seed: int = 7) -> dict:
    """Greedy submodular sensor plan plus a random-placement baseline."""
    sig = _load()
    detect, weights = sig["detect"], sig["weights"]
    n_candidates = detect.shape[1]
    budget = max(1, min(int(budget), 25, n_candidates))

    covered = np.zeros(detect.shape[0], dtype=bool)
    chosen: list[int] = []
    steps = []
    for _ in range(budget):
        gains = weights @ (detect & ~covered[:, None])  # marginal weight per candidate
        best = int(gains.argmax())
        gain = float(gains[best])
        if gain <= 0:
            break  # nothing left to cover — stop early rather than pad
        chosen.append(best)
        covered |= detect[:, best]
        steps.append({
            "k": len(chosen),
            "node_id": int(sig["candidate_nodes"][best]),
            "marginal_weight": round(gain, 4),
            "coverage_pct": round(100 * float(weights[covered].sum()) / sig["total_weight"], 1),
        })

    # honest baseline: mean coverage of random placements at the same budget
    rng = np.random.default_rng(seed)
    baseline = []
    for _ in range(30):
        idx = rng.choice(n_candidates, size=min(budget, n_candidates), replace=False)
        cov = detect[:, idx].any(axis=1)
        baseline.append(float(weights[cov].sum()) / sig["total_weight"])
    detectable_any = detect.any(axis=1)
    ceiling_pct = round(100 * float(weights[detectable_any].sum()) / sig["total_weight"], 1)

    return {
        "method": (
            "greedy weighted max-coverage over a physics-derived leak-signature matrix "
            f"({sig['meta']['n_scenarios']} risk-weighted leak scenarios, detection floor "
            f"{sig['meta']['threshold_kpa']} kPa). Monotone submodular objective -> greedy "
            "is (1-1/e)-optimal."
        ),
        "sensor_node_ids": [s["node_id"] for s in steps],
        "coverage_pct": steps[-1]["coverage_pct"] if steps else 0.0,
        "curve": steps,
        "baseline_random_pct": round(100 * sum(baseline) / len(baseline), 1),
        "ceiling_pct": ceiling_pct,
        "scenario_count": int(detect.shape[0]),
        "threshold_kpa": sig["meta"]["threshold_kpa"],
    }
