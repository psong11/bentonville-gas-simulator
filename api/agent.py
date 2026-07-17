"""
ChatOps Agent
=============
Claude tool-use agent over the simulator: POST /api/agent streams SSE frames
(text deltas + tool events) while Claude calls the same services the UI uses.

Tool results carry node/pipe ids so the frontend can highlight what the
agent cites on the map.
"""

import json
import os
from pathlib import Path
from typing import Any, AsyncGenerator

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).parent.parent / ".env")

router = APIRouter()

AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-opus-4-8")
MAX_TOKENS = 16000
MAX_TOOL_TURNS = 8

SYSTEM_PROMPT = """\
You are the operations assistant for the Bentonville Gas Distribution digital twin —
a simulator of a synthetic-but-street-true gas network for Bentonville, Arkansas.

Context you must keep in mind:
- The network is SYNTHETIC: pipes are routed along real Bentonville street centerlines
  with demand from real city land use and address density, pipe vintage informed by
  Census housing age, and real FEMA flood-zone exposure — but it is NOT the utility's
  actual system (real gas maps are non-public for security). Say so if asked about
  real-world operations, and remind users to call 811 before any digging.
- Data sources: City of Bentonville GIS (streets, land use, FEMA flood, addresses),
  ARDOT traffic counts, US Census ACS.
- Pressure is in kPa. The service threshold is 300 kPa; below ~250 is concerning,
  below 210 is critical. Source pressure comes from three approximate city gates.

How to answer:
- Use your tools — never guess numbers. Chain tools when needed (e.g. status first,
  then inspection candidates).
- Cite street names, not node ids. Be concise and operational: lead with the answer,
  then the two or three facts that support it.
- When a tool returns highlighted locations, tell the user they are highlighted on
  the map.
- This is a planning/training tool. For anything smelling of a real emergency, say:
  evacuate, avoid ignition sources, and call 911 and Black Hills Energy.
"""

TOOLS: list[dict] = [
    {
        "name": "get_network_status",
        "description": (
            "Current state of the gas network: node/pipe counts, source pressure, "
            "demand multiplier, pressure distribution (min/mean/max, count below "
            "service threshold), active leaks, and current warnings. Call this first "
            "for any 'how does the system look' question."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_inspection_candidates",
        "description": (
            "Rank pipes by engineering risk = P(fail) x consequence. P(fail) uses "
            "material/age priors, FEMA flood exposure, excavation intensity (traffic), "
            "and pressure utilization. Consequence uses demand isolated if the pipe "
            "fails (graph bridges), flow carried, structural betweenness, and "
            "proximity to critical facilities (approximate landmarks). Returns street "
            "names, factor breakdowns, and pipe ids for map highlighting. Call this "
            "for weak points, inspections, or maintenance priorities."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "top_k": {"type": "integer", "description": "How many pipes to return (default 5, max 15)"}
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "run_scenario",
        "description": (
            "Re-run the physics simulation with new parameters. Use to answer "
            "'what if' questions (e.g. peak demand, reduced gate pressure). Returns "
            "the resulting pressure distribution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_pressure": {"type": "number", "description": "Gate pressure in kPa (200-800)"},
                "demand_multiplier": {"type": "number", "description": "Demand scaling 0.5-2.0 (1.0 = normal)"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "inject_leaks",
        "description": "Inject N random test leaks into the network (training scenario). Re-runs the simulation.",
        "input_schema": {
            "type": "object",
            "properties": {"count": {"type": "integer", "description": "Number of leaks (1-10)"}},
            "required": ["count"],
            "additionalProperties": False,
        },
    },
    {
        "name": "clear_leaks",
        "description": "Clear all active test leaks and restore normal operation.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "place_sensors",
        "description": (
            "Optimal sensor placement for a budget via greedy submodular max-coverage "
            "over a physics-derived leak-signature matrix (200 risk-weighted leak "
            "simulations; (1-1/e)-optimal). Returns locations (street names), % of "
            "leak scenarios detected, the marginal-gain curve (how much each extra "
            "sensor buys), a random-placement baseline, and node ids for highlighting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"budget": {"type": "integer", "description": "Number of sensors (1-25)"}},
            "required": ["budget"],
            "additionalProperties": False,
        },
    },
    {
        "name": "detect_leaks",
        "description": (
            "Run leak detection using sensors at the optimal locations for the given "
            "budget. Returns suspected leak locations with confidence, plus detection "
            "rate if test leaks are active."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"num_sensors": {"type": "integer", "description": "Sensor budget to use (default 5)"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_hazard_context",
        "description": (
            "Static natural-hazard context for the network: FEMA flood-zone exposure "
            "(how many pipes/km in 100yr and 500yr zones, worst streets), pipe-age "
            "profile, and regional hazard notes (tornado/hail/ice, karst geology). "
            "Use for questions about natural disasters or environmental risk."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


# ------------------------------------------------------------- tool executors --

def _street(obj) -> str:
    return getattr(obj, "street", None) or getattr(obj, "name", "unnamed")


def tool_get_network_status(state, _args: dict) -> dict:
    sim = state.get_current_simulation_state()
    pressures = list(sim.node_pressures.values())
    below = [p for p in pressures if p < 300]
    return {
        "nodes": len(state.nodes),
        "pipes": len(state.pipes),
        "source_pressure_kpa": state.current_source_pressure,
        "demand_multiplier": state.current_demand_multiplier,
        "pressure_kpa": {
            "min": round(min(pressures), 1),
            "mean": round(sum(pressures) / len(pressures), 1),
            "max": round(max(pressures), 1),
        },
        "nodes_below_300kpa": len(below),
        "nodes_below_210kpa_critical": len([p for p in pressures if p < 210]),
        "active_leaks": len(state.current_active_leaks),
        "warnings": sim.warnings[:5],
    }


def tool_list_inspection_candidates(state, args: dict) -> dict:
    import risk

    top_k = min(int(args.get("top_k", 5) or 5), 15)
    result = risk.score_pipes(state)
    top = result["pipes"][:top_k]
    return {
        "method": result["method"],
        "candidates": top,
        "highlight": {"pipe_ids": [c["pipe_id"] for c in top]},
    }


def tool_run_scenario(state, args: dict) -> dict:
    sp = args.get("source_pressure")
    dm = args.get("demand_multiplier")
    if sp is not None:
        sp = max(200.0, min(800.0, float(sp)))
    if dm is not None:
        dm = max(0.5, min(2.0, float(dm)))
    sim = state.run_simulation(source_pressure=sp, demand_multiplier=dm)
    pressures = list(sim.node_pressures.values())
    return {
        "applied": {"source_pressure": state.current_source_pressure,
                    "demand_multiplier": state.current_demand_multiplier},
        "pressure_kpa": {
            "min": round(min(pressures), 1),
            "mean": round(sum(pressures) / len(pressures), 1),
            "max": round(max(pressures), 1),
        },
        "nodes_below_300kpa": len([p for p in pressures if p < 300]),
        "warnings": sim.warnings[:5],
    }


def tool_inject_leaks(state, args: dict) -> dict:
    count = max(1, min(10, int(args.get("count", 3))))
    result = state.inject_leaks(count)
    leaks = [n for n in state.nodes if n.id in result.injected_node_ids]
    return {
        "injected": [{"node_id": n.id, "street": _street(n)} for n in leaks],
        "highlight": {"node_ids": result.injected_node_ids},
    }


def tool_clear_leaks(state, _args: dict) -> dict:
    state.clear_leaks()
    state.run_simulation()
    return {"status": "all leaks cleared, simulation restored"}


def tool_place_sensors(state, args: dict) -> dict:
    import placement

    budget = max(1, min(25, int(args.get("budget", 5))))
    by_id = {n.id: n for n in state.nodes}
    try:
        result = placement.plan(budget)
        return {
            "method": result["method"],
            "scenario_coverage_pct": result["coverage_pct"],
            "random_baseline_pct": result["baseline_random_pct"],
            "marginal_gain_curve": [
                {"k": s["k"], "coverage_pct": s["coverage_pct"]} for s in result["curve"]
            ],
            "sensors": [
                {"node_id": nid, "street": _street(by_id[nid])}
                for nid in result["sensor_node_ids"] if nid in by_id
            ],
            "highlight": {"node_ids": result["sensor_node_ids"]},
        }
    except placement.SignaturesUnavailable:
        fallback = state.get_optimal_sensor_placements(budget)
        return {
            "method": f"fallback: {fallback.algorithm} (signature matrix not built)",
            "coverage_percentage": fallback.coverage_percentage,
            "sensors": [
                {"node_id": nid, "street": _street(by_id[nid])}
                for nid in fallback.sensor_node_ids if nid in by_id
            ],
            "highlight": {"node_ids": fallback.sensor_node_ids},
        }


def tool_detect_leaks(state, args: dict) -> dict:
    num = max(1, min(25, int(args.get("num_sensors", 5))))
    placement = state.get_optimal_sensor_placements(num)
    result = state.detect_leaks("combined", sensor_node_ids=placement.sensor_node_ids)
    by_id = {n.id: n for n in state.nodes}
    return {
        "sensors_used": len(result.sensor_placements),
        "suspected_leaks": [
            {"street": _street(by_id[s.node_id]), "node_id": s.node_id,
             "confidence": round(s.confidence, 2), "reason": s.reason}
            for s in result.suspected_leaks[:10] if s.node_id in by_id
        ],
        "detection_rate": result.detection_rate,
        "actual_active_leaks": len(state.current_active_leaks),
        "highlight": {"node_ids": [s.node_id for s in result.suspected_leaks[:10]]},
    }


def tool_get_hazard_context(state, _args: dict) -> dict:
    pipes = state.pipes
    in_100 = [p for p in pipes if p.flood_zone == "100yr"]
    in_500 = [p for p in pipes if p.flood_zone == "500yr"]
    old = [p for p in pipes if p.year_installed < 1975]
    worst_flood_streets = sorted(
        {(_street(p)) for p in in_100},
    )[:8]
    return {
        "flood_exposure": {
            "pipes_in_100yr_zone": len(in_100),
            "km_in_100yr_zone": round(sum(p.length for p in in_100) / 1000, 1),
            "pipes_in_500yr_zone": len(in_500),
            "example_streets_in_100yr": worst_flood_streets,
            "source": "FEMA flood layers via City of Bentonville GIS (current, March 2022)",
        },
        "age_profile": {
            "pipes_pre_1975": len(old),
            "oldest_year": min(p.year_installed for p in pipes),
            "note": "vintage derived from Census ACS median year built per block group",
        },
        "regional_hazards": {
            "severe_weather": "NW Arkansas: tornado, hail, and ice-storm exposure (FEMA National Risk Index).",
            "geology": "Springfield Plateau karst — localized sinkhole/subsidence risk for buried utilities.",
            "seismic": "Low regional seismicity; far from the New Madrid zone.",
        },
        "highlight": {"pipe_ids": [p.id for p in in_100][:40]},
    }


TOOL_EXECUTORS = {
    "get_network_status": tool_get_network_status,
    "list_inspection_candidates": tool_list_inspection_candidates,
    "run_scenario": tool_run_scenario,
    "inject_leaks": tool_inject_leaks,
    "clear_leaks": tool_clear_leaks,
    "place_sensors": tool_place_sensors,
    "detect_leaks": tool_detect_leaks,
    "get_hazard_context": tool_get_hazard_context,
}


# ------------------------------------------------------------------- endpoint --

class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class AgentRequest(BaseModel):
    messages: list[ChatTurn] = Field(min_length=1, max_length=40)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _agent_stream(app_state, turns: list[ChatTurn]) -> AsyncGenerator[str, None]:
    # generous read timeout + retries: adaptive thinking can pause the byte
    # stream, and a mid-stream ReadTimeout otherwise kills the whole answer
    client = AsyncAnthropic(timeout=600.0, max_retries=2)
    messages: list[dict[str, Any]] = [{"role": t.role, "content": t.content} for t in turns]

    try:
        for _ in range(MAX_TOOL_TURNS):
            async with client.messages.stream(
                model=AGENT_MODEL,
                max_tokens=MAX_TOKENS,
                system=[{"type": "text", "text": SYSTEM_PROMPT,
                         "cache_control": {"type": "ephemeral"}}],
                tools=TOOLS,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield _sse({"type": "text", "text": event.delta.text})
                final = await stream.get_final_message()

            if final.stop_reason != "tool_use":
                yield _sse({"type": "done"})
                return

            tool_results = []
            for block in final.content:
                if block.type != "tool_use":
                    continue
                yield _sse({"type": "tool_start", "name": block.name, "input": block.input})
                executor = TOOL_EXECUTORS.get(block.name)
                try:
                    result = executor(app_state, block.input or {}) if executor else {
                        "error": f"unknown tool {block.name}"
                    }
                    is_error = executor is None
                except Exception as e:  # tool bug should not kill the stream
                    result, is_error = {"error": str(e)}, True
                highlight = result.get("highlight") if isinstance(result, dict) else None
                yield _sse({
                    "type": "tool_result",
                    "name": block.name,
                    "highlight": highlight,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                    **({"is_error": True} if is_error else {}),
                })

            messages.append({"role": "assistant", "content": final.content})
            messages.append({"role": "user", "content": tool_results})

        yield _sse({"type": "text", "text": "\n\n(Stopped after reaching the tool-call limit.)"})
        yield _sse({"type": "done"})
    except Exception as e:
        detail = str(e).strip() or type(e).__name__
        yield _sse({
            "type": "error",
            "message": f"Connection hiccup while streaming ({detail}). Please ask again.",
        })


def create_agent_router(get_app_state) -> APIRouter:
    """get_app_state: callable returning the AppState singleton (avoids import cycle)."""

    @router.post("/api/agent")
    async def agent(request: AgentRequest):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(
                status_code=503,
                detail="Agent unavailable: ANTHROPIC_API_KEY is not configured on the server.",
            )
        return StreamingResponse(
            _agent_stream(get_app_state(), request.messages),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
