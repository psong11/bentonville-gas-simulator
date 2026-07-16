/**
 * NetworkMap Component
 * Street-true gas network over real Bentonville on MapLibre + deck.gl.
 *
 * Encoding:
 *  - Pipes: diverging color around the 300 kPa service threshold
 *    (warm = below threshold, neutral gray = at threshold, teal = healthy),
 *    width by road class (arterial > collector > local).
 *  - City gates: large amber dots. Leaks: pulsing red. Sensors: violet rings.
 *  - Flood overlay: FEMA SFHA (100yr) and 500yr zones, toggleable.
 */

import { useEffect, useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { PathLayer, ScatterplotLayer, GeoJsonLayer } from '@deck.gl/layers';
import type { PickingInfo } from '@deck.gl/core';
import { Map } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Network, SimulationState, Node, Pipe, LeakDetectionResult } from '../types';

interface AgentHighlight {
  node_ids?: number[];
  pipe_ids?: number[];
}

interface NetworkMapProps {
  network: Network;
  simulationState: SimulationState;
  sourcePressure: number;
  selectedPipeId: number | null;
  onPipeSelect: (pipeId: number | null) => void;
  activeLeaks: number[];
  detectionResult: LeakDetectionResult | null;
  sensorNodes: number[];
  agentHighlight?: AgentHighlight | null;
}

const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const INITIAL_VIEW = {
  longitude: -94.2088,
  latitude: 36.3729,
  zoom: 12.2,
  pitch: 0,
  bearing: 0,
};

// Diverging pressure ramp around the 300 kPa service threshold
const SERVICE_THRESHOLD_KPA = 300;
const P_LOW: [number, number, number] = [255, 107, 74]; // warm — below service
const P_MID: [number, number, number] = [154, 165, 177]; // neutral — at threshold
const P_HIGH: [number, number, number] = [45, 212, 191]; // teal — healthy

const COLOR_SOURCE: [number, number, number] = [255, 212, 59];
const COLOR_LEAK: [number, number, number] = [255, 82, 82];
const COLOR_SENSOR: [number, number, number] = [177, 151, 252];
const COLOR_DETECTED: [number, number, number] = [255, 169, 77];
const COLOR_NO_SIM: [number, number, number] = [120, 130, 140];

const PIPE_WIDTH: Record<string, number> = { arterial: 4, collector: 2.5, local: 1.4 };

const tooltipStyle = {
  backgroundColor: 'rgba(15, 23, 42, 0.92)',
  color: '#e2e8f0',
  fontSize: '12px',
  borderRadius: '6px',
  padding: '8px 10px',
  maxWidth: '260px',
};

function lerp(a: [number, number, number], b: [number, number, number], t: number) {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ] as [number, number, number];
}

function pressureColor(kPa: number, sourcePressure: number): [number, number, number] {
  if (kPa <= SERVICE_THRESHOLD_KPA) {
    const t = Math.max(0, Math.min(1, (kPa - 200) / (SERVICE_THRESHOLD_KPA - 200)));
    return lerp(P_LOW, P_MID, t);
  }
  const top = Math.max(sourcePressure, 340);
  const t = Math.max(0, Math.min(1, (kPa - SERVICE_THRESHOLD_KPA) / (top - SERVICE_THRESHOLD_KPA)));
  return lerp(P_MID, P_HIGH, t);
}

export function NetworkMap({
  network,
  simulationState,
  sourcePressure,
  selectedPipeId,
  onPipeSelect,
  activeLeaks,
  detectionResult,
  sensorNodes,
  agentHighlight,
}: NetworkMapProps) {
  const [showFlood, setShowFlood] = useState(false);
  const [flood, setFlood] = useState<GeoJSON.FeatureCollection | null>(null);
  const [pulse, setPulse] = useState(1);

  // Load the static flood overlay lazily on first toggle
  useEffect(() => {
    if (showFlood && !flood) {
      fetch('/overlays/flood.geojson')
        .then((r) => r.json())
        .then(setFlood)
        .catch(() => setFlood(null));
    }
  }, [showFlood, flood]);

  // Pulse animation while leaks are active
  const hasLeaks = activeLeaks.length > 0;
  useEffect(() => {
    if (!hasLeaks) return;
    const id = setInterval(
      () => setPulse(1 + 0.5 * Math.abs(Math.sin(Date.now() / 350))),
      70,
    );
    return () => clearInterval(id);
  }, [hasLeaks]);

  const nodeById = useMemo(() => {
    const dict = new globalThis.Map<number, Node>();
    network.nodes.forEach((n) => dict.set(n.id, n));
    return dict;
  }, [network.nodes]);

  const pressures = simulationState.node_pressures;
  const hasSim = Object.keys(pressures).length > 0;

  const pipePressure = useMemo(() => {
    const p = new globalThis.Map<number, number>();
    for (const pipe of network.pipes) {
      const a = pressures[pipe.source_id];
      const b = pressures[pipe.target_id];
      p.set(pipe.id, a !== undefined && b !== undefined ? (a + b) / 2 : sourcePressure);
    }
    return p;
  }, [network.pipes, pressures, sourcePressure]);

  const getPipePath = (pipe: Pipe): [number, number][] => {
    if (pipe.path && pipe.path.length >= 2) return pipe.path;
    const a = nodeById.get(pipe.source_id);
    const b = nodeById.get(pipe.target_id);
    return a && b ? [[a.x, a.y], [b.x, b.y]] : [];
  };

  const consumers = useMemo(
    () => network.nodes.filter((n) => n.node_type !== 'source'),
    [network.nodes],
  );
  const sources = useMemo(
    () => network.nodes.filter((n) => n.node_type === 'source'),
    [network.nodes],
  );
  const leakSet = useMemo(() => new Set(activeLeaks), [activeLeaks]);
  const leakNodes = useMemo(
    () => network.nodes.filter((n) => leakSet.has(n.id)),
    [network.nodes, leakSet],
  );
  const sensorSet = useMemo(() => new Set(sensorNodes), [sensorNodes]);
  const sensorNodeObjs = useMemo(
    () => network.nodes.filter((n) => sensorSet.has(n.id)),
    [network.nodes, sensorSet],
  );
  const detectedNodes = useMemo(() => {
    const ids = new Set(detectionResult?.detected_leaks ?? []);
    return network.nodes.filter((n) => ids.has(n.id));
  }, [network.nodes, detectionResult]);

  const agentPipes = useMemo(() => {
    const ids = new Set(agentHighlight?.pipe_ids ?? []);
    return network.pipes.filter((p) => ids.has(p.id));
  }, [network.pipes, agentHighlight]);
  const agentNodes = useMemo(() => {
    const ids = new Set(agentHighlight?.node_ids ?? []);
    return network.nodes.filter((n) => ids.has(n.id));
  }, [network.nodes, agentHighlight]);

  const layers = [
    showFlood &&
      flood &&
      new GeoJsonLayer({
        id: 'flood',
        data: flood,
        stroked: true,
        filled: true,
        getFillColor: (f) =>
          (f.properties as { zone?: string }).zone === '100yr'
            ? [77, 171, 247, 55]
            : [77, 171, 247, 30],
        getLineColor: [77, 171, 247, 90],
        getLineWidth: 1,
        lineWidthUnits: 'pixels' as const,
        pickable: false,
      }),
    new PathLayer<Pipe>({
      id: 'pipes',
      data: network.pipes,
      getPath: getPipePath,
      getColor: (p) =>
        hasSim
          ? pressureColor(pipePressure.get(p.id) ?? sourcePressure, sourcePressure)
          : COLOR_NO_SIM,
      getWidth: (p) => PIPE_WIDTH[p.road_class ?? 'local'] ?? 1.4,
      widthUnits: 'pixels',
      widthMinPixels: 1,
      capRounded: true,
      jointRounded: true,
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 120],
      onClick: (info: PickingInfo<Pipe>) =>
        onPipeSelect(info.object ? info.object.id : null),
      updateTriggers: {
        getColor: [pipePressure, hasSim, sourcePressure],
      },
    }),
    selectedPipeId !== null &&
      new PathLayer<Pipe>({
        id: 'selected-pipe',
        data: network.pipes.filter((p) => p.id === selectedPipeId),
        getPath: getPipePath,
        getColor: [255, 255, 255] as [number, number, number],
        getWidth: (p) => (PIPE_WIDTH[p.road_class ?? 'local'] ?? 1.4) + 2.5,
        widthUnits: 'pixels' as const,
        capRounded: true,
        pickable: false,
      }),
    new ScatterplotLayer<Node>({
      id: 'consumers',
      data: consumers,
      getPosition: (n) => [n.x, n.y],
      getRadius: 14,
      radiusUnits: 'meters',
      radiusMinPixels: 1.2,
      radiusMaxPixels: 5,
      getFillColor: (n) =>
        hasSim && pressures[n.id] !== undefined
          ? pressureColor(pressures[n.id], sourcePressure)
          : COLOR_NO_SIM,
      pickable: true,
      updateTriggers: { getFillColor: [pressures, hasSim, sourcePressure] },
    }),
    new ScatterplotLayer<Node>({
      id: 'sensors',
      data: sensorNodeObjs,
      getPosition: (n) => [n.x, n.y],
      getRadius: 55,
      radiusUnits: 'meters',
      radiusMinPixels: 6,
      stroked: true,
      filled: false,
      getLineColor: COLOR_SENSOR,
      getLineWidth: 3,
      lineWidthUnits: 'pixels',
      pickable: true,
    }),
    new ScatterplotLayer<Node>({
      id: 'detected-leaks',
      data: detectedNodes,
      getPosition: (n) => [n.x, n.y],
      getRadius: 75,
      radiusUnits: 'meters',
      radiusMinPixels: 8,
      stroked: true,
      filled: false,
      getLineColor: COLOR_DETECTED,
      getLineWidth: 2.5,
      lineWidthUnits: 'pixels',
      pickable: true,
    }),
    new ScatterplotLayer<Node>({
      id: 'leaks',
      data: leakNodes,
      getPosition: (n) => [n.x, n.y],
      getRadius: 45 * pulse,
      radiusUnits: 'meters',
      radiusMinPixels: 5,
      getFillColor: [...COLOR_LEAK, 200] as [number, number, number, number],
      stroked: true,
      getLineColor: [255, 255, 255, 180],
      getLineWidth: 1.5,
      lineWidthUnits: 'pixels',
      pickable: true,
      updateTriggers: { getRadius: [pulse] },
    }),
    agentPipes.length > 0 &&
      new PathLayer<Pipe>({
        id: 'agent-pipes',
        data: agentPipes,
        getPath: getPipePath,
        getColor: [255, 255, 255, Math.round(140 + 90 * Math.abs(Math.sin(Date.now() / 400)))] as [number, number, number, number],
        getWidth: (p) => (PIPE_WIDTH[p.road_class ?? 'local'] ?? 1.4) + 3.5,
        widthUnits: 'pixels' as const,
        capRounded: true,
        pickable: false,
      }),
    agentNodes.length > 0 &&
      new ScatterplotLayer<Node>({
        id: 'agent-nodes',
        data: agentNodes,
        getPosition: (n) => [n.x, n.y],
        getRadius: 85,
        radiusUnits: 'meters' as const,
        radiusMinPixels: 9,
        stroked: true,
        filled: false,
        getLineColor: [255, 255, 255, 230] as [number, number, number, number],
        getLineWidth: 3,
        lineWidthUnits: 'pixels' as const,
        pickable: false,
      }),
    new ScatterplotLayer<Node>({
      id: 'sources',
      data: sources,
      getPosition: (n) => [n.x, n.y],
      getRadius: 110,
      radiusUnits: 'meters',
      radiusMinPixels: 9,
      getFillColor: [...COLOR_SOURCE, 230] as [number, number, number, number],
      stroked: true,
      getLineColor: [30, 30, 30, 255],
      getLineWidth: 2,
      lineWidthUnits: 'pixels',
      pickable: true,
    }),
  ].filter(Boolean);

  const getTooltip = ({ object, layer }: PickingInfo) => {
    if (!object) return null;
    if (layer?.id === 'pipes') {
      const p = object as Pipe;
      const kPa = pipePressure.get(p.id);
      return {
        html: `
          <div style="font-weight:600;margin-bottom:2px">${p.street ?? 'Pipe'} <span style="opacity:.6">#${p.id}</span></div>
          <div>${p.road_class ?? ''} · ${p.material} · ${p.year_installed}</div>
          <div>${(p.length / 1000).toFixed(2)} km · Ø ${(p.diameter * 1000).toFixed(0)} mm</div>
          ${hasSim && kPa !== undefined ? `<div>avg pressure ${kPa.toFixed(1)} kPa</div>` : ''}
          ${p.flood_zone ? `<div style="color:#4dabf7">⚠ FEMA ${p.flood_zone} flood zone</div>` : ''}
        `,
        style: tooltipStyle,
      };
    }
    const n = object as Node;
    const kPa = pressures[n.id];
    return {
      html: `
        <div style="font-weight:600;margin-bottom:2px">${n.name}</div>
        <div>${n.node_type}${n.land_use ? ` · ${n.land_use}` : ''}</div>
        <div>demand ${n.base_demand.toFixed(1)} m³/h${
          n.n_addresses ? ` · ${n.n_addresses} addresses nearby` : ''
        }</div>
        ${kPa !== undefined ? `<div>pressure ${kPa.toFixed(1)} kPa</div>` : ''}
      `,
      style: tooltipStyle,
    };
  };

  return (
    <div className="relative w-full h-full min-h-[400px] rounded-lg overflow-hidden">
      <DeckGL
        initialViewState={INITIAL_VIEW}
        controller={true}
        layers={layers}
        getTooltip={getTooltip}
        onClick={(info) => {
          if (!info.object) onPipeSelect(null);
        }}
      >
        <Map mapStyle={BASEMAP} reuseMaps attributionControl={false} />
      </DeckGL>

      {/* Layer controls */}
      <div className="absolute top-3 left-3 flex gap-2">
        <button
          onClick={() => setShowFlood((v) => !v)}
          className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
            showFlood
              ? 'bg-blue-500/20 border-blue-400/60 text-blue-100'
              : 'bg-slate-900/70 border-slate-600 text-slate-300 hover:border-slate-400'
          }`}
        >
          FEMA flood zones
        </button>
      </div>

      {/* Pressure legend */}
      <div className="absolute bottom-3 left-3 bg-slate-900/80 rounded-md px-3 py-2 text-[11px] text-slate-200">
        <div className="font-medium mb-1">Pressure (kPa)</div>
        <div
          className="h-2 w-36 rounded-sm"
          style={{
            background:
              'linear-gradient(to right, rgb(255,107,74), rgb(154,165,177) 45%, rgb(45,212,191))',
          }}
        />
        <div className="flex justify-between mt-0.5 text-slate-400">
          <span>200</span>
          <span>300</span>
          <span>{Math.max(sourcePressure, 340).toFixed(0)}</span>
        </div>
        <div className="mt-1.5 flex flex-col gap-0.5 text-slate-300">
          <span>
            <span style={{ color: 'rgb(255,212,59)' }}>●</span> city gate (approx.)
          </span>
          {hasLeaks && (
            <span>
              <span style={{ color: 'rgb(255,82,82)' }}>●</span> active leak
            </span>
          )}
          {sensorNodes.length > 0 && (
            <span>
              <span style={{ color: 'rgb(177,151,252)' }}>○</span> sensor
            </span>
          )}
          {((agentHighlight?.pipe_ids?.length ?? 0) > 0 || (agentHighlight?.node_ids?.length ?? 0) > 0) && (
            <span>
              <span style={{ color: 'rgb(255,255,255)' }}>○</span> cited by assistant
            </span>
          )}
        </div>
      </div>

      {/* Data provenance */}
      <div className="absolute bottom-3 right-3 bg-slate-900/70 rounded px-2 py-1 text-[10px] text-slate-400 max-w-[300px] text-right">
        Streets, land use &amp; FEMA zones: City of Bentonville GIS. Network is
        synthetic &amp; street-true — not utility as-builts.
      </div>
    </div>
  );
}
