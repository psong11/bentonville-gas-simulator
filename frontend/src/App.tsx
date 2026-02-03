/**
 * Bentonville Gas Simulator
 * Main Application Component
 */

import { useState, useCallback, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Flame, AlertCircle } from 'lucide-react';

import {
  NetworkMap,
  FlowChart,
  PressureHistogram,
  ControlPanel,
  LeakDetection,
  StatusBar,
  ToastContainer,
} from './components';
import type { ToastMessage } from './components';

import {
  useNetwork,
  useSimulation,
  useGenerateNetwork,
  useRunSimulation,
  useLeakDetection,
  useInjectLeaks,
  useClearLeaks,
} from './hooks/useApi';

import { useWebSocket } from './hooks/useWebSocket';

import type { NetworkParams, LeakDetectionResult, SimulationState } from './types';

// Create QueryClient instance
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 2,
    },
  },
});

// Default empty simulation state
const defaultSimulationState: SimulationState = {
  node_pressures: {},
  pipe_flow_rates: {},
  node_actual_demand: {},
  pipe_velocities: {},
  pipe_pressure_drops: {},
  pipe_reynolds: {},
  active_leaks: {},
  warnings: [],
};

function SimulatorApp() {
  // State
  const [sourcePressure, setSourcePressure] = useState(500);
  const [demandMultiplier, setDemandMultiplier] = useState(1.0);
  const [selectedPipeId, setSelectedPipeId] = useState<number | null>(null);
  const [detectionResult, setDetectionResult] = useState<LeakDetectionResult | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  // Toast helpers
  const addToast = useCallback((type: ToastMessage['type'], title: string, message?: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    setToasts(prev => [...prev, { id, type, title, message }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // WebSocket for real-time updates
  const { isConnected: wsConnected, lastUpdate, setPressure: wsPressure, setDemandMultiplier: wsDemand } = useWebSocket();

  // TanStack Query hooks - network and simulation are separate
  const { data: networkData, isLoading: isLoadingNetwork, error: networkError } = useNetwork();
  const { data: simulationData } = useSimulation();
  const generateNetworkMutation = useGenerateNetwork();
  const runSimulationMutation = useRunSimulation();
  const detectLeaksMutation = useLeakDetection();
  const injectLeaksMutation = useInjectLeaks();
  const clearLeaksMutation = useClearLeaks();

  // Extract data with defaults - network comes from /api/network
  const network = networkData ?? { nodes: [], pipes: [] };
  // Simulation state comes from /api/simulation/state
  const simulationState = simulationData ?? defaultSimulationState;
  // Active leaks are node IDs where active_leaks[id] > 0
  const activeLeaks = Object.entries(simulationState.active_leaks ?? {})
    .filter(([_, rate]) => rate > 0)
    .map(([id]) => parseInt(id));

  // Auto-run simulation via WebSocket when parameters change (debounced)
  useEffect(() => {
    if (!networkData || !wsConnected) return;
    
    const timer = setTimeout(() => {
      // Use WebSocket for real-time broadcast to all clients
      wsPressure(sourcePressure);
      wsDemand(demandMultiplier);
    }, 300); // 300ms debounce
    
    return () => clearTimeout(timer);
  }, [sourcePressure, demandMultiplier, wsConnected]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handlers
  const handleRunSimulation = useCallback(() => {
    if (network.nodes.length === 0) {
      addToast('warning', 'No Network Loaded', 'Generate or load a network first before running simulation.');
      return;
    }
    runSimulationMutation.mutate(
      { source_pressure: sourcePressure, demand_multiplier: demandMultiplier },
      {
        onSuccess: (data) => {
          const warnings = data.warnings?.length ?? 0;
          if (warnings > 0) {
            addToast('warning', 'Simulation Complete', `Completed with ${warnings} warning(s). Check pressure levels.`);
          } else {
            addToast('success', 'Simulation Complete', 'Network pressures and flows updated successfully.');
          }
        },
        onError: (error) => {
          addToast('error', 'Simulation Failed', error instanceof Error ? error.message : 'An unexpected error occurred.');
        },
      }
    );
  }, [sourcePressure, demandMultiplier, runSimulationMutation, network.nodes.length, addToast]);

  const handleGenerateNetwork = useCallback(
    (params: NetworkParams) => {
      generateNetworkMutation.mutate(params, {
        onSuccess: (data) => {
          setSelectedPipeId(null);
          setDetectionResult(null);
          const nodeCount = data.nodes?.length ?? 0;
          const pipeCount = data.pipes?.length ?? 0;
          addToast('success', 'Network Generated', `Created ${nodeCount} nodes and ${pipeCount} pipes.`);
        },
        onError: (error) => {
          addToast('error', 'Generation Failed', error instanceof Error ? error.message : 'Failed to generate network.');
        },
      });
    },
    [generateNetworkMutation, addToast]
  );

  const handleInjectLeaks = useCallback(
    (nodeIds: number[]) => {
      if (nodeIds.length === 0) {
        addToast('warning', 'No Nodes Selected', 'Select at least one node to inject leaks.');
        return;
      }
      injectLeaksMutation.mutate(
        { node_ids: nodeIds },
        {
          onSuccess: () => {
            setDetectionResult(null);
            addToast('success', 'Leaks Injected', `${nodeIds.length} leak(s) injected into the network. Run detection to find them.`);
          },
          onError: (error) => {
            addToast('error', 'Injection Failed', error instanceof Error ? error.message : 'Failed to inject leaks.');
          },
        }
      );
    },
    [injectLeaksMutation, addToast]
  );

  const handleDetectLeaks = useCallback(
    (numSensors: number) => {
      if (activeLeaks.length === 0) {
        addToast('warning', 'No Active Leaks', 'Inject leaks first before running detection.');
        return;
      }
      detectLeaksMutation.mutate(
        { num_sensors: numSensors },
        {
          onSuccess: (data) => {
            setDetectionResult(data);
            const detected = data.detected_leaks?.length ?? 0;
            const rate = ((data.detection_rate ?? 0) * 100).toFixed(0);
            if (detected > 0) {
              addToast('success', 'Leaks Detected', `Found ${detected} leak(s) with ${rate}% detection rate.`);
            } else {
              addToast('warning', 'No Leaks Detected', 'Detection algorithm could not locate any leaks. Try adding more sensors.');
            }
          },
          onError: (error) => {
            addToast('error', 'Detection Failed', error instanceof Error ? error.message : 'Failed to run leak detection.');
          },
        }
      );
    },
    [detectLeaksMutation, activeLeaks.length, addToast]
  );

  const handleClearLeaks = useCallback(() => {
    clearLeaksMutation.mutate(undefined, {
      onSuccess: () => {
        setDetectionResult(null);
        addToast('info', 'Leaks Cleared', 'All active leaks have been removed from the network.');
      },
      onError: (error) => {
        addToast('error', 'Clear Failed', error instanceof Error ? error.message : 'Failed to clear leaks.');
      },
    });
  }, [clearLeaksMutation, addToast]);

  const handlePipeSelect = useCallback((pipeId: number | null) => {
    setSelectedPipeId(pipeId);
  }, []);

  // Loading state
  if (isLoadingNetwork) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <Flame className="w-16 h-16 text-orange-500 mx-auto animate-pulse" />
          <p className="mt-4 text-lg text-slate-600">Loading network...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (networkError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="card max-w-md text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto" />
          <h2 className="text-xl font-semibold mt-4">Connection Error</h2>
          <p className="mt-2 text-slate-600">
            Unable to connect to the API server. Make sure the backend is running on port 8000.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="btn btn-primary mt-4"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="flex items-center gap-3">
          <Flame className="w-8 h-8 text-orange-500" />
          <div>
            <h1 className="text-xl font-bold text-slate-900">
              Bentonville Gas Distribution Simulator
            </h1>
            <p className="text-sm text-slate-500">
              Real-time network visualization with Darcy-Weisbach physics
            </p>
          </div>
        </div>
      </header>

      {/* Status Bar */}
      <StatusBar
        network={network}
        simulationState={simulationState}
        isConnected={wsConnected}
        lastUpdate={lastUpdate}
      />

      {/* Main Content */}
      <main className="flex-1 p-6">
        <div className="grid grid-cols-12 gap-6">
          {/* Left Sidebar - Controls */}
          <div className="col-span-3 space-y-6">
            <ControlPanel
              sourcePressure={sourcePressure}
              demandMultiplier={demandMultiplier}
              onSourcePressureChange={setSourcePressure}
              onDemandMultiplierChange={setDemandMultiplier}
              onRunSimulation={handleRunSimulation}
              onGenerateNetwork={handleGenerateNetwork}
              isSimulating={runSimulationMutation.isPending}
              isGenerating={generateNetworkMutation.isPending}
            />
            <LeakDetection
              network={network}
              activeLeaks={activeLeaks}
              detectionResult={detectionResult}
              onInjectLeaks={handleInjectLeaks}
              onDetectLeaks={handleDetectLeaks}
              onClearLeaks={handleClearLeaks}
              isDetecting={detectLeaksMutation.isPending}
              isInjecting={injectLeaksMutation.isPending}
            />
          </div>

          {/* Main Content Area */}
          <div className="col-span-9 space-y-6">
            {/* Network Map */}
            <div className="card">
              <h3 className="font-semibold mb-4">Network Map</h3>
              <NetworkMap
                network={network}
                simulationState={simulationState}
                sourcePressure={sourcePressure}
                selectedPipeId={selectedPipeId}
                onPipeSelect={handlePipeSelect}
                activeLeaks={activeLeaks}
              />
              {selectedPipeId !== null && (
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-sm text-slate-600">
                    Selected: Pipe #{selectedPipeId}
                  </span>
                  <button
                    onClick={() => setSelectedPipeId(null)}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Clear Selection
                  </button>
                </div>
              )}
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-2 gap-6">
              <FlowChart
                network={network}
                simulationState={simulationState}
                selectedPipeId={selectedPipeId}
                onPipeSelect={handlePipeSelect}
              />
              <PressureHistogram
                simulationState={simulationState}
                sourcePressure={sourcePressure}
              />
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 px-6 py-3 text-center text-sm text-slate-500">
        Bentonville Gas Distribution Network Simulator • Darcy-Weisbach Physics Engine
      </footer>

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

// Wrap with QueryClientProvider
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <SimulatorApp />
    </QueryClientProvider>
  );
}

export default App;
