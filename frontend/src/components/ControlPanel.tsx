/**
 * ControlPanel Component
 * Controls for simulation parameters and network generation
 */

import { useState, useCallback } from 'react';
import { RotateCcw, Settings, Loader2, RefreshCw } from 'lucide-react';
import type { NetworkParams } from '../types';

interface ControlPanelProps {
  sourcePressure: number;
  demandMultiplier: number;
  onSourcePressureChange: (pressure: number) => void;
  onDemandMultiplierChange: (multiplier: number) => void;
  onGenerateNetwork: (params: NetworkParams) => void;
  onRefreshNetwork: () => void;
  isGenerating: boolean;
}

export function ControlPanel({
  sourcePressure,
  demandMultiplier,
  onSourcePressureChange,
  onDemandMultiplierChange,
  onGenerateNetwork,
  onRefreshNetwork,
  isGenerating,
}: ControlPanelProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [networkParams, setNetworkParams] = useState<NetworkParams>({
    residential: 150,
    commercial: 30,
    industrial: 8,
    total_pipes: 250,
  });

  const handlePressureChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = parseFloat(e.target.value);
      if (!isNaN(value)) {
        onSourcePressureChange(value);
      }
    },
    [onSourcePressureChange]
  );

  const handleDemandChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = parseFloat(e.target.value);
      if (!isNaN(value)) {
        onDemandMultiplierChange(value);
      }
    },
    [onDemandMultiplierChange]
  );

  const handleParamChange = useCallback(
    (key: keyof NetworkParams) => (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = parseInt(e.target.value);
      if (!isNaN(value)) {
        setNetworkParams((prev: NetworkParams) => ({ ...prev, [key]: value }));
      }
    },
    []
  );

  const handleGenerate = useCallback(() => {
    onGenerateNetwork(networkParams);
  }, [onGenerateNetwork, networkParams]);

  return (
    <div className="card space-y-6">
      <h3 className="font-semibold text-lg">Simulation Controls</h3>

      {/* Source Pressure Slider */}
      <div>
        <label className="label">
          Source Pressure: {sourcePressure.toFixed(0)} kPa
        </label>
        <input
          type="range"
          min="200"
          max="800"
          step="10"
          value={sourcePressure}
          onChange={handlePressureChange}
          className="input w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer"
        />
        <div className="flex justify-between text-xs text-slate-500 mt-1">
          <span>200 kPa</span>
          <span>600 kPa (default)</span>
          <span>800 kPa</span>
        </div>
      </div>

      {/* Demand Multiplier Slider */}
      <div>
        <label className="label">
          Demand Multiplier: {demandMultiplier.toFixed(1)}x
        </label>
        <input
          type="range"
          min="0.5"
          max="2.0"
          step="0.1"
          value={demandMultiplier}
          onChange={handleDemandChange}
          className="input w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer"
        />
        <div className="flex justify-between text-xs text-slate-500 mt-1">
          <span>0.5x (low)</span>
          <span>1.0x (normal)</span>
          <span>2.0x (peak)</span>
        </div>
      </div>

      {/* Refresh Network Button */}
      <button
        onClick={onRefreshNetwork}
        className="btn btn-secondary w-full flex items-center justify-center gap-2"
      >
        <RefreshCw className="w-4 h-4" />
        Refresh Network
      </button>

      {/* Advanced Settings Toggle */}
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="btn btn-secondary w-full flex items-center justify-center gap-2"
      >
        <Settings className="w-4 h-4" />
        {showAdvanced ? 'Hide' : 'Show'} Network Settings
      </button>

      {/* Advanced Settings Panel */}
      {showAdvanced && (
        <div className="space-y-4 pt-4 border-t border-slate-200">
          <h4 className="font-medium text-sm text-slate-700">Network Generation</h4>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Residential</label>
              <input
                type="number"
                value={networkParams.residential}
                onChange={handleParamChange('residential')}
                min={50}
                max={500}
                className="input w-full"
              />
            </div>
            <div>
              <label className="label">Commercial</label>
              <input
                type="number"
                value={networkParams.commercial}
                onChange={handleParamChange('commercial')}
                min={10}
                max={100}
                className="input w-full"
              />
            </div>
            <div>
              <label className="label">Industrial</label>
              <input
                type="number"
                value={networkParams.industrial}
                onChange={handleParamChange('industrial')}
                min={1}
                max={30}
                className="input w-full"
              />
            </div>
            <div>
              <label className="label">Total Pipes</label>
              <input
                type="number"
                value={networkParams.total_pipes}
                onChange={handleParamChange('total_pipes')}
                min={100}
                max={500}
                className="input w-full"
              />
            </div>
          </div>

          <button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="btn btn-secondary w-full flex items-center justify-center gap-2"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <RotateCcw className="w-4 h-4" />
                Generate New Network
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
