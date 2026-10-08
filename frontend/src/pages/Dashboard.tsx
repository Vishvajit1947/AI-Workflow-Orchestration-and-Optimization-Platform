/**
 * Analytics dashboard: one filter row (date range + workflow) scoping everything
 * below it, headline stat tiles, trend charts, model/latency/cache breakdowns,
 * per-stage-type table and routing effectiveness.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity, CheckCircle2, Coins, Database, Gauge, Hash, RefreshCw,
} from 'lucide-react';
import { analyticsApi } from '../api/analyticsApi';
import { workflowApi } from '../lib/workflows';
import type {
  AnalyticsFilters, CacheMetrics, CostTrendPoint, LatencyMetrics, ModelUtilization,
  RoutingEffectiveness, StageTypeMetrics, TokenTrendPoint, WorkflowMetrics,
} from '../types/analytics';
import type { WorkflowListItem } from '../types';
import { formatCompact, formatDuration, formatPercent, formatUSD } from '../lib/format';
import { MetricCard, MetricGrid } from '../components/metrics/MetricCard';
import { CostChart } from '../components/charts/CostChart';
import { TokenChart } from '../components/charts/TokenChart';
import { LatencyChart } from '../components/charts/LatencyChart';
import { CacheMeter } from '../components/charts/CacheMeter';
import { BarList } from '../components/charts/BarList';
import { CHART, ChartCard, DataTable } from '../components/charts/chartKit';
import { ExportButton } from '../components/analytics/ExportButton';

const RANGES = [
  { days: 7, label: 'Last 7 days' },
  { days: 30, label: 'Last 30 days' },
  { days: 90, label: 'Last 90 days' },
];

interface DashboardData {
  overview: WorkflowMetrics;
  cache: CacheMetrics;
  latency: LatencyMetrics;
  models: ModelUtilization[];
  stageTypes: StageTypeMetrics[];
  routing: RoutingEffectiveness;
  costs: CostTrendPoint[];
  tokens: TokenTrendPoint[];
}

/** Filters for "the last N days": start at 00:00 UTC N-1 days ago so KPIs and daily trends cover the same days. */
export const rangeFilters = (days: number, workflowId: string): AnalyticsFilters & { days: number } => {
  const start = new Date();
  start.setUTCHours(0, 0, 0, 0);
  start.setUTCDate(start.getUTCDate() - (days - 1));
  return { start_date: start.toISOString(), workflow_id: workflowId || undefined, days };
};

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const [workflowId, setWorkflowId] = useState('');
  const [workflows, setWorkflows] = useState<WorkflowListItem[]>([]);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filters = useMemo(() => rangeFilters(days, workflowId), [days, workflowId]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [overview, cache, latency, models, stageTypes, routing, costs, tokens] = await Promise.all([
        analyticsApi.getOverview(filters),
        analyticsApi.getCache(filters),
        analyticsApi.getLatency(filters),
        analyticsApi.getModels(filters),
        analyticsApi.getStageTypes(filters),
        analyticsApi.getRouting(filters),
        analyticsApi.getCostTrend(filters),
        analyticsApi.getTokenTrend(filters),
      ]);
      setData({ overview, cache, latency, models, stageTypes, routing, costs, tokens });
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    workflowApi.list(0, 100)
      .then((page) => setWorkflows(page.items))
      .catch(() => { /* filter just lists fewer options */ });
  }, []);

  const exportFilters: AnalyticsFilters = { start_date: filters.start_date, workflow_id: filters.workflow_id };
  const o = data?.overview;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-surface-200/50 mt-1">Cost, speed and reliability of workflow executions</p>
        </div>
      </div>

      {/* One filter row scoping everything below */}
      <div className="flex flex-wrap items-center gap-3 mb-6" role="group" aria-label="Dashboard filters">
        <div className="flex rounded-lg bg-surface-800/60 p-1" role="radiogroup" aria-label="Date range">
          {RANGES.map((r) => (
            <button key={r.days} role="radio" aria-checked={days === r.days} onClick={() => setDays(r.days)}
                    className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                      days === r.days ? 'bg-primary-500/20 text-white font-medium' : 'text-surface-200/60 hover:text-white'}`}>
              {r.label}
            </button>
          ))}
        </div>
        <select aria-label="Workflow" value={workflowId} onChange={(e) => setWorkflowId(e.target.value)}
                className="px-3 py-2 bg-surface-800/50 border border-surface-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-primary-500/50">
          <option value="">All workflows</option>
          {workflows.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
        <div className="flex gap-2 ml-auto">
          <button onClick={load} disabled={loading}
                  className="flex items-center gap-1.5 px-3 py-2 bg-surface-700/50 hover:bg-surface-700 rounded-lg text-sm transition-colors disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          <ExportButton filters={exportFilters} />
        </div>
      </div>

      {error && <p className="text-red-400 mb-6">Could not load analytics: {error}</p>}
      {!data && loading && <p className="text-surface-200/50">Loading analytics…</p>}

      {data && o && (
        // Refetch keeps the previous render, dimmed: no skeleton flash, no layout jump
        <div className={`space-y-6 transition-opacity ${loading ? 'opacity-60' : ''}`} aria-busy={loading}>
          {o.total_executions === 0 && (
            <div className="glass rounded-xl p-6 text-sm text-surface-200/60" data-testid="dashboard-empty">
              No executions in this range{workflowId ? ' for this workflow' : ''}. Run a workflow to see its cost, speed and cache savings here.
            </div>
          )}

          <MetricGrid>
            <MetricCard testId="kpi-executions" icon={Activity} label="Executions" value={formatCompact(o.total_executions)}
              detail={`${o.total_stages.toLocaleString()} stage runs`} />
            <MetricCard testId="kpi-success" icon={CheckCircle2} label="Execution success"
              value={o.total_executions ? formatPercent(o.execution_success_rate) : '—'}
              detail={`${o.failed_stages} failed · ${o.cancelled_stages} cancelled stages`} />
            <MetricCard testId="kpi-cost" icon={Coins} label="LLM cost" value={formatUSD(o.total_cost)}
              detail={o.llm_calls ? `${formatUSD(o.total_cost / o.llm_calls)} per call` : 'no LLM calls'} />
            <MetricCard testId="kpi-tokens" icon={Hash} label="Tokens" value={formatCompact(o.total_tokens)}
              detail={`${o.llm_calls.toLocaleString()} LLM calls`} />
            <MetricCard testId="kpi-latency" icon={Gauge} label="Avg LLM latency"
              value={o.llm_calls ? formatDuration(o.avg_latency_ms) : '—'}
              detail={o.total_executions ? `${formatDuration(o.avg_execution_duration_ms)} per execution` : undefined} />
            <MetricCard testId="kpi-cache" icon={Database} label="Cache hit rate" value={formatPercent(data.cache.hit_rate)}
              detail={`${formatUSD(data.cache.total_cost_saved)} saved`} />
          </MetricGrid>

          <div className="grid lg:grid-cols-2 gap-6">
            <CostChart data={data.costs} />
            <TokenChart data={data.tokens} />
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <ChartCard
              title="Model usage"
              subtitle="LLM calls per model (cache hits excluded)"
              empty={data.models.length === 0}
              emptyText="No LLM calls in this range"
              table={<DataTable headers={['Model', 'Provider', 'Calls', 'Share', 'Tokens', 'Cost', 'Avg latency']}
                align={['left', 'left']}
                rows={data.models.map((m) => [m.model, m.provider, m.usage_count, formatPercent(m.share),
                  m.total_tokens.toLocaleString(), formatUSD(m.total_cost), formatDuration(m.avg_latency_ms)])} />}
            >
              <BarList ariaLabel="LLM calls per model" data={data.models.map((m) => ({
                key: `${m.provider}/${m.model}`,
                label: m.model,
                value: m.usage_count,
                display: `${m.usage_count} · ${formatPercent(m.share, 0)}`,
                tooltip: [
                  { label: 'calls', value: m.usage_count.toLocaleString(), color: CHART.series1 },
                  { label: 'cost', value: formatUSD(m.total_cost) },
                  { label: 'tokens', value: m.total_tokens.toLocaleString() },
                  { label: 'avg latency', value: formatDuration(m.avg_latency_ms) },
                  { label: 'provider', value: m.provider },
                ],
              }))} />
            </ChartCard>
            <LatencyChart data={data.latency} />
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <CacheMeter data={data.cache} />
            <RoutingCard routing={data.routing} />
          </div>

          <ChartCard title="By stage type" subtitle="Where time, money and cache hits go" empty={data.stageTypes.length === 0}>
            <DataTable
              headers={['Stage type', 'Runs', 'Completed', 'Failed', 'Cache hit rate', 'Avg LLM latency', 'Tokens', 'Cost']}
              align={['left']}
              rows={data.stageTypes.map((s) => [s.stage_type, s.runs, s.completed, s.failed, formatPercent(s.cache_hit_rate),
                s.avg_latency_ms ? formatDuration(s.avg_latency_ms) : '—', s.total_tokens.toLocaleString(), formatUSD(s.total_cost)])}
            />
          </ChartCard>
        </div>
      )}
    </div>
  );
}

function RoutingCard({ routing }: { routing: RoutingEffectiveness }) {
  const priorities = Object.entries(routing.priority_distribution);
  return (
    <ChartCard
      title="Routing"
      subtitle={`${routing.total_decisions.toLocaleString()} routing decisions`}
      empty={routing.total_decisions === 0}
      emptyText="No routing decisions in this range"
      table={<DataTable headers={['Model', 'Times selected']} align={['left']}
        rows={routing.top_models.map((m) => [m.model, m.decisions])} />}
    >
      <dl className="grid grid-cols-2 gap-3 mb-4 text-sm">
        <div>
          <dt className="text-xs text-surface-200/50">User overrides</dt>
          <dd className="font-semibold mt-0.5">{formatPercent(routing.override_rate)} <span className="text-xs font-normal text-surface-200/50">({routing.override_count})</span></dd>
        </div>
        <div>
          <dt className="text-xs text-surface-200/50">Fallbacks</dt>
          <dd className="font-semibold mt-0.5">{formatPercent(routing.fallback_rate)} <span className="text-xs font-normal text-surface-200/50">({routing.fallback_count})</span></dd>
        </div>
      </dl>
      <p className="text-xs text-surface-200/50 mb-1">Most selected models</p>
      <BarList ariaLabel="Routing decisions per selected model" data={routing.top_models.map((m) => ({
        key: m.model, label: m.model, value: m.decisions, display: String(m.decisions),
        tooltip: [{ label: 'selections', value: String(m.decisions), color: CHART.series1 }],
      }))} />
      {priorities.length > 0 && (
        <p className="text-xs text-surface-200/50 mt-3">
          Priority used: {priorities.map(([p, n]) => `${p} ${n}`).join(' · ')}
        </p>
      )}
    </ChartCard>
  );
}
