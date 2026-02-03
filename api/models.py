"""
SQLAlchemy Models
=================
Database models for the gas distribution network.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from api.database import Base


class NodeType(enum.Enum):
    """Types of gas consumption nodes."""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    SOURCE = "source"


class Node(Base):
    """Gas network node (consumption point)."""
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)  # Longitude
    y: Mapped[float] = mapped_column(Float, nullable=False)  # Latitude
    base_demand: Mapped[float] = mapped_column(Float, default=0.0)
    elevation: Mapped[float] = mapped_column(Float, default=0.0)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    outgoing_pipes: Mapped[list["Pipe"]] = relationship(
        "Pipe", foreign_keys="Pipe.source_id", back_populates="source_node"
    )
    incoming_pipes: Mapped[list["Pipe"]] = relationship(
        "Pipe", foreign_keys="Pipe.target_id", back_populates="target_node"
    )
    leaks: Mapped[list["Leak"]] = relationship("Leak", back_populates="node")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "node_type": self.node_type,
            "x": self.x,
            "y": self.y,
            "base_demand": self.base_demand,
            "elevation": self.elevation,
            "name": self.name,
        }


class Pipe(Base):
    """Gas distribution pipe."""
    __tablename__ = "pipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("nodes.id"), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, ForeignKey("nodes.id"), nullable=False)
    length: Mapped[float] = mapped_column(Float, nullable=False)  # meters
    diameter: Mapped[float] = mapped_column(Float, nullable=False)  # meters
    roughness: Mapped[float] = mapped_column(Float, default=0.0001)
    material: Mapped[str] = mapped_column(String(50), default="steel")
    year_installed: Mapped[int] = mapped_column(Integer, default=2000)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source_node: Mapped["Node"] = relationship("Node", foreign_keys=[source_id], back_populates="outgoing_pipes")
    target_node: Mapped["Node"] = relationship("Node", foreign_keys=[target_id], back_populates="incoming_pipes")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "length": self.length,
            "diameter": self.diameter,
            "roughness": self.roughness,
            "material": self.material,
            "year_installed": self.year_installed,
        }


class Leak(Base):
    """Active leak in the network."""
    __tablename__ = "leaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("nodes.id"), nullable=False)
    severity: Mapped[float] = mapped_column(Float, default=1.0)  # Leak rate multiplier
    detected: Mapped[bool] = mapped_column(default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    node: Mapped["Node"] = relationship("Node", back_populates="leaks")

    @property
    def is_active(self) -> bool:
        return self.cleared_at is None


class SimulationSnapshot(Base):
    """Cached simulation results for quick retrieval."""
    __tablename__ = "simulation_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_pressure: Mapped[float] = mapped_column(Float, nullable=False)
    demand_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    
    # Store full simulation state as JSON
    node_pressures: Mapped[dict] = mapped_column(JSON, default=dict)
    pipe_flow_rates: Mapped[dict] = mapped_column(JSON, default=dict)
    node_actual_demand: Mapped[dict] = mapped_column(JSON, default=dict)
    pipe_velocities: Mapped[dict] = mapped_column(JSON, default=dict)
    pipe_pressure_drops: Mapped[dict] = mapped_column(JSON, default=dict)
    pipe_reynolds: Mapped[dict] = mapped_column(JSON, default=dict)
    active_leaks: Mapped[dict] = mapped_column(JSON, default=dict)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Flag for current/latest snapshot
    is_current: Mapped[bool] = mapped_column(default=False, index=True)
