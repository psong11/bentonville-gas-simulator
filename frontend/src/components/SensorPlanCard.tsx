/**
 * SensorPlanCard
 * Physics-based sensor planning: greedy submodular max-coverage over the
 * leak-signature matrix. Shows the marginal-gain curve (what each extra
 * sensor buys) against a random-placement baseline, and applies the chosen
 * plan to the map.
 */

import { useEffect, useRef, useState } from 'react';
import Plot from 'react-plotly.js';
import { Radar } from 'lucide-react';

interface CurvePoint {
  k: number;
  coverage_pct: number;
  node_id: number;
}

interface SensorPlan {
  sensors: { node_id: number; street: string }[];
  coverage_pct: number;
  baseline_random_pct: number;
  ceiling_pct: number;
  scenario_count: number;
  threshold_kpa: number;
  curve: CurvePoint[];
  sensor_node_ids: number[];
}

interface SensorPlanCardProps {
  onApply: (nodeIds: number[]) => void;
}

export function SensorPlanCard({ onApply }: SensorPlanCardProps) {
  const [budget, setBudget] = useState(8);
  const [plan, setPlan] = useState<SensorPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<number>(0);

  useEffect(() => {
    window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(async () => {
      setLoading(true);
      try {
        const resp = await fetch('/api/sensors/plan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ num_sensors: budget }),
        });
        if (!resp.ok) {
          const detail = await resp.json().catch(() => null);
          throw new Error(detail?.detail ?? `Request failed (${resp.status})`);
        }
        setPlan(await resp.json());
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Request failed');
      } finally {
        setLoading(false);
      }
    }, 350);
    return () => window.clearTimeout(debounceRef.current);
  }, [budget]);

  const last = plan?.curve[plan.curve.length - 1];

  return (
    <div className="card bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center gap-2 mb-1">
        <Radar className="w-4 h-4 text-teal-600" />
        <h2 className="font-semibold text-slate-900">Sensor Planning</h2>
      </div>
      <p className="text-xs text-slate-500 mb-3">
        Greedy submodular coverage over {plan?.scenario_count ?? 200} simulated leak
        scenarios (detection floor {plan?.threshold_kpa ?? 2} kPa). Each point = value
        of one more sensor.
      </p>

      <label className="text-sm text-slate-700 flex items-center gap-3">
        Budget: <strong className="tabular-nums">{budget}</strong> sensors
        <input
          type="range"
          min={1}
          max={25}
          value={budget}
          onChange={(e) => setBudget(Number(e.target.value))}
          className="flex-1 h-2 accent-teal-600 cursor-pointer"
        />
      </label>

      {error ? (
        <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3 mt-3">
          {error}
        </div>
      ) : (
        <>
          <Plot
            data={[
              {
                x: plan?.curve.map((c) => c.k) ?? [],
                y: plan?.curve.map((c) => c.coverage_pct) ?? [],
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Optimized',
                line: { color: '#0d9488', width: 2.5 },
                marker: { size: 6 },
                hovertemplate: '%{x} sensors → %{y:.1f}%<extra></extra>',
              },
              {
                x: plan ? plan.curve.map((c) => c.k) : [],
                y: plan
                  ? plan.curve.map((c) => (plan.baseline_random_pct / budget) * c.k)
                  : [],
                type: 'scatter',
                mode: 'lines',
                name: 'Random (avg)',
                line: { color: '#94a3b8', width: 1.5, dash: 'dot' },
                hoverinfo: 'skip',
              },
            ]}
            layout={{
              height: 220,
              margin: { l: 42, r: 12, t: 8, b: 34 },
              xaxis: { title: { text: 'Sensors', font: { size: 11 } }, dtick: budget > 12 ? 4 : 2 },
              yaxis: { title: { text: '% scenarios detected', font: { size: 11 } }, range: [0, 100] },
              legend: { orientation: 'h', y: -0.25, font: { size: 10 } },
              annotations: last
                ? [{
                    x: last.k,
                    y: last.coverage_pct,
                    text: `<b>${last.k} → ${last.coverage_pct.toFixed(0)}%</b>`,
                    showarrow: true,
                    arrowhead: 2,
                    ax: -34,
                    ay: 18,
                    font: { size: 11, color: '#0d9488' },
                  }]
                : [],
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%' }}
          />
          <div className="flex items-center justify-between mt-1">
            <span className="text-sm text-slate-600">
              {plan
                ? `${budget} sensors detect ${plan.coverage_pct.toFixed(0)}% of leak scenarios (random: ${plan.baseline_random_pct.toFixed(0)}%)`
                : 'Computing…'}
            </span>
            <button
              onClick={() => plan && onApply(plan.sensor_node_ids)}
              disabled={!plan || loading}
              className="btn btn-primary text-sm px-3 py-1.5 disabled:opacity-50"
            >
              Apply to map
            </button>
          </div>
        </>
      )}
    </div>
  );
}
