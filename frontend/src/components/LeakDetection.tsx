/**
 * LeakDetection Component
 * Panel for injecting and detecting leaks in the network
 */

import { useState, useCallback, useMemo } from 'react';
import { AlertTriangle, Search, Plus, Trash2, Loader2 } from 'lucide-react';
import type { Network, LeakDetectionResult } from '../types';

interface LeakDetectionProps {
  network: Network;
  activeLeaks: number[];
  detectionResult: LeakDetectionResult | null;
  onInjectLeaks: (nodeIds: number[]) => void;
  onDetectLeaks: (numSensors: number) => void;
  onClearLeaks: () => void;
  isDetecting: boolean;
  isInjecting: boolean;
}

export function LeakDetection({
  network,
  activeLeaks,
  detectionResult,
  onInjectLeaks,
  onDetectLeaks,
  onClearLeaks,
  isDetecting,
  isInjecting,
}: LeakDetectionProps) {
  const [numLeaks, setNumLeaks] = useState(3);
  const [numSensors, setNumSensors] = useState(5);
  const [selectedNodes, setSelectedNodes] = useState<number[]>([]);

  // Get injectable nodes (non-source)
  const injectableNodes = useMemo(() => {
    return network.nodes
      .filter(n => n.node_type !== 'source')
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [network.nodes]);

  // Handle random leak injection
  const handleRandomLeaks = useCallback(() => {
    const shuffled = [...injectableNodes]
      .sort(() => Math.random() - 0.5)
      .slice(0, numLeaks)
      .map(n => n.id);
    onInjectLeaks(shuffled);
  }, [injectableNodes, numLeaks, onInjectLeaks]);

  // Handle selected node injection
  const handleInjectSelected = useCallback(() => {
    if (selectedNodes.length > 0) {
      onInjectLeaks(selectedNodes);
      setSelectedNodes([]);
    }
  }, [selectedNodes, onInjectLeaks]);

  // Handle node selection
  const handleNodeToggle = useCallback((nodeId: number) => {
    setSelectedNodes(prev =>
      prev.includes(nodeId)
        ? prev.filter(id => id !== nodeId)
        : [...prev, nodeId]
    );
  }, []);

  // Handle detection
  const handleDetect = useCallback(() => {
    onDetectLeaks(numSensors);
  }, [numSensors, onDetectLeaks]);

  return (
    <div className="card space-y-6">
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-5 h-5 text-amber-500" />
        <h3 className="font-semibold text-lg">Leak Simulation</h3>
      </div>

      {/* Active Leaks Status */}
      {activeLeaks.length > 0 ? (
        <div className="alert alert-warning">
          <AlertTriangle className="w-4 h-4" />
          <span>{activeLeaks.length} active leak{activeLeaks.length > 1 ? 's' : ''} in network</span>
        </div>
      ) : (
        <div className="alert alert-info">
          <span>No active leaks. Inject leaks to test detection.</span>
        </div>
      )}

      {/* Random Leak Injection */}
      <div className="space-y-3">
        <h4 className="font-medium text-sm">Random Leak Injection</h4>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="label">Number of Leaks</label>
            <input
              type="number"
              value={numLeaks}
              onChange={(e) => setNumLeaks(parseInt(e.target.value) || 1)}
              min={1}
              max={10}
              className="input w-full"
            />
          </div>
          <button
            onClick={handleRandomLeaks}
            disabled={isInjecting}
            className="btn btn-secondary flex items-center gap-2"
          >
            {isInjecting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            Inject
          </button>
        </div>
      </div>

      {/* Manual Node Selection */}
      <div className="space-y-3">
        <h4 className="font-medium text-sm">Manual Selection</h4>
        <select
          className="input w-full"
          value=""
          onChange={(e) => {
            const nodeId = parseInt(e.target.value);
            if (!isNaN(nodeId)) {
              handleNodeToggle(nodeId);
            }
          }}
        >
          <option value="">Select node to add...</option>
          {injectableNodes
            .filter(n => !selectedNodes.includes(n.id))
            .map(node => (
              <option key={node.id} value={node.id}>
                {node.name} ({node.node_type})
              </option>
            ))}
        </select>

        {selectedNodes.length > 0 && (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              {selectedNodes.map(nodeId => {
                const node = network.nodes.find(n => n.id === nodeId);
                return (
                  <span
                    key={nodeId}
                    className="badge badge-warning flex items-center gap-1"
                  >
                    {node?.name || `Node ${nodeId}`}
                    <button
                      onClick={() => handleNodeToggle(nodeId)}
                      className="hover:text-amber-900"
                    >
                      ×
                    </button>
                  </span>
                );
              })}
            </div>
            <button
              onClick={handleInjectSelected}
              disabled={isInjecting}
              className="btn btn-primary w-full flex items-center justify-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Inject Selected ({selectedNodes.length})
            </button>
          </div>
        )}
      </div>

      {/* Clear Leaks */}
      {activeLeaks.length > 0 && (
        <button
          onClick={onClearLeaks}
          className="btn btn-secondary w-full flex items-center justify-center gap-2 text-red-600 border-red-200 hover:bg-red-50"
        >
          <Trash2 className="w-4 h-4" />
          Clear All Leaks
        </button>
      )}

      {/* Leak Detection */}
      <div className="pt-4 border-t border-slate-200 space-y-3">
        <h4 className="font-medium text-sm flex items-center gap-2">
          <Search className="w-4 h-4" />
          Leak Detection
        </h4>
        
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="label">Number of Sensors</label>
            <input
              type="number"
              value={numSensors}
              onChange={(e) => setNumSensors(parseInt(e.target.value) || 1)}
              min={1}
              max={20}
              className="input w-full"
            />
          </div>
          <button
            onClick={handleDetect}
            disabled={isDetecting || activeLeaks.length === 0}
            className="btn btn-primary flex items-center gap-2"
          >
            {isDetecting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
            Detect
          </button>
        </div>
      </div>

      {/* Detection Results */}
      {detectionResult && (
        <div className="pt-4 border-t border-slate-200 space-y-3">
          <h4 className="font-medium text-sm">Detection Results</h4>
          
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-slate-500">Detection Rate:</span>
              <span className={`ml-2 font-bold ${
                detectionResult.detection_rate > 0.8 ? 'text-green-600' :
                detectionResult.detection_rate > 0.5 ? 'text-amber-600' :
                'text-red-600'
              }`}>
                {(detectionResult.detection_rate * 100).toFixed(0)}%
              </span>
            </div>
            <div>
              <span className="text-slate-500">False Positive:</span>
              <span className={`ml-2 font-bold ${
                detectionResult.false_positive_rate < 0.1 ? 'text-green-600' :
                detectionResult.false_positive_rate < 0.3 ? 'text-amber-600' :
                'text-red-600'
              }`}>
                {(detectionResult.false_positive_rate * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          {detectionResult.detected_leaks.length > 0 && (
            <div>
              <span className="text-sm text-slate-500">Detected:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {detectionResult.detected_leaks.map(nodeId => {
                  const node = network.nodes.find(n => n.id === nodeId);
                  return (
                    <span key={nodeId} className="badge badge-success text-xs">
                      {node?.name || `Node ${nodeId}`}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {detectionResult.sensor_placements.length > 0 && (
            <div>
              <span className="text-sm text-slate-500">Sensor Locations:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {detectionResult.sensor_placements.map(nodeId => {
                  const node = network.nodes.find(n => n.id === nodeId);
                  return (
                    <span key={nodeId} className="badge bg-blue-100 text-blue-800 text-xs">
                      {node?.name || `Node ${nodeId}`}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
