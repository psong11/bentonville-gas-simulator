"""
Test Suite for City Generator Module
=====================================
Tests the procedural network generation functionality including:
- Node generation and types
- Pipe creation and properties
- Graph connectivity
- Coordinate providers
- Save/Load functionality
"""

import pytest
import numpy as np
import networkx as nx
import tempfile
import json
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from city_gen import (
    CityNetworkGenerator,
    ProceduralCoordinateProvider,
    GasNode,
    GasPipe,
    NodeType,
    generate_sample_network
)


class TestProceduralCoordinateProvider:
    """Tests for the ProceduralCoordinateProvider class."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        provider = ProceduralCoordinateProvider()
        assert provider.center == (-94.2088, 36.3729)  # Bentonville coords
        assert provider.spread == 0.05
    
    def test_initialization_custom(self):
        """Test custom initialization."""
        provider = ProceduralCoordinateProvider(
            center=(-100.0, 40.0),
            spread=0.1,
            seed=42
        )
        assert provider.center == (-100.0, 40.0)
        assert provider.spread == 0.1
    
    def test_get_bounds(self):
        """Test bounds calculation."""
        provider = ProceduralCoordinateProvider(
            center=(0.0, 0.0),
            spread=1.0
        )
        bounds = provider.get_bounds()
        assert bounds == (-1.0, 1.0, -1.0, 1.0)
    
    def test_generate_points_count(self):
        """Test that correct number of points are generated."""
        provider = ProceduralCoordinateProvider(seed=42)
        points = provider.generate_points(100)
        assert len(points) == 100
    
    def test_generate_points_reproducibility(self):
        """Test that same seed produces same points."""
        provider1 = ProceduralCoordinateProvider(seed=42)
        provider2 = ProceduralCoordinateProvider(seed=42)
        
        points1 = provider1.generate_points(50)
        points2 = provider2.generate_points(50)
        
        for p1, p2 in zip(points1, points2):
            assert p1[0] == pytest.approx(p2[0], rel=1e-10)
            assert p1[1] == pytest.approx(p2[1], rel=1e-10)
    
    def test_generate_points_within_bounds(self):
        """Test that generated points are roughly within expected bounds."""
        provider = ProceduralCoordinateProvider(
            center=(0.0, 0.0),
            spread=0.1,
            seed=42
        )
        points = provider.generate_points(100)
        
        for x, y in points:
            # Points should be within ~3 standard deviations
            assert -0.5 < x < 0.5
            assert -0.5 < y < 0.5


class TestGasNode:
    """Tests for the GasNode dataclass."""
    
    def test_creation(self):
        """Test node creation."""
        node = GasNode(
            id=1,
            node_type="residential",
            x=-94.2,
            y=36.37,
            base_demand=2.5,
            elevation=400.0,
            name="Test Node"
        )
        assert node.id == 1
        assert node.node_type == "residential"
        assert node.base_demand == 2.5
    
    def test_to_dict(self):
        """Test dictionary conversion."""
        node = GasNode(
            id=1,
            node_type="commercial",
            x=-94.2,
            y=36.37,
            base_demand=15.0,
            elevation=410.0,
            name="Store #1"
        )
        d = node.to_dict()
        assert d['id'] == 1
        assert d['node_type'] == "commercial"
        assert d['base_demand'] == 15.0


class TestGasPipe:
    """Tests for the GasPipe dataclass."""
    
    def test_creation(self):
        """Test pipe creation."""
        pipe = GasPipe(
            id=1,
            source_id=0,
            target_id=1,
            length=500.0,
            diameter=0.15,
            roughness=0.000045,
            material="steel",
            year_installed=2010
        )
        assert pipe.id == 1
        assert pipe.length == 500.0
        assert pipe.material == "steel"
    
    def test_to_dict(self):
        """Test dictionary conversion."""
        pipe = GasPipe(
            id=5,
            source_id=2,
            target_id=3,
            length=250.0,
            diameter=0.1,
            roughness=0.000007,
            material="polyethylene",
            year_installed=2020
        )
        d = pipe.to_dict()
        assert d['id'] == 5
        assert d['diameter'] == 0.1
        assert d['material'] == "polyethylene"


class TestCityNetworkGenerator:
    """Tests for the CityNetworkGenerator class."""
    
    @pytest.fixture
    def generator(self):
        """Create a generator with fixed seed for reproducibility."""
        return CityNetworkGenerator(seed=42)
    
    def test_initialization(self, generator):
        """Test generator initialization."""
        assert generator.seed == 42
        assert generator.coord_provider is not None
    
    def test_generate_network_node_count(self, generator):
        """Test that correct number of nodes are generated."""
        nodes, pipes, G = generator.generate_network(n_nodes=50, n_sources=2)
        assert len(nodes) == 52  # 50 + 2 sources
    
    def test_generate_network_has_sources(self, generator):
        """Test that source nodes are created."""
        nodes, pipes, G = generator.generate_network(n_nodes=50, n_sources=3)
        source_nodes = [n for n in nodes if n.node_type == "source"]
        assert len(source_nodes) == 3
    
    def test_generate_network_connectivity(self, generator):
        """Test that network is connected."""
        nodes, pipes, G = generator.generate_network(
            n_nodes=100,
            ensure_connected=True
        )
        assert nx.is_connected(G)
    
    def test_generate_network_node_types(self, generator):
        """Test that various node types are generated."""
        nodes, pipes, G = generator.generate_network(n_nodes=200)
        
        types = set(n.node_type for n in nodes)
        assert "source" in types
        assert "residential" in types
        # Commercial and industrial should appear with 200 nodes
        assert len(types) >= 2
    
    def test_generate_network_pipe_properties(self, generator):
        """Test that pipes have valid properties."""
        nodes, pipes, G = generator.generate_network(n_nodes=50)
        
        for pipe in pipes:
            assert pipe.length > 0
            assert 0.01 < pipe.diameter < 1.0  # Reasonable diameter range
            assert pipe.roughness > 0
            assert pipe.material in ["steel", "ductile_iron", "polyethylene", "pvc"]
            assert 1950 <= pipe.year_installed <= 2030
    
    def test_generate_network_reproducibility(self):
        """Test that same seed produces same network."""
        gen1 = CityNetworkGenerator(seed=123)
        gen2 = CityNetworkGenerator(seed=123)
        
        nodes1, pipes1, G1 = gen1.generate_network(n_nodes=50)
        nodes2, pipes2, G2 = gen2.generate_network(n_nodes=50)
        
        assert len(nodes1) == len(nodes2)
        assert len(pipes1) == len(pipes2)
        
        # Check first few nodes match
        for n1, n2 in zip(nodes1[:5], nodes2[:5]):
            assert n1.id == n2.id
            assert n1.x == pytest.approx(n2.x, rel=1e-10)
    
    def test_save_and_load_network(self, generator):
        """Test saving and loading network."""
        nodes, pipes, G = generator.generate_network(n_nodes=30)
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filepath = f.name
        
        try:
            # Save
            generator.save_network(nodes, pipes, filepath)
            
            # Verify file exists and has content
            assert Path(filepath).exists()
            with open(filepath) as f:
                data = json.load(f)
            assert 'nodes' in data
            assert 'pipes' in data
            assert len(data['nodes']) == len(nodes)
            
            # Load
            loaded_nodes, loaded_pipes, loaded_G = CityNetworkGenerator.load_network(filepath)
            
            assert len(loaded_nodes) == len(nodes)
            assert len(loaded_pipes) == len(pipes)
            assert nx.is_connected(loaded_G)
        finally:
            Path(filepath).unlink(missing_ok=True)


class TestGenerateSampleNetwork:
    """Tests for the convenience function."""
    
    def test_generate_sample_network(self):
        """Test the convenience function."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filepath = f.name
        
        try:
            nodes, pipes, G = generate_sample_network(
                n_nodes=50,
                seed=42,
                output_path=filepath
            )
            
            assert len(nodes) > 50  # Includes sources
            assert len(pipes) > 0
            assert nx.is_connected(G)
            assert Path(filepath).exists()
        finally:
            Path(filepath).unlink(missing_ok=True)


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_small_network(self):
        """Test very small network generation."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=5, n_sources=1)
        
        assert len(nodes) == 6
        assert nx.is_connected(G)
    
    def test_large_network(self):
        """Test larger network generation."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=300)
        
        assert len(nodes) > 300
        assert nx.is_connected(G)
    
    def test_single_source(self):
        """Test network with single source."""
        generator = CityNetworkGenerator(seed=42)
        nodes, pipes, G = generator.generate_network(n_nodes=50, n_sources=1)
        
        sources = [n for n in nodes if n.node_type == "source"]
        assert len(sources) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
