/**
 * TanStack Query Hooks for API data fetching
 * Provides caching, background refetching, and optimistic updates
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '../api/client';
import type { NetworkParams, SimulationRequest, InjectLeaksRequest } from '../types';

// ============================================================================
// Query Keys
// ============================================================================

export const queryKeys = {
  network: ['network'] as const,
  simulation: ['simulation'] as const,
  leakDetection: ['leaks', 'detection'] as const,
};

// ============================================================================
// Network Hooks
// ============================================================================

export function useNetwork() {
  return useQuery({
    queryKey: queryKeys.network,
    queryFn: api.getNetwork,
    staleTime: Infinity, // Network doesn't change unless regenerated
  });
}

export function useGenerateNetwork() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (params: NetworkParams) => api.generateNetwork(params),
    onSuccess: (data) => {
      // Update network cache with new data
      queryClient.setQueryData(queryKeys.network, data);
      // Invalidate simulation since network changed
      queryClient.invalidateQueries({ queryKey: ['simulation'] });
    },
  });
}

// ============================================================================
// Simulation Hooks
// ============================================================================

export function useSimulation() {
  return useQuery({
    queryKey: queryKeys.simulation,
    queryFn: api.getSimulationState,
    staleTime: 1000 * 60, // 1 minute
    refetchOnWindowFocus: false,
  });
}

export function useRunSimulation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (params: SimulationRequest) => api.runSimulation(params),
    onSuccess: (data) => {
      // Update simulation cache
      queryClient.setQueryData(queryKeys.simulation, data);
      // Invalidate network to get updated state
      queryClient.invalidateQueries({ queryKey: queryKeys.network });
    },
  });
}

// ============================================================================
// Leak Hooks
// ============================================================================

export function useLeakDetection() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (params: { num_sensors: number; sensor_node_ids?: number[] }) => api.detectLeaks(params),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.leakDetection, data);
    },
  });
}

export function useInjectLeaks() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: InjectLeaksRequest) => api.injectLeaks(request),
    onSuccess: () => {
      // Invalidate queries to reflect new leaks
      queryClient.invalidateQueries({ queryKey: queryKeys.network });
      queryClient.invalidateQueries({ queryKey: queryKeys.simulation });
    },
  });
}

export function useClearLeaks() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.clearLeaks,
    onSuccess: () => {
      // Invalidate queries to reflect cleared leaks
      queryClient.invalidateQueries({ queryKey: queryKeys.network });
      queryClient.invalidateQueries({ queryKey: queryKeys.simulation });
    },
  });
}
