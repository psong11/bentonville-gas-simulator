/**
 * PressureHistogram Component
 * Distribution of node pressures with colored bins by status
 */

import { useMemo } from 'react';
import Plot from 'react-plotly.js';
import type { SimulationState } from '../types';
import { getPressureStatus, PRESSURE_COLORS } from '../types';

interface PressureHistogramProps {
  simulationState: SimulationState;
  sourcePressure: number;
}

export function PressureHistogram({
  simulationState,
  sourcePressure,
}: PressureHistogramProps) {
  // Categorize pressures by status
  const pressureData = useMemo(() => {
    const pressures = Object.values(simulationState.node_pressures);
    
    const categories: Record<string, number[]> = {
      critical: [],
      warning: [],
      normal: [],
      over: [],
    };

    pressures.forEach(pressure => {
      const status = getPressureStatus(pressure, sourcePressure);
      categories[status].push(pressure);
    });

    return categories;
  }, [simulationState.node_pressures, sourcePressure]);

  // Create histogram traces for each category
  const traces = useMemo(() => {
    return [
      {
        x: pressureData.critical,
        name: 'Critical (<70%)',
        type: 'histogram' as const,
        marker: { color: PRESSURE_COLORS.critical },
        opacity: 0.7,
      },
      {
        x: pressureData.warning,
        name: 'Warning (70-85%)',
        type: 'histogram' as const,
        marker: { color: PRESSURE_COLORS.warning },
        opacity: 0.7,
      },
      {
        x: pressureData.normal,
        name: 'Normal (85-105%)',
        type: 'histogram' as const,
        marker: { color: PRESSURE_COLORS.normal },
        opacity: 0.7,
      },
      {
        x: pressureData.over,
        name: 'Over Pressure (>105%)',
        type: 'histogram' as const,
        marker: { color: PRESSURE_COLORS.over },
        opacity: 0.7,
      },
    ];
  }, [pressureData]);

  // Calculate statistics
  const stats = useMemo(() => {
    const pressures = Object.values(simulationState.node_pressures);
    if (pressures.length === 0) return null;
    
    const sorted = [...pressures].sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const mean = pressures.reduce((a, b) => a + b, 0) / pressures.length;
    const median = sorted[Math.floor(sorted.length / 2)];
    
    return { min, max, mean, median };
  }, [simulationState.node_pressures]);

  return (
    <div className="card">
      <h3 className="font-semibold mb-2">Pressure Distribution</h3>
      
      {stats && (
        <div className="grid grid-cols-4 gap-2 text-sm mb-4">
          <div className="text-center">
            <div className="text-slate-500">Min</div>
            <div className="font-mono">{stats.min.toFixed(1)} kPa</div>
          </div>
          <div className="text-center">
            <div className="text-slate-500">Max</div>
            <div className="font-mono">{stats.max.toFixed(1)} kPa</div>
          </div>
          <div className="text-center">
            <div className="text-slate-500">Mean</div>
            <div className="font-mono">{stats.mean.toFixed(1)} kPa</div>
          </div>
          <div className="text-center">
            <div className="text-slate-500">Median</div>
            <div className="font-mono">{stats.median.toFixed(1)} kPa</div>
          </div>
        </div>
      )}

      <Plot
        data={traces}
        layout={{
          barmode: 'stack',
          margin: { l: 50, r: 20, t: 10, b: 80 },
          xaxis: {
            title: { text: 'Pressure (kPa)' },
          },
          yaxis: {
            title: { text: 'Node Count' },
          },
          height: 280,
          showlegend: true,
          legend: {
            orientation: 'h' as const,
            y: -0.35,
            x: 0.5,
            xanchor: 'center' as const,
          },
        }}
        config={{
          displayModeBar: false,
        }}
        style={{ width: '100%' }}
        useResizeHandler
      />

      {/* Status summary */}
      <div className="grid grid-cols-4 gap-2 mt-4">
        <div className="text-center">
          <span className="badge badge-critical">
            {pressureData.critical.length} Critical
          </span>
        </div>
        <div className="text-center">
          <span className="badge badge-warning">
            {pressureData.warning.length} Warning
          </span>
        </div>
        <div className="text-center">
          <span className="badge badge-success">
            {pressureData.normal.length} Normal
          </span>
        </div>
        <div className="text-center">
          <span className="badge bg-purple-100 text-purple-800">
            {pressureData.over.length} Over
          </span>
        </div>
      </div>
    </div>
  );
}
