import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FlowChart } from '../FlowChart';
import { mockNetwork, mockSimulationState } from '../../test/fixtures';

// Mock react-plotly.js since jsdom cannot render canvas/WebGL
vi.mock('react-plotly.js', () => ({
  __esModule: true,
  default: (props: { data: unknown[]; layout: Record<string, unknown> }) => (
    <div data-testid="plotly-chart" data-traces={JSON.stringify(props.data)} />
  ),
}));

describe('FlowChart', () => {
  const defaultProps = {
    network: mockNetwork,
    simulationState: mockSimulationState,
    selectedPipeId: null as number | null,
    onPipeSelect: vi.fn(),
  };

  it('renders chart heading', () => {
    render(<FlowChart {...defaultProps} />);
    expect(screen.getByText('Top 20 Pipes by Flow Rate')).toBeInTheDocument();
  });

  it('renders the Plotly chart', () => {
    render(<FlowChart {...defaultProps} />);
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument();
  });

  it('passes correct number of bars (capped at 20)', () => {
    render(<FlowChart {...defaultProps} />);
    const chart = screen.getByTestId('plotly-chart');
    const traces = JSON.parse(chart.getAttribute('data-traces') || '[]');

    // Should have one trace (bar chart) with pipe count bars (5 pipes, all < 20)
    expect(traces).toHaveLength(1);
    expect(traces[0].x).toHaveLength(mockNetwork.pipes.length);
  });

  it('sorts pipes by flow rate descending', () => {
    render(<FlowChart {...defaultProps} />);
    const chart = screen.getByTestId('plotly-chart');
    const traces = JSON.parse(chart.getAttribute('data-traces') || '[]');

    const flowValues: number[] = traces[0].x;
    for (let i = 1; i < flowValues.length; i++) {
      expect(flowValues[i - 1]).toBeGreaterThanOrEqual(flowValues[i]);
    }
  });

  it('highlights selected pipe in red', () => {
    render(<FlowChart {...defaultProps} selectedPipeId={1} />);
    const chart = screen.getByTestId('plotly-chart');
    const traces = JSON.parse(chart.getAttribute('data-traces') || '[]');

    // Find the index of pipe 1 in customdata
    const pipeIds: number[] = traces[0].customdata;
    const idx = pipeIds.indexOf(1);
    expect(idx).toBeGreaterThanOrEqual(0);
    expect(traces[0].marker.color[idx]).toBe('#ef4444'); // red
  });

  it('uses blue for non-selected pipes', () => {
    render(<FlowChart {...defaultProps} selectedPipeId={null} />);
    const chart = screen.getByTestId('plotly-chart');
    const traces = JSON.parse(chart.getAttribute('data-traces') || '[]');

    const colors: string[] = traces[0].marker.color;
    colors.forEach(c => expect(c).toBe('#3b82f6')); // all blue
  });

  it('renders instruction text', () => {
    render(<FlowChart {...defaultProps} />);
    expect(screen.getByText('Click a bar to highlight on map')).toBeInTheDocument();
  });
});
