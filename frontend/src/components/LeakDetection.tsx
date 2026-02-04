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
  onDetectLeaks: (numSensors: number, sensorNodeIds?: number[]) => void;
  onClearLeaks: () => void;
  onSensorNodesChange: (nodeIds: number[]) => void;
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
  onSensorNodesChange,
  isDetecting,
  isInjecting,
}: LeakDetectionProps) {
  const [numLeaks, setNumLeaks] = useState(3);
  const [numSensors, setNumSensors] = useState(3);
  const [selectedNodes, setSelectedNodes] = useState<number[]>([]);
  const [selectedSensorNodes, setSelectedSensorNodes] = useState<number[]>([]);
  const [sensorSearchTerm, setSensorSearchTerm] = useState('');
  const [showSensorDropdown, setShowSensorDropdown] = useState(false);
  const [leakSearchTerm, setLeakSearchTerm] = useState('');
  const [showLeakDropdown, setShowLeakDropdown] = useState(false);

  // Get injectable nodes (non-source)
  const injectableNodes = useMemo(() => {
    return network.nodes
      .filter(n => n.node_type !== 'source')
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [network.nodes]);

  // Filtered nodes for sensor search
  const filteredSensorNodes = useMemo(() => {
    const available = injectableNodes.filter(n => !selectedSensorNodes.includes(n.id));
    if (!sensorSearchTerm.trim()) return available;
    const term = sensorSearchTerm.toLowerCase();
    return available.filter(n => 
      n.name.toLowerCase().includes(term) || 
      n.node_type.toLowerCase().includes(term)
    );
  }, [injectableNodes, selectedSensorNodes, sensorSearchTerm]);

  // Filtered nodes for leak search
  const filteredLeakNodes = useMemo(() => {
    const available = injectableNodes.filter(n => !selectedNodes.includes(n.id));
    if (!leakSearchTerm.trim()) return available;
    const term = leakSearchTerm.toLowerCase();
    return available.filter(n => 
      n.name.toLowerCase().includes(term) || 
      n.node_type.toLowerCase().includes(term)
    );
  }, [injectableNodes, selectedNodes, leakSearchTerm]);

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

  // Handle node selection - enforce limit
  const handleNodeToggle = useCallback((nodeId: number) => {
    setSelectedNodes(prev => {
      if (prev.includes(nodeId)) {
        return prev.filter(id => id !== nodeId);
      }
      // Don't add if already at limit
      if (prev.length >= numLeaks) {
        return prev;
      }
      return [...prev, nodeId];
    });
    setLeakSearchTerm('');
    setShowLeakDropdown(false);
  }, [numLeaks]);

  // Clear selected if they exceed new limit when numLeaks changes
  const handleNumLeaksChange = useCallback((newValue: number) => {
    setNumLeaks(newValue);
    setSelectedNodes(prev => prev.slice(0, newValue));
  }, []);

  // How many more manual selections can be added
  const remainingSlots = numLeaks - selectedNodes.length;

  // Handle sensor node selection - enforce limit
  const handleSensorNodeToggle = useCallback((nodeId: number) => {
    setSelectedSensorNodes(prev => {
      let newNodes: number[];
      if (prev.includes(nodeId)) {
        newNodes = prev.filter(id => id !== nodeId);
      } else if (prev.length >= numSensors) {
        newNodes = prev;
      } else {
        newNodes = [...prev, nodeId];
      }
      // Notify parent of change
      onSensorNodesChange(newNodes);
      return newNodes;
    });
    setSensorSearchTerm('');
    setShowSensorDropdown(false);
  }, [numSensors, onSensorNodesChange]);

  // Clear selected sensors if they exceed new limit when numSensors changes
  const handleNumSensorsChange = useCallback((newValue: number) => {
    setNumSensors(newValue);
    setSelectedSensorNodes(prev => {
      const newNodes = prev.slice(0, newValue);
      onSensorNodesChange(newNodes);
      return newNodes;
    });
  }, [onSensorNodesChange]);

  // How many more manual sensor selections can be added
  const remainingSensorSlots = numSensors - selectedSensorNodes.length;

  // Handle detection - use manual sensors if selected, otherwise auto-place
  const handleDetect = useCallback(() => {
    if (selectedSensorNodes.length > 0) {
      onDetectLeaks(selectedSensorNodes.length, selectedSensorNodes);
    } else {
      onDetectLeaks(numSensors);
    }
  }, [numSensors, selectedSensorNodes, onDetectLeaks]);

  return (
    <div className="card space-y-6">
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-5 h-5 text-amber-500" />
        <h3 className="font-semibold text-lg">Leak Detection Simulation</h3>
      </div>

      {/* ================================================================== */}
      {/* STEP 1: Sensor Setup */}
      {/* ================================================================== */}
      <div className="space-y-3">
        <h4 className="font-medium text-sm flex items-center gap-2">
          <Search className="w-4 h-4 text-blue-500" />
          Step 1: Setup Sensors
        </h4>
        <p className="text-xs text-slate-500">
          Place sensors to detect pressure anomalies. Choose locations manually or use auto-placement.
        </p>
        
        {/* Number of Sensors */}
        <div>
          <label className="label">Number of Sensors</label>
          <input
            type="number"
            value={numSensors}
            onChange={(e) => handleNumSensorsChange(parseInt(e.target.value) || 1)}
            min={1}
            max={20}
            className="input w-full"
          />
        </div>

        {/* Manual Sensor Selection */}
        <div className="space-y-2">
          <label className="label">
            Manual Sensor Placement
            <span className="text-slate-400 font-normal ml-2">
              ({selectedSensorNodes.length}/{numSensors} placed)
            </span>
          </label>
          <div className="relative">
            <input
              type="text"
              className="input w-full"
              placeholder={
                remainingSensorSlots === 0 
                  ? `All ${numSensors} sensors placed` 
                  : `Type to search nodes (${remainingSensorSlots} remaining)...`
              }
              value={sensorSearchTerm}
              disabled={remainingSensorSlots === 0}
              onChange={(e) => {
                setSensorSearchTerm(e.target.value);
                setShowSensorDropdown(true);
              }}
              onFocus={() => setShowSensorDropdown(true)}
              onBlur={() => {
                // Delay to allow click on dropdown item
                setTimeout(() => setShowSensorDropdown(false), 200);
              }}
            />
            {showSensorDropdown && remainingSensorSlots > 0 && filteredSensorNodes.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-y-auto">
                {filteredSensorNodes.slice(0, 50).map(node => (
                  <button
                    key={node.id}
                    type="button"
                    className="w-full px-3 py-2 text-left text-sm hover:bg-blue-50 focus:bg-blue-50 focus:outline-none"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      handleSensorNodeToggle(node.id);
                    }}
                  >
                    <span className="font-medium">{node.name}</span>
                    <span className="text-slate-400 ml-2">({node.node_type})</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {selectedSensorNodes.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {selectedSensorNodes.map(nodeId => {
                const node = network.nodes.find(n => n.id === nodeId);
                return (
                  <span
                    key={nodeId}
                    className="badge bg-blue-100 text-blue-800 flex items-center gap-1"
                  >
                    {node?.name || `Node ${nodeId}`}
                    <button
                      onClick={() => handleSensorNodeToggle(nodeId)}
                      className="hover:text-blue-900"
                    >
                      ×
                    </button>
                  </span>
                );
              })}
            </div>
          )}
          
          {selectedSensorNodes.length === 0 && (
            <p className="text-xs text-slate-400 italic">
              No manual placement — sensors will be auto-placed optimally.
            </p>
          )}
        </div>

        {/* Random Sensor Placement */}
        <button
          onClick={() => {
            const shuffled = [...injectableNodes]
              .sort(() => Math.random() - 0.5)
              .slice(0, numSensors)
              .map(n => n.id);
            setSelectedSensorNodes(shuffled);
            onSensorNodesChange(shuffled);
          }}
          className="btn btn-secondary w-full flex items-center justify-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Place {numSensors} Random Sensor{numSensors > 1 ? 's' : ''}
        </button>

        {/* Clear Sensors */}
        {selectedSensorNodes.length > 0 && (
          <button
            onClick={() => {
              setSelectedSensorNodes([]);
              onSensorNodesChange([]);
            }}
            className="btn btn-secondary w-full flex items-center justify-center gap-2 text-red-600 border-red-200 hover:bg-red-50"
          >
            <Trash2 className="w-4 h-4" />
            Clear All Sensors
          </button>
        )}
      </div>

      {/* ================================================================== */}
      {/* STEP 2: Leak Injection */}
      {/* ================================================================== */}
      <div className="pt-4 border-t border-slate-200 space-y-3">
        <h4 className="font-medium text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          Step 2: Inject Leaks
        </h4>
        
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

        {/* Leak Count Setting */}
        <div>
          <label className="label">Number of Leaks</label>
          <input
            type="number"
            value={numLeaks}
            onChange={(e) => handleNumLeaksChange(parseInt(e.target.value) || 1)}
            min={1}
            max={10}
            className="input w-full"
          />
        </div>

        {/* Manual Node Selection */}
        <div className="space-y-2">
          <label className="label">
            Manual Leak Injection
            <span className="text-slate-400 font-normal ml-2">
              ({selectedNodes.length}/{numLeaks} selected)
            </span>
          </label>
          <div className="relative">
            <input
              type="text"
              className="input w-full"
              placeholder={
                remainingSlots === 0 
                  ? `All ${numLeaks} slots filled` 
                  : `Type to search nodes (${remainingSlots} remaining)...`
              }
              value={leakSearchTerm}
              disabled={remainingSlots === 0}
              onChange={(e) => {
                setLeakSearchTerm(e.target.value);
                setShowLeakDropdown(true);
              }}
              onFocus={() => setShowLeakDropdown(true)}
              onBlur={() => {
                // Delay to allow click on dropdown item
                setTimeout(() => setShowLeakDropdown(false), 200);
              }}
            />
            {showLeakDropdown && remainingSlots > 0 && filteredLeakNodes.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-y-auto">
                {filteredLeakNodes.slice(0, 50).map(node => (
                  <button
                    key={node.id}
                    type="button"
                    className="w-full px-3 py-2 text-left text-sm hover:bg-amber-50 focus:bg-amber-50 focus:outline-none"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      handleNodeToggle(node.id);
                    }}
                  >
                    <span className="font-medium">{node.name}</span>
                    <span className="text-slate-400 ml-2">({node.node_type})</span>
                  </button>
                ))}
              </div>
            )}
          </div>

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

        {/* Random Leak Injection */}
        <button
          onClick={handleRandomLeaks}
          disabled={isInjecting}
          className="btn btn-secondary w-full flex items-center justify-center gap-2"
        >
          {isInjecting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Plus className="w-4 h-4" />
          )}
          Inject {numLeaks} Random Leak{numLeaks > 1 ? 's' : ''}
        </button>

        {/* Display active leak addresses */}
        {activeLeaks.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {activeLeaks.map(nodeId => {
              const node = network.nodes.find(n => n.id === nodeId);
              return (
                <span
                  key={nodeId}
                  className="badge bg-red-100 text-red-800 flex items-center gap-1"
                >
                  {node?.name || `Node ${nodeId}`}
                  <button
                    onClick={() => onInjectLeaks(activeLeaks.filter(id => id !== nodeId))}
                    className="hover:text-red-900"
                  >
                    ×
                  </button>
                </span>
              );
            })}
          </div>
        )}

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
      </div>

      {/* ================================================================== */}
      {/* STEP 3: Run Detection */}
      {/* ================================================================== */}
      <div className="pt-4 border-t border-slate-200 space-y-3">
        <h4 className="font-medium text-sm flex items-center gap-2">
          <Search className="w-4 h-4 text-green-600" />
          Step 3: Run Detection
        </h4>
        
        <button
          onClick={handleDetect}
          disabled={isDetecting || activeLeaks.length === 0}
          className="btn btn-primary w-full flex items-center justify-center gap-2 py-3 text-base"
        >
          {isDetecting ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Search className="w-5 h-5" />
          )}
          Run Detection Simulation
        </button>
        
        {activeLeaks.length === 0 && (
          <p className="text-xs text-amber-600 text-center">
            Inject leaks first before running detection.
          </p>
        )}
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
