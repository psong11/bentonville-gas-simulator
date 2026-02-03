"""
FastAPI Main Application
========================
Entry point for the API server with CORS, routes, and WebSocket support.
Phase 6: Now with PostgreSQL persistence.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import List, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
import json

from api.schemas import (
    HealthResponse,
    NetworkResponse,
    GenerateNetworkRequest,
    SimulationRequest,
    SimulationResponse,
    LeakDetectionRequest,
    LeakDetectionResponse,
    InjectLeaksRequest,
    InjectLeaksResponse,
    NodeSchema,
    PipeSchema,
    SuspectedLeak,
    WSMessage,
    WSMessageType,
)
from api.state import AppState
from api.database import init_db, close_db, get_db


# ============================================================================
# Application State (will be replaced by PostgreSQL in Phase 6)
# ============================================================================

app_state = AppState()


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        if not self.active_connections:
            return
        
        message_json = json.dumps(message)
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.add(connection)
        
        # Clean up dead connections
        self.active_connections -= disconnected
    
    async def broadcast_simulation_update(self, state: SimulationResponse):
        """Broadcast simulation state to all clients."""
        await self.broadcast({
            "type": WSMessageType.SIMULATION_UPDATE.value,
            "payload": state.model_dump()
        })


manager = ConnectionManager()


# ============================================================================
# Lifespan (startup/shutdown)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup: Initialize database and load network
    print("🚀 Starting Bentonville Gas Simulator API...")
    
    # Initialize PostgreSQL connection pool
    use_db = os.getenv("USE_DATABASE", "false").lower() == "true"
    if use_db:
        try:
            await init_db()
            print("✅ PostgreSQL database connected")
        except Exception as e:
            print(f"⚠️ Database connection failed: {e}")
            print("   Falling back to file-based storage")
    
    # Load existing network from file (legacy mode)
    app_state.load_network_if_exists()
    
    yield
    
    # Shutdown: Close database connections
    print("👋 Shutting down API...")
    if use_db:
        await close_db()


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Bentonville Gas Simulator API",
    description="Real-time gas distribution network simulation with Darcy-Weisbach physics",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration - allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative React port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Check if the API is running."""
    return HealthResponse()


# ============================================================================
# Network Routes
# ============================================================================

@app.get("/api/network", response_model=NetworkResponse, tags=["Network"])
async def get_network():
    """Get the current network configuration."""
    return app_state.get_network()


@app.post("/api/network/generate", response_model=NetworkResponse, tags=["Network"])
async def generate_network(request: GenerateNetworkRequest):
    """Generate a new network with the specified number of nodes."""
    network = app_state.generate_network(request.node_count)
    
    # Broadcast network update to all WebSocket clients
    await manager.broadcast({
        "type": WSMessageType.NETWORK_UPDATE.value,
        "payload": network.model_dump()
    })
    
    return network


# ============================================================================
# Simulation Routes
# ============================================================================

@app.post("/api/simulate", response_model=SimulationResponse, tags=["Simulation"])
async def run_simulation(request: SimulationRequest):
    """Run physics simulation with current parameters."""
    result = app_state.run_simulation(
        source_pressure=request.source_pressure,
        demand_multiplier=request.demand_multiplier,
        active_leaks=request.active_leaks,
    )
    
    # Broadcast simulation update to all WebSocket clients
    await manager.broadcast_simulation_update(result)
    
    return result


@app.get("/api/simulation/state", response_model=SimulationResponse, tags=["Simulation"])
async def get_simulation_state():
    """Get the current simulation state without re-running."""
    return app_state.get_current_simulation_state()


# ============================================================================
# Leak Detection Routes
# ============================================================================

@app.post("/api/leaks/detect", response_model=LeakDetectionResponse, tags=["Leaks"])
async def detect_leaks(request: LeakDetectionRequest):
    """Run leak detection with the specified strategy."""
    return app_state.detect_leaks(request.strategy.value, request.num_sensors)


@app.post("/api/leaks/inject", response_model=InjectLeaksResponse, tags=["Leaks"])
async def inject_leaks(request: InjectLeaksRequest):
    """Inject leaks into the network. Replaces any existing leaks."""
    result = app_state.inject_leaks(request.count, request.node_ids)
    
    # Broadcast leak alert to all WebSocket clients
    await manager.broadcast({
        "type": WSMessageType.LEAK_ALERT.value,
        "payload": {"injected_node_ids": result.injected_node_ids}
    })
    
    # Also broadcast updated simulation state so clients see active_leaks
    sim_state = app_state.get_current_simulation_state()
    await manager.broadcast_simulation_update(sim_state)
    
    return result


@app.post("/api/leaks/clear", tags=["Leaks"])
async def clear_leaks():
    """Clear all active leaks."""
    app_state.clear_leaks()
    return {"status": "ok", "message": "All leaks cleared"}


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    
    Client can send:
    - SET_PRESSURE: {"type": "SET_PRESSURE", "payload": {"value": 500}}
    - SET_DEMAND_MULTIPLIER: {"type": "SET_DEMAND_MULTIPLIER", "payload": {"value": 1.5}}
    - INJECT_LEAK: {"type": "INJECT_LEAK", "payload": {"count": 2}}
    - CLEAR_LEAKS: {"type": "CLEAR_LEAKS", "payload": {}}
    - HIGHLIGHT_PIPE: {"type": "HIGHLIGHT_PIPE", "payload": {"pipeId": 5}}
    
    Server broadcasts:
    - SIMULATION_UPDATE: Full simulation state after changes
    - NETWORK_UPDATE: Network topology changed
    - LEAK_ALERT: New leaks detected or injected
    """
    await manager.connect(websocket)
    
    # Send current state on connect
    try:
        current_state = app_state.get_current_simulation_state()
        await websocket.send_text(json.dumps({
            "type": WSMessageType.SIMULATION_UPDATE.value,
            "payload": current_state.model_dump()
        }))
    except Exception as e:
        print(f"Error sending initial state: {e}")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")
            payload = message.get("payload", {})
            
            try:
                if msg_type == WSMessageType.SET_PRESSURE.value:
                    value = payload.get("value", 400.0)
                    result = app_state.run_simulation(source_pressure=value)
                    await manager.broadcast_simulation_update(result)
                
                elif msg_type == WSMessageType.SET_DEMAND_MULTIPLIER.value:
                    value = payload.get("value", 1.0)
                    result = app_state.run_simulation(demand_multiplier=value)
                    await manager.broadcast_simulation_update(result)
                
                elif msg_type == WSMessageType.INJECT_LEAK.value:
                    count = payload.get("count", 1)
                    leak_result = app_state.inject_leaks(count)
                    await manager.broadcast({
                        "type": WSMessageType.LEAK_ALERT.value,
                        "payload": {"injected_node_ids": leak_result.injected_node_ids}
                    })
                    # Re-run simulation with new leaks
                    result = app_state.run_simulation()
                    await manager.broadcast_simulation_update(result)
                
                elif msg_type == WSMessageType.CLEAR_LEAKS.value:
                    app_state.clear_leaks()
                    result = app_state.run_simulation()
                    await manager.broadcast_simulation_update(result)
                
                elif msg_type == WSMessageType.HIGHLIGHT_PIPE.value:
                    # Broadcast pipe highlight to all clients (for multi-user sync)
                    pipe_id = payload.get("pipeId")
                    await manager.broadcast({
                        "type": "HIGHLIGHT_PIPE",
                        "payload": {"pipeId": pipe_id}
                    })
                
                else:
                    await websocket.send_text(json.dumps({
                        "type": WSMessageType.ERROR.value,
                        "payload": {"message": f"Unknown message type: {msg_type}"}
                    }))
                    
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": WSMessageType.ERROR.value,
                    "payload": {"message": str(e)}
                }))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
