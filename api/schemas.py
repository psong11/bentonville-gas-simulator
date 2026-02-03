"""
Pydantic Schemas for API Request/Response Validation
====================================================
These models define the API contract between frontend and backend.
They mirror the dataclasses in city_gen.py and physics.py.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class NodeType(str, Enum):
    """Types of gas consumption nodes."""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    SOURCE = "source"


class LeakDetectionStrategy(str, Enum):
    """Available leak detection algorithms."""
    PRESSURE_DROP = "pressure_drop"
    FLOW_IMBALANCE = "flow_imbalance"
    COMBINED = "combined"


# ============================================================================
# Network Models
# ============================================================================

class NodeSchema(BaseModel):
    """Gas network node (consumption point)."""
    id: int
    node_type: str
    x: float = Field(..., description="Longitude or normalized X coordinate")
    y: float = Field(..., description="Latitude or normalized Y coordinate")
    base_demand: float = Field(..., description="Base gas demand in m³/hour")
    elevation: float = Field(..., description="Elevation in meters")
    name: str

    model_config = {"from_attributes": True}  # Allows creating from dataclass


class PipeSchema(BaseModel):
    """Gas distribution pipe."""
    id: int
    source_id: int
    target_id: int
    length: float = Field(..., description="Pipe length in meters")
    diameter: float = Field(..., description="Pipe diameter in meters")
    roughness: float = Field(..., description="Pipe roughness for Darcy-Weisbach")
    material: str
    year_installed: int

    model_config = {"from_attributes": True}


class NetworkResponse(BaseModel):
    """Complete network data response."""
    nodes: List[NodeSchema]
    pipes: List[PipeSchema]


class GenerateNetworkRequest(BaseModel):
    """Request to generate a new network."""
    node_count: int = Field(default=50, ge=10, le=200, description="Number of nodes to generate")


# ============================================================================
# Simulation Models
# ============================================================================

class SimulationRequest(BaseModel):
    """Request to run a simulation."""
    source_pressure: float = Field(
        default=400.0, 
        ge=100.0, 
        le=1000.0,
        description="Source pressure in kPa"
    )
    demand_multiplier: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Demand multiplier for peak simulation"
    )
    active_leaks: List[int] = Field(
        default_factory=list,
        description="List of node IDs with active leaks"
    )


class SimulationResponse(BaseModel):
    """Simulation results."""
    node_pressures: Dict[int, float] = Field(..., description="Pressure at each node in kPa")
    node_actual_demand: Dict[int, float] = Field(..., description="Actual demand at each node in m³/h")
    pipe_flow_rates: Dict[int, float] = Field(..., description="Flow rate in each pipe in m³/h")
    pipe_velocities: Dict[int, float] = Field(..., description="Velocity in each pipe in m/s")
    pipe_pressure_drops: Dict[int, float] = Field(..., description="Pressure drop in each pipe in kPa")
    pipe_reynolds: Dict[int, float] = Field(..., description="Reynolds number in each pipe")
    active_leaks: Dict[int, float] = Field(..., description="Active leaks: node_id -> leak_rate")
    warnings: List[str] = Field(default_factory=list, description="Simulation warnings")


# ============================================================================
# Leak Detection Models
# ============================================================================

class LeakDetectionRequest(BaseModel):
    """Request to run leak detection."""
    strategy: LeakDetectionStrategy = Field(
        default=LeakDetectionStrategy.COMBINED,
        description="Detection algorithm to use"
    )
    num_sensors: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of sensors to use for detection"
    )
    sensor_node_ids: Optional[List[int]] = Field(
        default=None,
        description="Specific node IDs to place sensors on (overrides num_sensors if provided)"
    )


class SuspectedLeak(BaseModel):
    """A suspected leak location."""
    node_id: int
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    pressure: Optional[float] = None
    flow_imbalance: Optional[float] = None


class LeakDetectionResponse(BaseModel):
    """Leak detection results."""
    suspected_leaks: List[SuspectedLeak]
    detected_leaks: List[int] = Field(default_factory=list, description="Node IDs of detected leaks")
    sensor_placements: List[int] = Field(default_factory=list, description="Node IDs where sensors are placed")
    detection_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Fraction of actual leaks detected")
    false_positive_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Fraction of detections that are false positives")
    strategy_used: str
    detection_time_ms: float


class InjectLeaksRequest(BaseModel):
    """Request to inject leaks - either random or specific nodes."""
    count: int = Field(default=3, ge=1, le=10, description="Number of leaks to inject (used for random injection)")
    node_ids: Optional[List[int]] = Field(default=None, description="Specific node IDs to inject leaks into (overrides count if provided)")


class InjectLeaksResponse(BaseModel):
    """Response after injecting leaks."""
    injected_node_ids: List[int]


# ============================================================================
# WebSocket Models
# ============================================================================

class WSMessageType(str, Enum):
    """WebSocket message types."""
    # Client -> Server
    SET_PRESSURE = "SET_PRESSURE"
    SET_DEMAND_MULTIPLIER = "SET_DEMAND_MULTIPLIER"
    INJECT_LEAK = "INJECT_LEAK"
    CLEAR_LEAKS = "CLEAR_LEAKS"
    HIGHLIGHT_PIPE = "HIGHLIGHT_PIPE"
    
    # Server -> Client
    SIMULATION_UPDATE = "SIMULATION_UPDATE"
    NETWORK_UPDATE = "NETWORK_UPDATE"
    LEAK_ALERT = "LEAK_ALERT"
    ERROR = "ERROR"


class WSMessage(BaseModel):
    """Base WebSocket message."""
    type: WSMessageType
    payload: dict = Field(default_factory=dict)


# ============================================================================
# Health Check
# ============================================================================

class HealthResponse(BaseModel):
    """API health check response."""
    status: str = "ok"
    version: str = "1.0.0"
