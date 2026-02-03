/**
 * FlowChart Component
 * Bar chart showing top 20 pipes by flow rate with click-to-select
 */

import { useMemo, useCallback } from 'react';
import Plot from 'react-plotly.js';
import type { PlotMouseEvent } from 'plotly.js';
import type { Network, SimulationState, Node } from '../types';

interface FlowChartProps {
  network: Network;
  simulationState: SimulationState;
  selectedPipeId: number | null;
  onPipeSelect: (pipeId: number | null) => void;
}

export function FlowChart({
  network,
  simulationState,
  selectedPipeId,
  onPipeSelect,
}: FlowChartProps) {
  // Build node lookup
  const nodeDict = useMemo(() => {
    const dict: Record<number, Node> = {};
    network.nodes.forEach(node => {
      dict[node.id] = node;
    });
    return dict;
  }, [network.nodes]);

  // Get top 20 pipes by flow rate
  const topPipes = useMemo(() => {
    const pipesWithFlow = network.pipes.map(pipe => ({
      pipe,
      flowRate: Math.abs(simulationState.pipe_flow_rates[pipe.id] ?? 0),
    }));

    return pipesWithFlow
      .sort((a, b) => b.flowRate - a.flowRate)
      .slice(0, 20);
  }, [network.pipes, simulationState.pipe_flow_rates]);

  // Create chart data
  const chartData = useMemo(() => {
    const labels = topPipes.map(({ pipe }) => {
      const source = nodeDict[pipe.source_id];
      const target = nodeDict[pipe.target_id];
      return source && target 
        ? `${source.name} → ${target.name}`
        : `Pipe ${pipe.id}`;
    });

    const values = topPipes.map(({ flowRate }) => flowRate);
    const pipeIds = topPipes.map(({ pipe }) => pipe.id);

    // Color bars - highlight selected
    const colors = pipeIds.map(id => 
      id === selectedPipeId ? '#ef4444' : '#3b82f6'
    );

    return {
      type: 'bar' as const,
      x: values,
      y: labels,
      orientation: 'h' as const,
      marker: {
        color: colors,
      },
      customdata: pipeIds,
      hovertemplate: '<b>%{y}</b><br>Flow: %{x:.1f} m³/h<extra></extra>',
    };
  }, [topPipes, nodeDict, selectedPipeId]);

  // Handle bar click
  const handleClick = useCallback((event: PlotMouseEvent) => {
    const point = event.points[0];
    if (point && 'customdata' in point) {
      const pipeId = point.customdata as number;
      // Toggle selection - if already selected, deselect
      onPipeSelect(pipeId === selectedPipeId ? null : pipeId);
    }
  }, [onPipeSelect, selectedPipeId]);

  return (
    <div className="card">
      <h3 className="font-semibold mb-2">Top 20 Pipes by Flow Rate</h3>
      <p className="text-sm text-slate-500 mb-4">Click a bar to highlight on map</p>
      <Plot
        data={[chartData]}
        layout={{
          margin: { l: 150, r: 20, t: 10, b: 40 },
          xaxis: {
            title: { text: 'Flow Rate (m³/h)' },
          },
          yaxis: {
            autorange: 'reversed' as const,
            tickfont: { size: 10 },
          },
          height: 450,
          hovermode: 'closest',
        }}
        config={{
          displayModeBar: false,
        }}
        style={{ width: '100%' }}
        onClick={handleClick}
        useResizeHandler
      />
    </div>
  );
}
