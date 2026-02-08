import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PressureHistogram } from '../PressureHistogram';
import { mockSimulationState } from '../../test/fixtures';

// Mock react-plotly.js
vi.mock('react-plotly.js', () => ({
  __esModule: true,
  default: (props: { data: unknown[] }) => (
    <div data-testid="plotly-histogram" data-traces={JSON.stringify(props.data)} />
  ),
}));

describe('PressureHistogram', () => {
  const sourcePressure = 600;

  it('renders chart heading', () => {
    render(
      <PressureHistogram
        simulationState={mockSimulationState}
        sourcePressure={sourcePressure}
      />
    );
    expect(screen.getByText('Pressure Distribution')).toBeInTheDocument();
  });

  it('renders the Plotly histogram', () => {
    render(
      <PressureHistogram
        simulationState={mockSimulationState}
        sourcePressure={sourcePressure}
      />
    );
    expect(screen.getByTestId('plotly-histogram')).toBeInTheDocument();
  });

  it('creates four histogram traces for pressure categories', () => {
    render(
      <PressureHistogram
        simulationState={mockSimulationState}
        sourcePressure={sourcePressure}
      />
    );
    const chart = screen.getByTestId('plotly-histogram');
    const traces = JSON.parse(chart.getAttribute('data-traces') || '[]');
    expect(traces).toHaveLength(4); // critical, warning, normal, over
  });

  it('displays pressure statistics', () => {
    render(
      <PressureHistogram
        simulationState={mockSimulationState}
        sourcePressure={sourcePressure}
      />
    );

    // Min, Max, Mean, Median labels should be present
    expect(screen.getByText('Min')).toBeInTheDocument();
    expect(screen.getByText('Max')).toBeInTheDocument();
    expect(screen.getByText('Mean')).toBeInTheDocument();
    expect(screen.getByText('Median')).toBeInTheDocument();
  });

  it('calculates correct min/max from pressures', () => {
    render(
      <PressureHistogram
        simulationState={mockSimulationState}
        sourcePressure={sourcePressure}
      />
    );

    const pressures = Object.values(mockSimulationState.node_pressures);
    const min = Math.min(...pressures);
    const max = Math.max(...pressures);

    expect(screen.getByText(`${min.toFixed(1)} kPa`)).toBeInTheDocument();
    expect(screen.getByText(`${max.toFixed(1)} kPa`)).toBeInTheDocument();
  });

  it('displays status summary badges', () => {
    render(
      <PressureHistogram
        simulationState={mockSimulationState}
        sourcePressure={sourcePressure}
      />
    );

    // Should show category count badges (use getAllBy since text appears in description too)
    expect(screen.getAllByText(/Critical/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Warning/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Normal/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Over/).length).toBeGreaterThanOrEqual(1);
  });

  it('categorizes all pressures as normal when within 85-105% of source', () => {
    const normalState = {
      ...mockSimulationState,
      // All pressures between 85% (510) and 105% (630) of source=600
      node_pressures: { 0: 600, 1: 570, 2: 540, 3: 580, 4: 520 },
    };

    render(
      <PressureHistogram simulationState={normalState} sourcePressure={sourcePressure} />
    );

    const chart = screen.getByTestId('plotly-histogram');
    const traces = JSON.parse(chart.getAttribute('data-traces') || '[]');

    // "normal" trace (index 2) should contain all pressures
    const normalTrace = traces[2]; // normal is third
    expect(normalTrace.x.length).toBe(5);
  });

  it('handles empty simulation state', () => {
    const emptyState = {
      node_pressures: {},
      node_actual_demand: {},
      pipe_flow_rates: {},
      pipe_velocities: {},
      pipe_pressure_drops: {},
      pipe_reynolds: {},
      active_leaks: {},
      warnings: [],
    };

    render(
      <PressureHistogram simulationState={emptyState} sourcePressure={600} />
    );

    // Should still render without crashing
    expect(screen.getByText('Pressure Distribution')).toBeInTheDocument();
  });
});
