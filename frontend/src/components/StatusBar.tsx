/**
 * StatusBar Component
 * Displays network statistics and connection status
 */

import { Activity, Wifi, WifiOff, Clock } from 'lucide-react';
import type { Network, SimulationState } from '../types';

interface StatusBarProps {
  network: Network;
  simulationState: SimulationState;
  isConnected: boolean;
  lastUpdate: Date | null;
}

export function StatusBar({
  network,
  simulationState,
  isConnected,
  lastUpdate,
}: StatusBarProps) {
  // Calculate stats
  const totalFlow = Object.values(simulationState.pipe_flow_rates).reduce(
    (sum, flow) => sum + Math.abs(flow),
    0
  );

  const avgPressure =
    Object.values(simulationState.node_pressures).length > 0
      ? Object.values(simulationState.node_pressures).reduce((a, b) => a + b, 0) /
        Object.values(simulationState.node_pressures).length
      : 0;

  const totalDemandMet = Object.values(simulationState.node_actual_demand).reduce(
    (sum, demand) => sum + demand,
    0
  );

  return (
    <div className="bg-slate-800 text-white px-4 py-2 flex items-center justify-between text-sm">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-green-400" />
          <span className="text-slate-400">Nodes:</span>
          <span className="font-mono">{network.nodes.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Pipes:</span>
          <span className="font-mono">{network.pipes.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Total Flow:</span>
          <span className="font-mono">{totalFlow.toFixed(0)} m³/h</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Avg Pressure:</span>
          <span className="font-mono">{avgPressure.toFixed(1)} kPa</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Demand Met:</span>
          <span className="font-mono">{totalDemandMet.toFixed(0)} m³/h</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {lastUpdate && (
          <div className="flex items-center gap-2 text-slate-400">
            <Clock className="w-4 h-4" />
            <span>
              {lastUpdate.toLocaleTimeString()}
            </span>
          </div>
        )}
        <div className="flex items-center gap-2">
          {isConnected ? (
            <>
              <Wifi className="w-4 h-4 text-green-400" />
              <span className="text-green-400">Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4 text-red-400" />
              <span className="text-red-400">Disconnected</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
