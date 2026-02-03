/**
 * NetworkMap Component
 * Renders the gas distribution network using Plotly Scattermapbox
 */

import { useMemo, useCallback } from 'react';
import Plot from 'react-plotly.js';
import type { PlotMouseEvent } from 'plotly.js';
import type { Network, SimulationState, Node } from '../types';
import { getPressureStatus, getPressureColor } from '../types';

interface NetworkMapProps {
  network: Network;
  simulationState: SimulationState;
  sourcePressure: number;
  selectedPipeId: number | null;
  onPipeSelect: (pipeId: number | null) => void;
  activeLeaks: number[];
}

export function NetworkMap({
  network,
  simulationState,
  sourcePressure,
  selectedPipeId,
  onPipeSelect,
  activeLeaks,
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
    const colors = network.nodes.map(node => {
      // Check if node has active leak
      if (activeLeaks.includes(node.id)) return '#ef4444'; // red for leak
      
      // Color by pressure status
      const pressure = simulationState.node_pressures[node.id] ?? 0;
      const status = getPressureStatus(pressure, sourcePressure);
      return getPressureColor(status);
    });

    const sizes = network.nodes.map(node => {
      if (node.node_type === 'source') return 20;
      if (node.node_type === 'industrial') return 14;
      if (node.node_type === 'commercial') return 12;
      return 10;
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
    };
  }, [network.nodes, simulationState, sourcePressure, activeLeaks]);

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

  return (
    <Plot
      data={[...pipeTraces, nodeTrace] as Plotly.Data[]}
      layout={{
        mapbox: {
          style: 'carto-positron',
          center: center,
          zoom: 12,
        },
        margin: { l: 0, r: 0, t: 0, b: 0 },
        showlegend: false,
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
