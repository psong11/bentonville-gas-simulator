import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBar } from '../StatusBar';
import { mockNetwork, mockSimulationState } from '../../test/fixtures';

describe('StatusBar', () => {
  it('renders node and pipe counts', () => {
    render(
      <StatusBar
        network={mockNetwork}
        simulationState={mockSimulationState}
        isConnected={true}
        lastUpdate={null}
      />
    );

    // Both nodes and pipes have count 5 in our fixture, so use label context
    expect(screen.getByText('Nodes:')).toBeInTheDocument();
    expect(screen.getByText('Pipes:')).toBeInTheDocument();

    // Check that the font-mono spans contain the correct counts
    const monos = screen.getAllByText(String(mockNetwork.nodes.length));
    expect(monos.length).toBeGreaterThanOrEqual(1);
  });

  it('shows Connected when WebSocket is connected', () => {
    render(
      <StatusBar
        network={mockNetwork}
        simulationState={mockSimulationState}
        isConnected={true}
        lastUpdate={null}
      />
    );

    expect(screen.getByText('Connected')).toBeInTheDocument();
  });

  it('shows Disconnected when WebSocket is disconnected', () => {
    render(
      <StatusBar
        network={mockNetwork}
        simulationState={mockSimulationState}
        isConnected={false}
        lastUpdate={null}
      />
    );

    expect(screen.getByText('Disconnected')).toBeInTheDocument();
  });

  it('displays total flow', () => {
    render(
      <StatusBar
        network={mockNetwork}
        simulationState={mockSimulationState}
        isConnected={true}
        lastUpdate={null}
      />
    );

    // Total flow = sum of absolute pipe flow rates
    const totalFlow = Object.values(mockSimulationState.pipe_flow_rates).reduce(
      (sum, f) => sum + Math.abs(f),
      0
    );
    expect(screen.getByText(`${totalFlow.toFixed(0)} m³/h`)).toBeInTheDocument();
  });

  it('displays average pressure', () => {
    render(
      <StatusBar
        network={mockNetwork}
        simulationState={mockSimulationState}
        isConnected={true}
        lastUpdate={null}
      />
    );

    const pressures = Object.values(mockSimulationState.node_pressures);
    const avg = pressures.reduce((a, b) => a + b, 0) / pressures.length;
    expect(screen.getByText(`${avg.toFixed(1)} kPa`)).toBeInTheDocument();
  });

  it('displays last update time when provided', () => {
    const lastUpdate = new Date('2026-02-08T12:30:00');
    render(
      <StatusBar
        network={mockNetwork}
        simulationState={mockSimulationState}
        isConnected={true}
        lastUpdate={lastUpdate}
      />
    );

    expect(screen.getByText(lastUpdate.toLocaleTimeString())).toBeInTheDocument();
  });

  it('handles empty simulation state gracefully', () => {
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
      <StatusBar
        network={{ nodes: [], pipes: [] }}
        simulationState={emptyState}
        isConnected={false}
        lastUpdate={null}
      />
    );

    // Multiple '0' values in empty state, just verify it renders without crashing
    expect(screen.getByText('Nodes:')).toBeInTheDocument();
    expect(screen.getByText('Pipes:')).toBeInTheDocument();
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
  });
});
