/**
 * TypeScript types matching the API schemas
 * These mirror the Pydantic models in api/schemas.py
 */

// ============================================================================
// Network Types
// ============================================================================

export type NodeType = 'residential' | 'commercial' | 'industrial' | 'source';

export interface Node {
  id: number;
  node_type: NodeType;
  x: number; // Longitude
  y: number; // Latitude
  base_demand: number; // m³/hour
  elevation: number; // meters
  name: string;
}

export interface Pipe {
  id: number;
  source_id: number;
  target_id: number;
  length: number; // meters
  diameter: number; // meters
  roughness: number;
  material: string;
  year_installed: number;
}

export interface Network {
  nodes: Node[];
  pipes: Pipe[];
}

export interface NetworkParams {
  residential: number;
  commercial: number;
  industrial: number;
  total_pipes: number;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface SimulationState {
  node_pressures: Record<number, number>;
  node_actual_demand: Record<number, number>;
  pipe_flow_rates: Record<number, number>;
  pipe_velocities?: Record<number, number>;
  pipe_pressure_drops?: Record<number, number>;
  pipe_reynolds?: Record<number, number>;
  active_leaks?: Record<number, number>;
  warnings?: string[];
}

export interface NetworkResponse {
  network: Network;
  simulation_state: SimulationState;
  active_leaks: number[];
}

// ============================================================================
// Simulation Types
// ============================================================================

export interface SimulationRequest {
  source_pressure?: number;
  demand_multiplier?: number;
}

export interface SimulationResponse {
  simulation_state: SimulationState;
  active_leaks: number[];
}

// ============================================================================
// Leak Detection Types
// ============================================================================

export type LeakDetectionStrategy = 'pressure_drop' | 'flow_imbalance' | 'combined';

export interface SuspectedLeak {
  node_id: number;
  confidence: number;
  reason: string;
  pressure?: number;
  flow_imbalance?: number;
}

export interface LeakDetectionResult {
  suspected_leaks: SuspectedLeak[];
  detected_leaks: number[];
  sensor_placements: number[];
  detection_rate: number;
  false_positive_rate: number;
  strategy_used: string;
  detection_time_ms: number;
}

export interface InjectLeaksRequest {
  node_ids: number[];
}

export interface InjectLeaksResult {
  injected_node_ids: number[];
  active_leaks: number[];
}

export interface ClearLeaksResult {
  cleared_count: number;
  active_leaks: number[];
}

// ============================================================================
// WebSocket Types
// ============================================================================

export type WSMessageType =
  | 'SET_PRESSURE'
  | 'SET_DEMAND_MULTIPLIER'
  | 'INJECT_LEAK'
  | 'CLEAR_LEAKS'
  | 'HIGHLIGHT_PIPE'
  | 'SIMULATION_UPDATE'
  | 'NETWORK_UPDATE'
  | 'LEAK_ALERT'
  | 'ERROR';

export interface WSMessage<T = unknown> {
  type: WSMessageType;
  payload: T;
}

// ============================================================================
// UI State Types
// ============================================================================

export interface SelectedPipe {
  id: number;
  source_name: string;
  target_name: string;
  flow_rate: number;
}

export type PressureStatus = 'normal' | 'warning' | 'critical' | 'over';

export const PRESSURE_COLORS = {
  normal: '#22c55e',    // green
  warning: '#eab308',   // yellow
  critical: '#ef4444',  // red
  over: '#a855f7',      // purple
} as const;

export function getPressureStatus(pressure: number, sourcePressure: number): PressureStatus {
  const ratio = pressure / sourcePressure;
  if (ratio < 0.7) return 'critical';
  if (ratio < 0.85) return 'warning';
  if (ratio <= 1.05) return 'normal';
  return 'over';
}

export function getPressureColor(status: PressureStatus): string {
  return PRESSURE_COLORS[status];
}
