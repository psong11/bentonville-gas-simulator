"""
Database CRUD Operations
========================
Async database operations for the gas network.
"""

from typing import Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models import Node, Pipe, Leak, SimulationSnapshot


# ============ NODES ============

async def get_all_nodes(db: AsyncSession) -> list[Node]:
    """Get all nodes."""
    result = await db.execute(select(Node).order_by(Node.id))
    return list(result.scalars().all())


async def get_node(db: AsyncSession, node_id: int) -> Optional[Node]:
    """Get a single node by ID."""
    result = await db.execute(select(Node).where(Node.id == node_id))
    return result.scalar_one_or_none()


async def create_node(db: AsyncSession, **kwargs) -> Node:
    """Create a new node."""
    node = Node(**kwargs)
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node


async def update_node(db: AsyncSession, node_id: int, **kwargs) -> Optional[Node]:
    """Update a node."""
    result = await db.execute(
        update(Node).where(Node.id == node_id).values(**kwargs).returning(Node)
    )
    await db.commit()
    return result.scalar_one_or_none()


async def delete_node(db: AsyncSession, node_id: int) -> bool:
    """Delete a node."""
    result = await db.execute(delete(Node).where(Node.id == node_id))
    await db.commit()
    return result.rowcount > 0


# ============ PIPES ============

async def get_all_pipes(db: AsyncSession) -> list[Pipe]:
    """Get all pipes."""
    result = await db.execute(select(Pipe).order_by(Pipe.id))
    return list(result.scalars().all())


async def get_pipe(db: AsyncSession, pipe_id: int) -> Optional[Pipe]:
    """Get a single pipe by ID."""
    result = await db.execute(select(Pipe).where(Pipe.id == pipe_id))
    return result.scalar_one_or_none()


async def create_pipe(db: AsyncSession, **kwargs) -> Pipe:
    """Create a new pipe."""
    pipe = Pipe(**kwargs)
    db.add(pipe)
    await db.commit()
    await db.refresh(pipe)
    return pipe


async def delete_pipe(db: AsyncSession, pipe_id: int) -> bool:
    """Delete a pipe."""
    result = await db.execute(delete(Pipe).where(Pipe.id == pipe_id))
    await db.commit()
    return result.rowcount > 0


# ============ LEAKS ============

async def get_active_leaks(db: AsyncSession) -> list[Leak]:
    """Get all active (not cleared) leaks."""
    result = await db.execute(
        select(Leak)
        .where(Leak.cleared_at.is_(None))
        .options(selectinload(Leak.node))
    )
    return list(result.scalars().all())


async def create_leak(db: AsyncSession, node_id: int, severity: float = 1.0) -> Leak:
    """Create a new leak."""
    leak = Leak(node_id=node_id, severity=severity)
    db.add(leak)
    await db.commit()
    await db.refresh(leak)
    return leak


async def clear_leak(db: AsyncSession, leak_id: int) -> bool:
    """Clear (fix) a leak."""
    from datetime import datetime
    result = await db.execute(
        update(Leak)
        .where(Leak.id == leak_id, Leak.cleared_at.is_(None))
        .values(cleared_at=datetime.utcnow())
    )
    await db.commit()
    return result.rowcount > 0


async def clear_all_leaks(db: AsyncSession) -> int:
    """Clear all active leaks."""
    from datetime import datetime
    result = await db.execute(
        update(Leak)
        .where(Leak.cleared_at.is_(None))
        .values(cleared_at=datetime.utcnow())
    )
    await db.commit()
    return result.rowcount


# ============ SIMULATION SNAPSHOTS ============

async def get_current_snapshot(db: AsyncSession) -> Optional[SimulationSnapshot]:
    """Get the current simulation snapshot."""
    result = await db.execute(
        select(SimulationSnapshot)
        .where(SimulationSnapshot.is_current == True)
        .order_by(SimulationSnapshot.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def save_snapshot(
    db: AsyncSession,
    source_pressure: float,
    demand_multiplier: float,
    node_pressures: dict,
    pipe_flow_rates: dict,
    node_actual_demand: dict,
    pipe_velocities: dict,
    pipe_pressure_drops: dict,
    pipe_reynolds: dict,
    active_leaks: dict,
    warnings: list,
) -> SimulationSnapshot:
    """Save a new simulation snapshot and mark it as current."""
    # Unmark previous current snapshots
    await db.execute(
        update(SimulationSnapshot)
        .where(SimulationSnapshot.is_current == True)
        .values(is_current=False)
    )
    
    # Create new snapshot
    snapshot = SimulationSnapshot(
        source_pressure=source_pressure,
        demand_multiplier=demand_multiplier,
        node_pressures=node_pressures,
        pipe_flow_rates=pipe_flow_rates,
        node_actual_demand=node_actual_demand,
        pipe_velocities=pipe_velocities,
        pipe_pressure_drops=pipe_pressure_drops,
        pipe_reynolds=pipe_reynolds,
        active_leaks=active_leaks,
        warnings=warnings,
        is_current=True,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


# ============ BULK OPERATIONS ============

async def bulk_create_nodes(db: AsyncSession, nodes_data: list[dict]) -> list[Node]:
    """Bulk create nodes."""
    nodes = [Node(**data) for data in nodes_data]
    db.add_all(nodes)
    await db.commit()
    for node in nodes:
        await db.refresh(node)
    return nodes


async def bulk_create_pipes(db: AsyncSession, pipes_data: list[dict]) -> list[Pipe]:
    """Bulk create pipes."""
    pipes = [Pipe(**data) for data in pipes_data]
    db.add_all(pipes)
    await db.commit()
    for pipe in pipes:
        await db.refresh(pipe)
    return pipes


async def clear_network(db: AsyncSession) -> None:
    """Clear all network data (for testing/reset)."""
    await db.execute(delete(Leak))
    await db.execute(delete(SimulationSnapshot))
    await db.execute(delete(Pipe))
    await db.execute(delete(Node))
    await db.commit()
