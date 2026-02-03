"""
Leak Detection Module
=====================
Intelligent leak detection algorithm using graph analysis and pressure anomalies.

Detection Strategies:
1. Pressure Deficit Analysis - Compare expected vs actual pressure
2. Graph Propagation - Trace low pressure back to source
3. Flow Imbalance - Detect nodes with supply-demand mismatch
4. Clustering - Group affected nodes to find leak epicenter
"""

import numpy as np
import networkx as nx
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
import heapq


@dataclass
class LeakDetectionResult:
    """Result of leak detection analysis."""
    detected_leaks: List[Dict]  # List of suspected leak locations
    affected_nodes: List[int]  # Nodes impacted by detected leaks
    confidence_scores: Dict[int, float]  # node_id -> confidence (0-1)
    analysis_details: Dict  # Additional analysis information
    recommendations: List[str]  # Action recommendations


@dataclass
class AnomalyScore:
    """Anomaly score for a single node."""
    node_id: int
    pressure_deficit: float  # Expected - Actual pressure
    deficit_ratio: float  # Deficit as percentage
    neighbor_avg_pressure: float
    is_isolated_drop: bool  # True if neighbors have normal pressure
    downstream_affected: int  # Number of downstream nodes affected
    score: float  # Combined anomaly score


class LeakDetector:
    """
    Intelligent leak detection system for gas distribution networks.
    
    Uses multiple detection strategies:
    1. Pressure Threshold Analysis
    2. Spatial Clustering of Anomalies
    3. Graph-based Propagation Tracing
    4. Statistical Outlier Detection
    """
    
    def __init__(
        self,
        pressure_deficit_threshold: float = 50.0,  # kPa
        deficit_ratio_threshold: float = 0.3,  # 30% drop
        min_confidence_threshold: float = 0.5,
        source_pressure: float = 400.0
    ):
        self.pressure_deficit_threshold = pressure_deficit_threshold
        self.deficit_ratio_threshold = deficit_ratio_threshold
        self.min_confidence_threshold = min_confidence_threshold
        self.source_pressure = source_pressure
    
    def analyze_network(
        self,
        graph: nx.Graph,
        nodes: List,
        pipes: List,
        simulation_state,  # SimulationState from physics module
        baseline_state = None  # Optional baseline for comparison
    ) -> LeakDetectionResult:
        """
        Perform comprehensive leak detection analysis.
        
        Args:
            graph: NetworkX graph of the network
            nodes: List of GasNode objects
            pipes: List of GasPipe objects
            simulation_state: Current SimulationState
            baseline_state: Optional baseline SimulationState for comparison
            
        Returns:
            LeakDetectionResult with detected leaks and analysis
        """
        # Build node lookup
        node_dict = {n.id: n for n in nodes}
        source_ids = {n.id for n in nodes if n.node_type == "source"}
        
        # Step 1: Calculate expected pressures (baseline or theoretical)
        if baseline_state:
            expected_pressures = baseline_state.node_pressures
        else:
            expected_pressures = self._estimate_expected_pressures(
                graph, nodes, source_ids
            )
        
        # Step 2: Calculate anomaly scores for all nodes
        anomaly_scores = self._calculate_anomaly_scores(
            graph, nodes, simulation_state, expected_pressures, source_ids
        )
        
        # Step 3: Identify candidate leak locations
        candidates = self._identify_candidates(anomaly_scores)
        
        # Step 4: Cluster nearby anomalies to find leak epicenters
        leak_clusters = self._cluster_anomalies(graph, candidates, node_dict)
        
        # Step 5: Trace propagation to refine leak locations
        refined_leaks = self._trace_leak_sources(
            graph, leak_clusters, simulation_state, node_dict, source_ids
        )
        
        # Step 6: Calculate confidence scores
        confidence_scores = self._calculate_confidence(
            refined_leaks, anomaly_scores, simulation_state
        )
        
        # Step 7: Identify all affected nodes
        affected_nodes = self._find_affected_nodes(
            graph, refined_leaks, simulation_state, source_ids
        )
        
        # Step 8: Generate recommendations
        recommendations = self._generate_recommendations(
            refined_leaks, affected_nodes, node_dict
        )
        
        # Compile results
        detected_leaks = []
        for leak_info in refined_leaks:
            node_id = leak_info['node_id']
            detected_leaks.append({
                'node_id': node_id,
                'node_name': node_dict[node_id].name,
                'node_type': node_dict[node_id].node_type,
                'location': (node_dict[node_id].x, node_dict[node_id].y),
                'confidence': confidence_scores.get(node_id, 0),
                'estimated_severity': leak_info.get('severity', 'unknown'),
                'pressure_deficit': leak_info.get('pressure_deficit', 0),
                'affected_downstream': leak_info.get('affected_downstream', 0)
            })
        
        # Sort by confidence
        detected_leaks.sort(key=lambda x: x['confidence'], reverse=True)
        
        return LeakDetectionResult(
            detected_leaks=detected_leaks,
            affected_nodes=affected_nodes,
            confidence_scores=confidence_scores,
            analysis_details={
                'total_anomalies': len(candidates),
                'clusters_found': len(leak_clusters),
                'anomaly_scores': {a.node_id: a.score for a in anomaly_scores},
                'pressure_deficits': {
                    a.node_id: a.pressure_deficit for a in anomaly_scores
                    if a.pressure_deficit > 0
                }
            },
            recommendations=recommendations
        )
    
    def _estimate_expected_pressures(
        self,
        graph: nx.Graph,
        nodes: List,
        source_ids: Set[int]
    ) -> Dict[int, float]:
        """
        Estimate expected pressures based on network topology.
        Uses shortest path distance from sources.
        """
        expected = {}
        
        # Calculate shortest paths from all sources
        min_distances = {}
        for source_id in source_ids:
            distances = nx.single_source_shortest_path_length(graph, source_id)
            for node_id, dist in distances.items():
                if node_id not in min_distances:
                    min_distances[node_id] = dist
                else:
                    min_distances[node_id] = min(min_distances[node_id], dist)
        
        # Estimate pressure based on distance
        max_distance = max(min_distances.values()) if min_distances else 1
        
        for node in nodes:
            if node.id in source_ids:
                expected[node.id] = self.source_pressure
            else:
                dist = min_distances.get(node.id, max_distance)
                # Pressure drops with distance (simplified model)
                drop_factor = 0.05 * dist  # 5% drop per hop
                expected[node.id] = self.source_pressure * (1 - min(drop_factor, 0.7))
        
        return expected
    
    def _calculate_anomaly_scores(
        self,
        graph: nx.Graph,
        nodes: List,
        state,
        expected_pressures: Dict[int, float],
        source_ids: Set[int]
    ) -> List[AnomalyScore]:
        """Calculate anomaly scores for all nodes."""
        scores = []
        
        # Find nodes with active leaks (they will have dramatically low pressure)
        all_pressures = [
            state.node_pressures.get(n.id, 0) 
            for n in nodes if n.id not in source_ids
        ]
        
        if all_pressures:
            mean_pressure = np.mean(all_pressures)
            std_pressure = np.std(all_pressures) if len(all_pressures) > 1 else 1
        else:
            mean_pressure = self.source_pressure * 0.5
            std_pressure = 50
        
        for node in nodes:
            if node.id in source_ids:
                continue
            
            actual = state.node_pressures.get(node.id, 0)
            expected = expected_pressures.get(node.id, self.source_pressure * 0.8)
            
            # Pressure deficit
            deficit = expected - actual
            deficit_ratio = deficit / expected if expected > 0 else 0
            
            # Z-score for outlier detection
            z_score = (mean_pressure - actual) / std_pressure if std_pressure > 0 else 0
            
            # Neighbor analysis
            neighbor_pressures = [
                state.node_pressures.get(n, 0)
                for n in graph.neighbors(node.id)
            ]
            neighbor_avg = np.mean(neighbor_pressures) if neighbor_pressures else 0
            neighbor_max = max(neighbor_pressures) if neighbor_pressures else 0
            
            # Pressure gradient from neighbors (high gradient = likely leak source)
            pressure_gradient = neighbor_max - actual
            
            # Is this an isolated drop? (neighbors have higher pressure)
            is_isolated = (
                neighbor_avg > actual * 1.5 and
                deficit_ratio > self.deficit_ratio_threshold
            )
            
            # Check if this node has anomalously low pressure compared to surroundings
            is_pressure_sink = (
                neighbor_max > actual * 2 and actual < mean_pressure * 0.5
            )
            
            # Count downstream affected nodes (simplified)
            downstream = sum(
                1 for n in graph.neighbors(node.id)
                if state.node_pressures.get(n, 0) < actual
            )
            
            # Combined score with emphasis on pressure sinks
            score = 0
            if deficit > self.pressure_deficit_threshold:
                score += 0.2
            if deficit_ratio > self.deficit_ratio_threshold:
                score += 0.2
            if is_isolated:
                score += 0.2
            if is_pressure_sink:
                score += 0.3
            if z_score > 2:  # Statistical outlier
                score += 0.2
            if pressure_gradient > 100:  # Large gradient indicates leak source
                score += 0.2
            if downstream > 0:
                score += 0.1 * min(downstream, 5) / 5
            
            scores.append(AnomalyScore(
                node_id=node.id,
                pressure_deficit=deficit,
                deficit_ratio=deficit_ratio,
                neighbor_avg_pressure=neighbor_avg,
                is_isolated_drop=is_isolated or is_pressure_sink,
                downstream_affected=downstream,
                score=min(score, 1.0)
            ))
        
        return scores
    
    def _identify_candidates(
        self,
        anomaly_scores: List[AnomalyScore]
    ) -> List[AnomalyScore]:
        """Identify candidate leak locations based on anomaly scores."""
        # First, find nodes with extremely low pressure (likely leak locations)
        severe_candidates = [
            a for a in anomaly_scores
            if a.pressure_deficit > self.source_pressure * 0.6  # More than 60% deficit
            or a.is_isolated_drop
        ]
        
        # Then add moderate anomalies
        moderate_candidates = [
            a for a in anomaly_scores
            if a.score >= self.min_confidence_threshold
            or a.deficit_ratio > self.deficit_ratio_threshold * 1.5
        ]
        
        # Combine and deduplicate
        seen_ids = set()
        candidates = []
        for a in severe_candidates + moderate_candidates:
            if a.node_id not in seen_ids:
                candidates.append(a)
                seen_ids.add(a.node_id)
        
        # Sort by pressure deficit (most severe first), then by score
        candidates.sort(key=lambda x: (x.pressure_deficit, x.score), reverse=True)
        
        return candidates
    
    def _cluster_anomalies(
        self,
        graph: nx.Graph,
        candidates: List[AnomalyScore],
        node_dict: Dict
    ) -> List[List[int]]:
        """
        Cluster nearby anomalies to identify leak epicenters.
        Uses graph distance for clustering.
        """
        if not candidates:
            return []
        
        candidate_ids = {c.node_id for c in candidates}
        clusters = []
        visited = set()
        
        for candidate in candidates:
            if candidate.node_id in visited:
                continue
            
            # BFS to find connected anomalies
            cluster = []
            queue = [candidate.node_id]
            
            while queue:
                node_id = queue.pop(0)
                if node_id in visited:
                    continue
                
                visited.add(node_id)
                
                if node_id in candidate_ids:
                    cluster.append(node_id)
                    
                    # Add neighbors to queue (limited depth)
                    for neighbor in graph.neighbors(node_id):
                        if neighbor not in visited:
                            queue.append(neighbor)
            
            if cluster:
                clusters.append(cluster)
        
        return clusters
    
    def _trace_leak_sources(
        self,
        graph: nx.Graph,
        clusters: List[List[int]],
        state,
        node_dict: Dict,
        source_ids: Set[int]
    ) -> List[Dict]:
        """
        Trace back from clusters to find likely leak source.
        The leak is likely at the node with lowest pressure that
        has neighbors with significantly higher pressure.
        """
        leak_sources = []
        
        for cluster in clusters:
            if not cluster:
                continue
            
            # Find node with lowest pressure in cluster - this is likely the leak
            best_candidate = min(
                cluster,
                key=lambda x: state.node_pressures.get(x, float('inf'))
            )
            
            # Calculate maximum pressure gradient (difference from highest neighbor)
            best_pressure = state.node_pressures.get(best_candidate, 0)
            
            neighbor_pressures = [
                state.node_pressures.get(n, 0)
                for n in graph.neighbors(best_candidate)
            ]
            max_neighbor = max(neighbor_pressures) if neighbor_pressures else best_pressure
            gradient = max_neighbor - best_pressure
            
            # Determine severity based on pressure at node
            node_pressure = state.node_pressures.get(best_candidate, 0)
            if node_pressure < 10:
                severity = "critical"
            elif node_pressure < 50:
                severity = "severe"
            elif node_pressure < 150:
                severity = "moderate"
            else:
                severity = "minor"
            
            leak_sources.append({
                'node_id': best_candidate,
                'cluster_size': len(cluster),
                'severity': severity,
                'pressure_deficit': self.source_pressure * 0.8 - node_pressure,
                'affected_downstream': len(cluster) - 1,
                'pressure_gradient': gradient
            })
        
        # Sort by severity (lowest pressure first)
        leak_sources.sort(
            key=lambda x: state.node_pressures.get(x['node_id'], float('inf'))
        )
        
        return leak_sources
    
    def _calculate_confidence(
        self,
        leak_sources: List[Dict],
        anomaly_scores: List[AnomalyScore],
        state
    ) -> Dict[int, float]:
        """Calculate confidence scores for detected leaks."""
        confidence = {}
        score_dict = {a.node_id: a for a in anomaly_scores}
        
        for leak in leak_sources:
            node_id = leak['node_id']
            
            # Base confidence from anomaly score
            anomaly = score_dict.get(node_id)
            if anomaly:
                base_confidence = anomaly.score
            else:
                base_confidence = 0.5
            
            # Boost for isolated drops
            if anomaly and anomaly.is_isolated_drop:
                base_confidence += 0.2
            
            # Boost for larger clusters (more evidence)
            cluster_boost = min(leak['cluster_size'] * 0.05, 0.2)
            base_confidence += cluster_boost
            
            # Boost for severe pressure drops
            if leak['severity'] in ['critical', 'severe']:
                base_confidence += 0.1
            
            confidence[node_id] = min(base_confidence, 1.0)
        
        return confidence
    
    def _find_affected_nodes(
        self,
        graph: nx.Graph,
        leak_sources: List[Dict],
        state,
        source_ids: Set[int]
    ) -> List[int]:
        """Find all nodes affected by the detected leaks."""
        affected = set()
        
        # Low pressure threshold
        threshold = self.source_pressure * 0.5
        
        for node_id, pressure in state.node_pressures.items():
            if node_id in source_ids:
                continue
            if pressure < threshold:
                affected.add(node_id)
        
        return list(affected)
    
    def _generate_recommendations(
        self,
        leak_sources: List[Dict],
        affected_nodes: List[int],
        node_dict: Dict
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if not leak_sources:
            recommendations.append("✓ No significant leaks detected in the network.")
            return recommendations
        
        # Priority actions
        critical_leaks = [l for l in leak_sources if l['severity'] == 'critical']
        severe_leaks = [l for l in leak_sources if l['severity'] == 'severe']
        
        if critical_leaks:
            recommendations.append(
                f"🚨 CRITICAL: {len(critical_leaks)} critical leak(s) detected. "
                "Immediate shutdown and repair required."
            )
            for leak in critical_leaks:
                node = node_dict[leak['node_id']]
                recommendations.append(
                    f"   → Dispatch emergency crew to {node.name} "
                    f"(Node #{leak['node_id']})"
                )
        
        if severe_leaks:
            recommendations.append(
                f"⚠️ WARNING: {len(severe_leaks)} severe leak(s) detected. "
                "Priority repair needed within 2 hours."
            )
        
        if affected_nodes:
            recommendations.append(
                f"📊 {len(affected_nodes)} nodes experiencing low pressure. "
                "Consider temporary pressure boost from sources."
            )
        
        # General recommendations
        if len(leak_sources) > 3:
            recommendations.append(
                "🔧 Multiple leaks detected. Consider systematic pipeline inspection."
            )
        
        return recommendations
    
    def quick_scan(
        self,
        state,
        nodes: List,
        threshold_ratio: float = 0.4
    ) -> List[int]:
        """
        Quick scan for obvious pressure anomalies.
        Returns list of node IDs with significant pressure drops.
        """
        source_ids = {n.id for n in nodes if n.node_type == "source"}
        anomalies = []
        
        for node in nodes:
            if node.id in source_ids:
                continue
            
            pressure = state.node_pressures.get(node.id, 0)
            if pressure < self.source_pressure * threshold_ratio:
                anomalies.append(node.id)
        
        return anomalies


def detect_leaks(
    graph: nx.Graph,
    nodes: List,
    pipes: List,
    simulation_state,
    pressure_threshold: float = 50.0,
    confidence_threshold: float = 0.5
) -> LeakDetectionResult:
    """
    Convenience function for leak detection.
    
    Args:
        graph: NetworkX graph
        nodes: List of GasNode objects
        pipes: List of GasPipe objects
        simulation_state: Current SimulationState
        pressure_threshold: Minimum pressure deficit to flag (kPa)
        confidence_threshold: Minimum confidence to report
        
    Returns:
        LeakDetectionResult
    """
    detector = LeakDetector(
        pressure_deficit_threshold=pressure_threshold,
        min_confidence_threshold=confidence_threshold
    )
    
    return detector.analyze_network(graph, nodes, pipes, simulation_state)


if __name__ == "__main__":
    # Test leak detection
    from city_gen import CityNetworkGenerator
    from physics import PhysicsEngine, LeakSimulator
    
    # Generate network
    generator = CityNetworkGenerator(seed=42)
    nodes, pipes, G = generator.generate_network(n_nodes=100)
    
    # Simulate with leaks
    engine = PhysicsEngine()
    leaks = LeakSimulator.create_random_leaks(nodes, n_leaks=2, seed=123)
    state = engine.simulate_network(G, nodes, pipes, leaks=leaks)
    
    print(f"Actual leaks at nodes: {list(leaks.keys())}")
    
    # Detect leaks
    result = detect_leaks(G, nodes, pipes, state)
    
    print(f"\nDetected {len(result.detected_leaks)} potential leak(s):")
    for leak in result.detected_leaks:
        print(f"  Node {leak['node_id']} ({leak['node_name']}): "
              f"Confidence {leak['confidence']:.0%}, Severity: {leak['estimated_severity']}")
    
    print(f"\nAffected nodes: {len(result.affected_nodes)}")
    print("\nRecommendations:")
    for rec in result.recommendations:
        print(f"  {rec}")
