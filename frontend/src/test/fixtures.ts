/**
 * Shared test fixtures for component tests
 */
import type { Network, SimulationState } from '../types';

export const mockNetwork: Network = {
  nodes: [
    { id: 0, node_type: 'source', x: -94.21, y: 36.37, base_demand: 0, elevation: 400, name: 'Source Station #1' },
    { id: 1, node_type: 'residential', x: -94.20, y: 36.38, base_demand: 2.5, elevation: 405, name: '101 Oak Street' },
    { id: 2, node_type: 'residential', x: -94.19, y: 36.39, base_demand: 3.0, elevation: 410, name: '202 Pine Avenue' },
    { id: 3, node_type: 'commercial', x: -94.22, y: 36.36, base_demand: 15.0, elevation: 395, name: 'Walmart Store #45' },
    { id: 4, node_type: 'industrial', x: -94.18, y: 36.35, base_demand: 50.0, elevation: 390, name: 'Distribution Center #12' },
  ],
  pipes: [
    { id: 0, source_id: 0, target_id: 1, length: 500, diameter: 0.15, roughness: 0.000045, material: 'steel', year_installed: 2010 },
    { id: 1, source_id: 0, target_id: 3, length: 300, diameter: 0.20, roughness: 0.000045, material: 'steel', year_installed: 2005 },
    { id: 2, source_id: 1, target_id: 2, length: 400, diameter: 0.10, roughness: 0.000045, material: 'polyethylene', year_installed: 2020 },
    { id: 3, source_id: 3, target_id: 4, length: 600, diameter: 0.25, roughness: 0.000045, material: 'ductile_iron', year_installed: 2000 },
    { id: 4, source_id: 2, target_id: 4, length: 700, diameter: 0.10, roughness: 0.000045, material: 'pvc', year_installed: 2015 },
  ],
};

export const mockSimulationState: SimulationState = {
  node_pressures: { 0: 600, 1: 570, 2: 540, 3: 580, 4: 520 },
  node_actual_demand: { 0: 0, 1: 2.5, 2: 3.0, 3: 15.0, 4: 50.0 },
  pipe_flow_rates: { 0: 25.5, 1: 65.0, 2: 12.3, 3: 50.0, 4: 8.7 },
  pipe_velocities: { 0: 1.2, 1: 2.1, 2: 0.8, 3: 1.5, 4: 0.6 },
  pipe_pressure_drops: { 0: 30, 1: 20, 2: 30, 3: 60, 4: 20 },
  pipe_reynolds: { 0: 15000, 1: 35000, 2: 8000, 3: 30000, 4: 5000 },
  active_leaks: {},
  warnings: [],
};

export const mockSimulationStateWithLeaks: SimulationState = {
  ...mockSimulationState,
  active_leaks: { 2: 50.0 },
  node_pressures: { 0: 600, 1: 570, 2: 450, 3: 580, 4: 520 },
};
