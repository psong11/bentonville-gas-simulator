/**
 * API Client for Bentonville Gas Simulator
 * Handles all HTTP requests to the FastAPI backend
 */

import axios from 'axios';
import type {
  NetworkResponse,
  NetworkParams,
  SimulationRequest,
  SimulationResponse,
  LeakDetectionResult,
  InjectLeaksRequest,
  InjectLeaksResult,
  ClearLeaksResult,
} from '../types';

// API base URL - uses Vite proxy in dev, direct in production
const API_BASE = '/api';

const client = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============================================================================
// Network API
// ============================================================================

export async function getNetwork(): Promise<NetworkResponse> {
  const response = await client.get<NetworkResponse>('/network');
  return response.data;
}

export async function generateNetwork(params: NetworkParams): Promise<NetworkResponse> {
  const nodeCount = params.residential + params.commercial + params.industrial + 1; // +1 for source
  const response = await client.post<NetworkResponse>('/network/generate', {
    node_count: nodeCount,
  });
  return response.data;
}

// ============================================================================
// Simulation API
// ============================================================================

export async function runSimulation(params: SimulationRequest): Promise<SimulationResponse> {
  const response = await client.post<SimulationResponse>('/simulate', {
    source_pressure: params.source_pressure ?? 400,
    demand_multiplier: params.demand_multiplier ?? 1.0,
    active_leaks: [],
  });
  return response.data;
}

export async function getSimulationState(): Promise<SimulationResponse> {
  const response = await client.get<SimulationResponse>('/simulation/state');
  return response.data;
}

// ============================================================================
// Leak API
// ============================================================================

export interface DetectLeaksParams {
  num_sensors: number;
}

export async function detectLeaks(params: DetectLeaksParams): Promise<LeakDetectionResult> {
  const response = await client.post<LeakDetectionResult>('/leaks/detect', {
    strategy: 'combined',
    num_sensors: params.num_sensors,
  });
  return response.data;
}

export async function injectLeaks(request: InjectLeaksRequest): Promise<InjectLeaksResult> {
  const response = await client.post<InjectLeaksResult>('/leaks/inject', {
    count: request.node_ids.length,
    node_ids: request.node_ids,
  });
  return response.data;
}

export async function clearLeaks(): Promise<ClearLeaksResult> {
  const response = await client.post<ClearLeaksResult>('/leaks/clear');
  return response.data;
}

// ============================================================================
// Health Check
// ============================================================================

export async function healthCheck(): Promise<{ status: string; version: string }> {
  const response = await client.get<{ status: string; version: string }>('/health');
  return response.data;
}
