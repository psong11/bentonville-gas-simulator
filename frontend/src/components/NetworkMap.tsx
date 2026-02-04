/**
 * NetworkMap Component
 * Renders the gas distribution network using Plotly Scattermapbox
 */

import { useMemo, useCallback } from 'react';
import Plot from 'react-plotly.js';
import type { PlotMouseEvent } from 'plotly.js';
import type { Network, SimulationState, Node, LeakDetectionResult } from '../types';
import { getPressureStatus, getPressureColor } from '../types';

interface NetworkMapProps {
  network: Network;
  simulationState: SimulationState;
  sourcePressure: number;
  selectedPipeId: number | null;
  onPipeSelect: (pipeId: number | null) => void;
  activeLeaks: number[];
  detectionResult: LeakDetectionResult | null;
  sensorNodes: number[];
}

export function NetworkMap({
  network,
  simulationState,
  sourcePressure,
  selectedPipeId,
  onPipeSelect,
  activeLeaks,
  detectionResult,
  sensorNodes,
}: NetworkMapProps) {
  // Build node lookup
  const nodeDict = useMemo(() => {
    const dict: Record<number, Node> = {};
    network.nodes.forEach(node => {
      dict[node.id] = node;
    });
    return dict;
  }, [network.nodes]);

  // Calculate center of network
  const center = useMemo(() => {
    const xs = network.nodes.map(n => n.x);
    const ys = network.nodes.map(n => n.y);
    return {
      lon: (Math.min(...xs) + Math.max(...xs)) / 2,
      lat: (Math.min(...ys) + Math.max(...ys)) / 2,
    };
  }, [network.nodes]);

  // Create node trace
  const nodeTrace = useMemo(() => {
    // Check if we have simulation data yet
    const hasSimulationData = Object.keys(simulationState.node_pressures).length > 0;
    
    const colors = network.nodes.map(node => {
      // Check if node has active leak
      if (activeLeaks.includes(node.id)) return '#ef4444'; // red for leak
      
      // If no simulation data yet, use a neutral blue color for visibility
      if (!hasSimulationData) return '#3b82f6'; // blue (loading state)
      
      // Color by pressure status
      const pressure = simulationState.node_pressures[node.id] ?? 0;
      const status = getPressureStatus(pressure, sourcePressure);
      return getPressureColor(status);
    });

    const sizes = network.nodes.map(node => {
      if (node.node_type === 'source') return 28;
      if (node.node_type === 'industrial') return 20;
      if (node.node_type === 'commercial') return 16;
      return 14;
    });

    const symbols = network.nodes.map(node => {
      if (activeLeaks.includes(node.id)) return 'x';
      if (node.node_type === 'source') return 'star';
      return 'circle';
    });

    const hoverText = network.nodes.map(node => {
      const pressure = simulationState.node_pressures[node.id] ?? 0;
      const demand = simulationState.node_actual_demand[node.id] ?? 0;
      const status = getPressureStatus(pressure, sourcePressure);
      const leakText = activeLeaks.includes(node.id) ? '<br>⚠️ LEAK ACTIVE' : '';
      
      return `<b>${node.name}</b><br>` +
        `Type: ${node.node_type}<br>` +
        `Pressure: ${pressure.toFixed(1)} kPa<br>` +
        `Demand: ${demand.toFixed(1)} m³/h<br>` +
        `Status: ${status}${leakText}`;
    });

    return {
      type: 'scattermapbox' as const,
      mode: 'markers' as const,
      lon: network.nodes.map(n => n.x),
      lat: network.nodes.map(n => n.y),
      marker: {
        size: sizes,
        color: colors,
        symbol: symbols,
      },
      text: network.nodes.map(n => n.name),
      hovertemplate: hoverText.map(t => t + '<extra></extra>'),
      name: 'Nodes',
      showlegend: false,
    };
  }, [network.nodes, simulationState, sourcePressure, activeLeaks]);

  // Create sensor trace (manually placed sensors before detection)
  const sensorTrace = useMemo(() => {
    if (sensorNodes.length === 0) return null;
    
    const sensorNodeData = sensorNodes
      .map(id => network.nodes.find(n => n.id === id))
      .filter((n): n is Node => n !== undefined);
    
    if (sensorNodeData.length === 0) return null;

    return {
      type: 'scattermapbox' as const,
      mode: 'markers' as const,
      lon: sensorNodeData.map(n => n.x),
      lat: sensorNodeData.map(n => n.y),
      marker: {
        size: 18,
        color: '#3b82f6', // blue
        symbol: 'triangle',
      },
      hovertemplate: sensorNodeData.map(n => 
        `<b>📡 Sensor</b><br>${n.name}<extra></extra>`
      ),
      name: 'Sensors',
      showlegend: true,
    };
  }, [sensorNodes, network.nodes]);

  // Create detection result traces
  const detectionTraces = useMemo(() => {
    if (!detectionResult) return [];
    
    const traces: Plotly.Data[] = [];
    const actualLeakSet = new Set(activeLeaks);
    
    // Detected leaks (true positives) - big green circles
    const truePositives = detectionResult.detected_leaks.filter(id => actualLeakSet.has(id));
    if (truePositives.length > 0) {
      const tpNodes = truePositives
        .map(id => network.nodes.find(n => n.id === id))
        .filter((n): n is Node => n !== undefined);
      
      traces.push({
        type: 'scattermapbox' as const,
        mode: 'markers' as const,
        lon: tpNodes.map(n => n.x),
        lat: tpNodes.map(n => n.y),
        marker: {
          size: 24,
          color: '#22c55e', // green
          symbol: 'circle',
        },
        hovertemplate: tpNodes.map(n => 
          `<b>✅ Leak Detected</b><br>${n.name}<extra></extra>`
        ),
        name: 'Detected Leaks',
        showlegend: true,
      });
    }
    
    // False positives - hollow red circles
    const falsePositives = detectionResult.detected_leaks.filter(id => !actualLeakSet.has(id));
    if (falsePositives.length > 0) {
      const fpNodes = falsePositives
        .map(id => network.nodes.find(n => n.id === id))
        .filter((n): n is Node => n !== undefined);
      
      traces.push({
        type: 'scattermapbox' as const,
        mode: 'markers' as const,
        lon: fpNodes.map(n => n.x),
        lat: fpNodes.map(n => n.y),
        marker: {
          size: 20,
          color: '#ef4444', // red
          symbol: 'circle-open',
        },
        hovertemplate: fpNodes.map(n => 
          `<b>❌ False Positive</b><br>${n.name}<extra></extra>`
        ),
        name: 'False Positives',
        showlegend: true,
      });
    }
    
    // Sensor placements from detection result (if different from manually placed)
    const resultSensors = detectionResult.sensor_placements;
    if (resultSensors.length > 0) {
      const sensorNodeData = resultSensors
        .map(id => network.nodes.find(n => n.id === id))
        .filter((n): n is Node => n !== undefined);
      
      traces.push({
        type: 'scattermapbox' as const,
        mode: 'markers' as const,
        lon: sensorNodeData.map(n => n.x),
        lat: sensorNodeData.map(n => n.y),
        marker: {
          size: 18,
          color: '#3b82f6', // blue
          symbol: 'triangle',
        },
        hovertemplate: sensorNodeData.map(n => 
          `<b>📡 Sensor</b><br>${n.name}<extra></extra>`
        ),
        name: 'Sensors',
        showlegend: true,
      });
    }
    
    return traces;
  }, [detectionResult, activeLeaks, network.nodes]);

  // Create pipe traces
  const pipeTraces = useMemo(() => {
    return network.pipes.map(pipe => {
      const sourceNode = nodeDict[pipe.source_id];
      const targetNode = nodeDict[pipe.target_id];
      
      if (!sourceNode || !targetNode) return null;

      const flowRate = Math.abs(simulationState.pipe_flow_rates[pipe.id] ?? 0);
      const isSelected = pipe.id === selectedPipeId;
      
      // Width based on flow rate (1-6 range)
      const width = Math.min(1 + flowRate / 100, 6);
      
      // Color based on flow rate
      let color = '#6b7280'; // gray default
      if (flowRate > 200) color = '#3b82f6'; // blue high
      else if (flowRate > 50) color = '#22c55e'; // green medium
      else if (flowRate > 10) color = '#eab308'; // yellow low

      // Override for selected pipe
      if (isSelected) {
        color = '#ef4444'; // red
      }

      return {
        type: 'scattermapbox' as const,
        mode: 'lines' as const,
        lon: [sourceNode.x, targetNode.x],
        lat: [sourceNode.y, targetNode.y],
        line: {
          width: isSelected ? width + 3 : width,
          color,
        },
        hoverinfo: 'text' as const,
        hovertemplate: 
          `<b>Pipe #${pipe.id}</b><br>` +
          `${sourceNode.name} → ${targetNode.name}<br>` +
          `Flow: ${flowRate.toFixed(1)} m³/h<br>` +
          `Length: ${pipe.length.toFixed(0)}m<br>` +
          `Diameter: ${(pipe.diameter * 1000).toFixed(0)}mm` +
          `<extra></extra>`,
        name: `Pipe ${pipe.id}`,
        customdata: [{ pipeId: pipe.id }],
        showlegend: false,
      };
    }).filter(Boolean);
  }, [network.pipes, nodeDict, simulationState, selectedPipeId]);

  // Handle click on pipe
  const handleClick = useCallback((event: PlotMouseEvent) => {
    const point = event.points[0];
    if (point && point.customdata) {
      const customData = point.customdata as unknown as { pipeId: number };
      if (customData?.pipeId !== undefined) {
        onPipeSelect(customData.pipeId);
      }
    }
  }, [onPipeSelect]);

  // Build the complete data array
  const plotData = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const data: any[] = [...pipeTraces.filter(Boolean), nodeTrace];
    
    // Add sensor trace (if manually placed before detection)
    if (sensorTrace && !detectionResult) {
      data.push(sensorTrace);
    }
    
    // Add detection result traces
    if (detectionResult) {
      data.push(...detectionTraces);
    }
    
    return data;
  }, [pipeTraces, nodeTrace, sensorTrace, detectionResult, detectionTraces]);

  // Determine if legend should be shown
  const showLegend = Boolean((sensorTrace && !detectionResult) || (detectionResult && detectionTraces.length > 0));

  return (
    <Plot
      data={plotData}
      layout={{
        mapbox: {
          style: 'carto-positron',
          center: center,
          zoom: 12,
        },
        margin: { l: 0, r: 0, t: 0, b: 0 },
        showlegend: showLegend,
        legend: {
          x: 0,
          y: 1,
          bgcolor: 'rgba(255,255,255,0.8)',
          bordercolor: '#e2e8f0',
          borderwidth: 1,
        },
        hovermode: 'closest',
      }}
      config={{
        mapboxAccessToken: '', // Using free Carto style, no token needed
        displayModeBar: true,
        modeBarButtonsToRemove: ['select2d', 'lasso2d'],
      }}
      style={{ width: '100%', height: '500px' }}
      onClick={handleClick}
      useResizeHandler
    />
  );
}
