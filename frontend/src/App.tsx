/**
 * Bentonville Gas Simulator
 * Main Application Component
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Flame, AlertCircle } from 'lucide-react';

import {
  NetworkMap,
  FlowChart,
  PressureHistogram,
  ControlPanel,
  LeakDetection,
  StatusBar,
} from './components';

import {
  useNetwork,
  useSimulation,
  useGenerateNetwork,
  useRunSimulation,
  useLeakDetection,
  useInjectLeaks,
  useClearLeaks,
} from './hooks/useApi';

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
  const [selectedPipeId, setSelectedPipeId] = useState<number | null>(null);
  const [detectionResult, setDetectionResult] = useState<LeakDetectionResult | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

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

  // WebSocket connection
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8000/ws`;
    
    const connect = () => {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'SIMULATION_UPDATE' || message.type === 'NETWORK_UPDATE' || message.type === 'LEAK_ALERT') {
            // Invalidate queries to refetch fresh data
            queryClient.invalidateQueries({ queryKey: ['network'] });
            queryClient.invalidateQueries({ queryKey: ['simulation'] });
            setLastUpdate(new Date());
          }
        } catch (err) {
          console.error('WebSocket message parse error:', err);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWsConnected(false);
        // Reconnect after 3 seconds
        setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        ws.close();
      };
    };

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Handlers
  const handleRunSimulation = useCallback(() => {
    runSimulationMutation.mutate(
      { source_pressure: sourcePressure },
      {
        onSuccess: () => {
          setLastUpdate(new Date());
        },
      }
    );
  }, [sourcePressure, runSimulationMutation]);

  const handleGenerateNetwork = useCallback(
    (params: NetworkParams) => {
      generateNetworkMutation.mutate(params, {
        onSuccess: () => {
          setSelectedPipeId(null);
          setDetectionResult(null);
          setLastUpdate(new Date());
        },
      });
    },
    [generateNetworkMutation]
  );

  const handleInjectLeaks = useCallback(
    (nodeIds: number[]) => {
      injectLeaksMutation.mutate(
        { node_ids: nodeIds },
        {
          onSuccess: () => {
            setDetectionResult(null);
            setLastUpdate(new Date());
          },
        }
      );
    },
    [injectLeaksMutation]
  );

  const handleDetectLeaks = useCallback(
    (numSensors: number) => {
      detectLeaksMutation.mutate(
        { num_sensors: numSensors },
        {
          onSuccess: (data) => {
            setDetectionResult(data);
            setLastUpdate(new Date());
          },
        }
      );
    },
    [detectLeaksMutation]
  );

  const handleClearLeaks = useCallback(() => {
    clearLeaksMutation.mutate(undefined, {
      onSuccess: () => {
        setDetectionResult(null);
        setLastUpdate(new Date());
      },
    });
  }, [clearLeaksMutation]);

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
              onSourcePressureChange={setSourcePressure}
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
