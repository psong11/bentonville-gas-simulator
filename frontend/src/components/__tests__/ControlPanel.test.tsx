import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ControlPanel } from '../ControlPanel';

const defaultProps = {
  sourcePressure: 600,
  demandMultiplier: 1.0,
  onSourcePressureChange: vi.fn(),
  onDemandMultiplierChange: vi.fn(),
  onGenerateNetwork: vi.fn(),
  onRefreshNetwork: vi.fn(),
  isGenerating: false,
};

describe('ControlPanel', () => {
  it('renders simulation controls heading', () => {
    render(<ControlPanel {...defaultProps} />);
    expect(screen.getByText('Simulation Controls')).toBeInTheDocument();
  });

  it('displays current source pressure value', () => {
    render(<ControlPanel {...defaultProps} />);
    expect(screen.getByText(/Source Pressure: 600 kPa/)).toBeInTheDocument();
  });

  it('displays current demand multiplier value', () => {
    render(<ControlPanel {...defaultProps} />);
    expect(screen.getByText(/Demand Multiplier: 1.0x/)).toBeInTheDocument();
  });

  it('calls onSourcePressureChange when slider changes', () => {
    const onChange = vi.fn();
    render(<ControlPanel {...defaultProps} onSourcePressureChange={onChange} />);

    const slider = screen.getByDisplayValue('600');
    fireEvent.change(slider, { target: { value: '500' } });
    expect(onChange).toHaveBeenCalledWith(500);
  });

  it('calls onDemandMultiplierChange when slider changes', () => {
    const onChange = vi.fn();
    render(<ControlPanel {...defaultProps} onDemandMultiplierChange={onChange} />);

    const slider = screen.getByDisplayValue('1');
    fireEvent.change(slider, { target: { value: '1.5' } });
    expect(onChange).toHaveBeenCalledWith(1.5);
  });

  it('calls onRefreshNetwork when Refresh button is clicked', () => {
    const onRefresh = vi.fn();
    render(<ControlPanel {...defaultProps} onRefreshNetwork={onRefresh} />);

    fireEvent.click(screen.getByText('Refresh Network'));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('shows advanced network settings when toggle is clicked', () => {
    render(<ControlPanel {...defaultProps} />);

    // Advanced settings should be hidden initially
    expect(screen.queryByText('Network Generation')).not.toBeInTheDocument();

    // Click to show
    fireEvent.click(screen.getByText('Show Network Settings'));
    expect(screen.getByText('Network Generation')).toBeInTheDocument();
  });

  it('shows Generate button in advanced settings', () => {
    render(<ControlPanel {...defaultProps} />);

    fireEvent.click(screen.getByText('Show Network Settings'));
    expect(screen.getByText('Generate New Network')).toBeInTheDocument();
  });

  it('calls onGenerateNetwork when Generate button is clicked', () => {
    const onGenerate = vi.fn();
    render(<ControlPanel {...defaultProps} onGenerateNetwork={onGenerate} />);

    fireEvent.click(screen.getByText('Show Network Settings'));
    fireEvent.click(screen.getByText('Generate New Network'));

    expect(onGenerate).toHaveBeenCalledTimes(1);
    expect(onGenerate).toHaveBeenCalledWith({
      residential: 150,
      commercial: 30,
      industrial: 8,
      total_pipes: 250,
    });
  });

  it('disables Generate button when isGenerating is true', () => {
    render(<ControlPanel {...defaultProps} isGenerating={true} />);

    fireEvent.click(screen.getByText('Show Network Settings'));
    expect(screen.getByText('Generating...')).toBeInTheDocument();
  });
});
