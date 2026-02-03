"""
City Generator Module
=====================
Procedurally generates a realistic gas distribution network for Bentonville.
Uses Random Geometric Graph algorithm for realistic city topology.

The module is designed to be modular - real coordinates can be swapped in
by implementing a custom CoordinateProvider.
"""

import numpy as np
import networkx as nx
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional, Protocol
from enum import Enum
import random
from pathlib import Path


class NodeType(Enum):
    """Types of gas consumption nodes in the network."""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    SOURCE = "source"  # High-pressure supply point


@dataclass
class GasNode:
    """Represents a gas consumption point in the network."""
    id: int
    node_type: str
    x: float  # Longitude or normalized X
    y: float  # Latitude or normalized Y
    base_demand: float  # m³/hour - base gas demand
    elevation: float  # meters - affects pressure calculations
    name: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GasPipe:
    """Represents a gas distribution pipe."""
    id: int
    source_id: int
    target_id: int
    length: float  # meters
    diameter: float  # meters (typical range: 0.05 - 0.5m)
    roughness: float  # meters (pipe roughness for Darcy-Weisbach)
    material: str
    year_installed: int
    
    def to_dict(self) -> dict:
        return asdict(self)


class CoordinateProvider(Protocol):
    """Protocol for coordinate providers - allows swapping procedural for real coordinates."""
    
    def get_bounds(self) -> Tuple[float, float, float, float]:
        """Returns (min_x, max_x, min_y, max_y)."""
        ...
    
    def generate_points(self, n: int) -> List[Tuple[float, float]]:
        """Generate n coordinate points."""
        ...


class ProceduralCoordinateProvider:
    """Generates procedural coordinates that look like a realistic city grid."""
    
    def __init__(
        self,
        center: Tuple[float, float] = (-94.2088, 36.3729),  # Bentonville, AR
        spread: float = 0.05,  # ~5km spread
        seed: Optional[int] = None
    ):
        self.center = center
        self.spread = spread
        self.rng = np.random.default_rng(seed)
    
    def get_bounds(self) -> Tuple[float, float, float, float]:
        return (
            self.center[0] - self.spread,
            self.center[0] + self.spread,
            self.center[1] - self.spread,
            self.center[1] + self.spread
        )
    
    def generate_points(self, n: int) -> List[Tuple[float, float]]:
        """
        Generate points with clustered distribution to simulate
        neighborhoods and commercial districts.
        """
        points = []
        
        # Create cluster centers (neighborhoods)
        n_clusters = max(3, n // 50)
        cluster_centers = [
            (
                self.rng.normal(self.center[0], self.spread * 0.6),
                self.rng.normal(self.center[1], self.spread * 0.6)
            )
            for _ in range(n_clusters)
        ]
        
        # Generate points around clusters
        for i in range(n):
            cluster = cluster_centers[i % n_clusters]
            # Add grid-like offset to simulate streets
            grid_noise = 0.002
            x = cluster[0] + self.rng.normal(0, self.spread * 0.3)
            y = cluster[1] + self.rng.normal(0, self.spread * 0.3)
            
            # Snap to pseudo-grid
            x = round(x / grid_noise) * grid_noise + self.rng.normal(0, grid_noise * 0.1)
            y = round(y / grid_noise) * grid_noise + self.rng.normal(0, grid_noise * 0.1)
            
            points.append((x, y))
        
        return points


class RealCoordinateProvider:
    """
    Placeholder for real Bentonville coordinates.
    Implement this class with actual GIS data when available.
    """
    
    def __init__(self, geojson_path: Optional[str] = None):
        self.geojson_path = geojson_path
        # TODO: Load real coordinates from GeoJSON/Shapefile
        raise NotImplementedError(
            "Real coordinate provider not yet implemented. "
            "Supply GeoJSON data with building footprints."
        )
    
    def get_bounds(self) -> Tuple[float, float, float, float]:
        pass
    
    def generate_points(self, n: int) -> List[Tuple[float, float]]:
        pass


class CityNetworkGenerator:
    """
    Generates a realistic gas distribution network.
    
    The network follows a hierarchical structure:
    1. Source nodes (high pressure supply)
    2. Main distribution lines (large diameter)
    3. Secondary distribution (medium diameter)
    4. Service lines to consumers (small diameter)
    """
    
    # Pipe materials and their typical roughness (meters)
    PIPE_MATERIALS = {
        "steel": 0.000045,
        "ductile_iron": 0.000025,
        "polyethylene": 0.000007,
        "pvc": 0.000005
    }
    
    # Typical demands by node type (m³/hour)
    DEMAND_RANGES = {
        NodeType.RESIDENTIAL: (0.5, 3.0),
        NodeType.COMMERCIAL: (5.0, 50.0),
        NodeType.INDUSTRIAL: (50.0, 500.0),
        NodeType.SOURCE: (0.0, 0.0)  # Sources supply, don't consume
    }
    
    # Node type distribution probabilities
    TYPE_DISTRIBUTION = {
        NodeType.RESIDENTIAL: 0.70,
        NodeType.COMMERCIAL: 0.20,
        NodeType.INDUSTRIAL: 0.10
    }
    
    def __init__(
        self,
        coordinate_provider: Optional[CoordinateProvider] = None,
        seed: Optional[int] = None
    ):
        self.coord_provider = coordinate_provider or ProceduralCoordinateProvider(seed=seed)
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        random.seed(seed)
    
    def generate_network(
        self,
        n_nodes: int = 200,
        n_sources: int = 2,
        connection_radius: float = 0.008,  # ~800m in coordinate units
        ensure_connected: bool = True
    ) -> Tuple[List[GasNode], List[GasPipe], nx.Graph]:
        """
        Generate a complete gas distribution network.
        
        Args:
            n_nodes: Number of consumption nodes
            n_sources: Number of high-pressure source nodes
            connection_radius: Maximum distance for pipe connections
            ensure_connected: If True, ensures all nodes are reachable
            
        Returns:
            Tuple of (nodes, pipes, networkx_graph)
        """
        # Generate coordinates
        coords = self.coord_provider.generate_points(n_nodes + n_sources)
        
        # Create graph using Random Geometric Graph approach
        G = nx.Graph()
        
        # Add nodes
        nodes = []
        for i, (x, y) in enumerate(coords):
            if i < n_sources:
                node_type = NodeType.SOURCE
                name = f"Supply Station {i + 1}"
            else:
                # Weighted random selection of node type
                rand_val = self.rng.random()
                cumulative = 0
                node_type = NodeType.RESIDENTIAL
                for ntype, prob in self.TYPE_DISTRIBUTION.items():
                    cumulative += prob
                    if rand_val <= cumulative:
                        node_type = ntype
                        break
                
                name = self._generate_node_name(node_type, i)
            
            # Generate demand based on type
            demand_range = self.DEMAND_RANGES[node_type]
            base_demand = self.rng.uniform(*demand_range)
            
            # Generate elevation (affects pressure)
            elevation = self.rng.uniform(350, 450)  # Bentonville elevation range
            
            node = GasNode(
                id=i,
                node_type=node_type.value,
                x=x,
                y=y,
                base_demand=round(base_demand, 2),
                elevation=round(elevation, 1),
                name=name
            )
            nodes.append(node)
            G.add_node(i, **node.to_dict())
        
        # Create edges using proximity
        pipes = []
        pipe_id = 0
        
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                dist = self._calculate_distance(nodes[i], nodes[j])
                
                # Connect if within radius
                if dist <= connection_radius:
                    # Probability of connection decreases with distance
                    prob = 1.0 - (dist / connection_radius) ** 0.5
                    if self.rng.random() < prob:
                        pipe = self._create_pipe(pipe_id, nodes[i], nodes[j], dist)
                        pipes.append(pipe)
                        G.add_edge(i, j, **pipe.to_dict())
                        pipe_id += 1
        
        # Ensure connectivity
        if ensure_connected:
            pipes, pipe_id = self._ensure_connectivity(G, nodes, pipes, pipe_id)
        
        # Ensure sources are well-connected
        pipes, pipe_id = self._connect_sources(G, nodes, pipes, pipe_id, n_sources)
        
        return nodes, pipes, G
    
    def _calculate_distance(self, node1: GasNode, node2: GasNode) -> float:
        """Calculate Euclidean distance between nodes."""
        return np.sqrt((node1.x - node2.x)**2 + (node1.y - node2.y)**2)
    
    def _create_pipe(
        self,
        pipe_id: int,
        source: GasNode,
        target: GasNode,
        coord_distance: float
    ) -> GasPipe:
        """Create a pipe between two nodes with realistic properties."""
        # Convert coordinate distance to meters (rough approximation)
        length = coord_distance * 111000  # ~111km per degree
        
        # Determine pipe characteristics based on node types
        source_type = source.node_type
        target_type = target.node_type
        
        # Larger pipes for industrial/commercial connections
        if source_type == "source" or target_type == "source":
            diameter = self.rng.uniform(0.3, 0.5)  # Main supply lines
            material = "steel"
        elif source_type == "industrial" or target_type == "industrial":
            diameter = self.rng.uniform(0.15, 0.3)
            material = random.choice(["steel", "ductile_iron"])
        elif source_type == "commercial" or target_type == "commercial":
            diameter = self.rng.uniform(0.1, 0.2)
            material = random.choice(["steel", "ductile_iron", "polyethylene"])
        else:
            diameter = self.rng.uniform(0.05, 0.1)
            material = random.choice(["polyethylene", "pvc"])
        
        roughness = self.PIPE_MATERIALS[material]
        year = int(self.rng.integers(1970, 2024))
        
        # Older pipes have higher roughness
        age_factor = 1 + (2024 - year) * 0.01
        roughness *= age_factor
        
        return GasPipe(
            id=pipe_id,
            source_id=source.id,
            target_id=target.id,
            length=round(length, 1),
            diameter=round(diameter, 3),
            roughness=round(roughness, 7),
            material=material,
            year_installed=year
        )
    
    def _ensure_connectivity(
        self,
        G: nx.Graph,
        nodes: List[GasNode],
        pipes: List[GasPipe],
        pipe_id: int
    ) -> Tuple[List[GasPipe], int]:
        """Ensure the graph is fully connected."""
        components = list(nx.connected_components(G))
        
        while len(components) > 1:
            # Connect two closest components
            min_dist = float('inf')
            best_pair = None
            
            for i, comp1 in enumerate(components):
                for comp2 in components[i + 1:]:
                    for n1 in comp1:
                        for n2 in comp2:
                            dist = self._calculate_distance(nodes[n1], nodes[n2])
                            if dist < min_dist:
                                min_dist = dist
                                best_pair = (n1, n2)
            
            if best_pair:
                n1, n2 = best_pair
                pipe = self._create_pipe(pipe_id, nodes[n1], nodes[n2], min_dist)
                pipes.append(pipe)
                G.add_edge(n1, n2, **pipe.to_dict())
                pipe_id += 1
            
            components = list(nx.connected_components(G))
        
        return pipes, pipe_id
    
    def _connect_sources(
        self,
        G: nx.Graph,
        nodes: List[GasNode],
        pipes: List[GasPipe],
        pipe_id: int,
        n_sources: int
    ) -> Tuple[List[GasPipe], int]:
        """Ensure source nodes are well-connected to the network."""
        for source_id in range(n_sources):
            source = nodes[source_id]
            
            # Ensure at least 3 connections from each source
            current_degree = G.degree(source_id)
            if current_degree < 3:
                # Find nearest non-connected nodes
                distances = []
                for i, node in enumerate(nodes):
                    if i != source_id and not G.has_edge(source_id, i):
                        dist = self._calculate_distance(source, node)
                        distances.append((dist, i))
                
                distances.sort()
                
                for dist, target_id in distances[:3 - current_degree]:
                    pipe = self._create_pipe(pipe_id, source, nodes[target_id], dist)
                    pipes.append(pipe)
                    G.add_edge(source_id, target_id, **pipe.to_dict())
                    pipe_id += 1
        
        return pipes, pipe_id
    
    def _generate_node_name(self, node_type: NodeType, index: int) -> str:
        """Generate a realistic name for a node."""
        residential_names = [
            "Oak Street", "Maple Drive", "Cedar Lane", "Pine Court",
            "Elm Avenue", "Walnut Way", "Birch Road", "Willow Place",
            "Cherry Hill", "Hickory Lane", "Spruce Street", "Ash Drive"
        ]
        
        commercial_names = [
            "Walmart Store", "Sam's Club", "Downtown Plaza", "Market Square",
            "Business Center", "Shopping Center", "Retail Park", "Commerce Way",
            "Trade Center", "Service Station", "Office Complex", "Medical Center"
        ]
        
        industrial_names = [
            "Distribution Center", "Warehouse Complex", "Manufacturing Plant",
            "Processing Facility", "Industrial Park", "Logistics Hub",
            "Factory Site", "Production Center"
        ]
        
        if node_type == NodeType.RESIDENTIAL:
            name = random.choice(residential_names)
            return f"{index} {name}"
        elif node_type == NodeType.COMMERCIAL:
            return f"{random.choice(commercial_names)} #{index}"
        else:
            return f"{random.choice(industrial_names)} #{index}"
    
    def save_network(
        self,
        nodes: List[GasNode],
        pipes: List[GasPipe],
        filepath: str
    ) -> None:
        """Save the network to a JSON file."""
        data = {
            "metadata": {
                "version": "1.0",
                "generator": "CityNetworkGenerator",
                "n_nodes": len(nodes),
                "n_pipes": len(pipes),
                "seed": self.seed
            },
            "nodes": [n.to_dict() for n in nodes],
            "pipes": [p.to_dict() for p in pipes]
        }
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def load_network(filepath: str) -> Tuple[List[GasNode], List[GasPipe], nx.Graph]:
        """Load a network from a JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        nodes = [GasNode(**n) for n in data['nodes']]
        pipes = [GasPipe(**p) for p in data['pipes']]
        
        # Reconstruct graph
        G = nx.Graph()
        for node in nodes:
            G.add_node(node.id, **node.to_dict())
        for pipe in pipes:
            G.add_edge(pipe.source_id, pipe.target_id, **pipe.to_dict())
        
        return nodes, pipes, G


def generate_sample_network(
    n_nodes: int = 200,
    seed: Optional[int] = None,
    output_path: str = "data/network_data.json"
) -> Tuple[List[GasNode], List[GasPipe], nx.Graph]:
    """Convenience function to generate and save a sample network."""
    generator = CityNetworkGenerator(seed=seed)
    nodes, pipes, G = generator.generate_network(n_nodes=n_nodes)
    generator.save_network(nodes, pipes, output_path)
    return nodes, pipes, G


if __name__ == "__main__":
    # Generate a sample network for testing
    nodes, pipes, G = generate_sample_network(n_nodes=200, seed=42)
    print(f"Generated network with {len(nodes)} nodes and {len(pipes)} pipes")
    print(f"Network is connected: {nx.is_connected(G)}")
