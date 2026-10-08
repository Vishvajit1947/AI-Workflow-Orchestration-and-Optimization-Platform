/**
 * Frontend Phase 6 tests: formatting helpers, dashboard (KPIs, filters, empty state,
 * charts, table views, export), execution timeline and the executions page.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from '../src/pages/Dashboard';
import ExecutionsPage from '../src/pages/ExecutionsPage';
import { TimelineChart } from '../src/components/charts/TimelineChart';
import { dayLabelIndexes } from '../src/components/charts/chartKit';
import { analyticsApi } from '../src/api/analyticsApi';
import { executionApi } from '../src/api/executionApi';
import { workflowApi } from '../src/lib/workflows';
import { formatCompact, formatDuration, formatUSD, niceTicks } from '../src/lib/format';
import type { ExecutionTimeline, WorkflowMetrics } from '../src/types/analytics';

vi.mock('../src/api/analyticsApi', () => ({
  analyticsApi: {
    getOverview: vi.fn(), getCache: vi.fn(), getLatency: vi.fn(), getModels: vi.fn(),
    getStageTypes: vi.fn(), getRouting: vi.fn(), getCostTrend: vi.fn(), getTokenTrend: vi.fn(),
    getTimeline: vi.fn(), downloadExport: vi.fn(),
  },
}));
vi.mock('../src/api/executionApi', () => ({ executionApi: { listExecutions: vi.fn() } }));
vi.mock('../src/lib/workflows', () => ({ workflowApi: { list: vi.fn() } }));

const api = vi.mocked(analyticsApi);

const overview = (overrides: Partial<WorkflowMetrics> = {}): WorkflowMetrics => ({
  total_executions: 63, successful_executions: 56, execution_success_rate: 88.89, avg_execution_duration_ms: 4063,
  total_stages: 313, completed_stages: 306, failed_stages: 7, cancelled_stages: 0, llm_calls: 204, cache_hits: 102,
  total_tokens: 294361, total_cost: 0.8796, avg_latency_ms: 1405.8, success_rate: 97.76, failure_rate: 2.24,
  ...overrides,
});

const days = (n: number) => Array.from({ length: n }, (_, i) => `2026-09-${String(i + 1).padStart(2, '0')}`);

function mockDashboard(metrics = overview()) {
  api.getOverview.mockResolvedValue(metrics);
  api.getCache.mockResolvedValue({ valid_entries: 12, total_hits: 102, total_misses: 204, hit_rate: 33.33,
    total_tokens_saved: 145100, total_cost_saved: 0.293 });
  api.getLatency.mockResolvedValue({ sample_count: 204, min_ms: 345, max_ms: 3200, avg_ms: 1410,
    p50: 1250, p75: 1570, p90: 2590, p95: 2990, p99: 3150 });
  api.getModels.mockResolvedValue([
    { provider: 'gemini', model: 'gemini-2.0-flash-exp', usage_count: 97, share: 47.5, total_tokens: 1000, total_cost: 0, avg_latency_ms: 900 },
    { provider: 'anthropic', model: 'claude-sonnet-4-20250514', usage_count: 66, share: 32.4, total_tokens: 2000, total_cost: 0.7, avg_latency_ms: 1800 },
  ]);
  api.getStageTypes.mockResolvedValue([
    { stage_type: 'design', runs: 104, completed: 103, failed: 1, cache_hits: 34, cache_hit_rate: 32.7,
      avg_latency_ms: 1150, total_tokens: 98008, total_cost: 0.053 },
  ]);
  api.getRouting.mockResolvedValue({ total_decisions: 211, override_count: 17, override_rate: 8.06, fallback_count: 14,
    fallback_rate: 6.64, priority_distribution: { quality: 73 }, top_models: [{ model: 'gemini-2.0-flash-exp', decisions: 99 }] });
  api.getCostTrend.mockResolvedValue(days(30).map((date, i) => ({ date, cost: i % 3 ? 0.05 : 0, executions: 2, llm_calls: 6, cache_hits: 3 })));
  api.getTokenTrend.mockResolvedValue(days(30).map((date) => ({ date, input_tokens: 6000, output_tokens: 4000, total_tokens: 10000 })));
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(workflowApi.list).mockResolvedValue({
    items: [{ id: 'wf-1', name: 'Todo app generator' } as any], total: 1, skip: 0, limit: 100, has_more: false,
  });
});

// ---------- helpers ----------

describe('format helpers', () => {
  it('formats numbers, money and durations', () => {
    expect(formatCompact(1284)).toBe('1,284');
    expect(formatCompact(294361)).toBe('294.4K');
    expect(formatCompact(4_200_000)).toBe('4.2M');
    expect(formatUSD(0.8796)).toBe('$0.8796');
    expect(formatUSD(1234.5)).toBe('$1,234.50');
    expect(formatDuration(850)).toBe('850ms');
    expect(formatDuration(1405.8)).toBe('1.41s');
    expect(formatDuration(125_000)).toBe('2m 5s');
  });

  it('makes round axis ticks that cover the max', () => {
    expect(niceTicks(0.1103)).toEqual([0, 0.05, 0.1, 0.15]);
    expect(niceTicks(27000)).toEqual([0, 10000, 20000, 30000]);
    expect(niceTicks(0)).toEqual([0, 1]);
  });

  it('never crowds the last day label', () => {
    const picked = dayLabelIndexes(30, 420); // every 5th
    expect(picked.has(29)).toBe(true);
    expect(picked.has(25)).toBe(false);      // 4 days from the end: dropped
    expect(picked.has(20)).toBe(true);
  });
});

// ---------- dashboard ----------

describe('Dashboard', () => {
  it('shows KPI tiles and every section', async () => {
    mockDashboard();
    render(<MemoryRouter><Dashboard /></MemoryRouter>);

    expect(await screen.findByTestId('kpi-executions')).toHaveTextContent('63');
    expect(screen.getByTestId('kpi-success')).toHaveTextContent('88.9%');
    expect(screen.getByTestId('kpi-cost')).toHaveTextContent('$0.8796');
    expect(screen.getByTestId('kpi-tokens')).toHaveTextContent('294.4K');
    expect(screen.getByTestId('kpi-latency')).toHaveTextContent('1.41s');
    expect(screen.getByTestId('kpi-cache')).toHaveTextContent('33.3%');

    for (const title of ['Cost per day', 'Tokens per day', 'Model usage', 'LLM latency percentiles', 'Semantic cache', 'Routing', 'By stage type']) {
      expect(screen.getByRole('region', { name: title })).toBeInTheDocument();
    }
    expect(screen.getByTestId('latency-p95')).toHaveTextContent('2.99s');
    expect(screen.getByTestId('bar-gemini/gemini-2.0-flash-exp')).toHaveTextContent('97 · 48%');
    expect(screen.queryByTestId('dashboard-empty')).not.toBeInTheDocument();
  });

  it('requests data for the chosen range and workflow', async () => {
    mockDashboard();
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await screen.findByTestId('kpi-executions');
    const first = api.getOverview.mock.calls[0][0]!;
    expect(first.workflow_id).toBeUndefined();

    fireEvent.click(screen.getByRole('radio', { name: 'Last 7 days' }));
    await waitFor(() => expect(api.getOverview).toHaveBeenCalledTimes(2));
    const sevenDays = api.getOverview.mock.calls[1][0]!;
    const start = new Date(sevenDays.start_date!);
    expect(start.getUTCHours()).toBe(0);
    expect(Math.round((Date.now() - start.getTime()) / 86_400_000)).toBeLessThanOrEqual(7);
    expect(api.getCostTrend).toHaveBeenLastCalledWith(expect.objectContaining({ days: 7 }));

    await screen.findByRole('option', { name: 'Todo app generator' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Workflow' }), { target: { value: 'wf-1' } });
    await waitFor(() => expect(api.getOverview).toHaveBeenLastCalledWith(expect.objectContaining({ workflow_id: 'wf-1' })));
  });

  it('shows an empty state and empty charts when nothing ran', async () => {
    mockDashboard(overview({ total_executions: 0, total_stages: 0, llm_calls: 0, total_cost: 0, total_tokens: 0 }));
    api.getModels.mockResolvedValue([]);
    api.getCostTrend.mockResolvedValue(days(7).map((date) => ({ date, cost: 0, executions: 0, llm_calls: 0, cache_hits: 0 })));
    render(<MemoryRouter><Dashboard /></MemoryRouter>);

    expect(await screen.findByTestId('dashboard-empty')).toBeInTheDocument();
    expect(screen.getByText('No LLM spend in this range')).toBeInTheDocument();
    expect(screen.getAllByText('No LLM calls in this range').length).toBeGreaterThan(0);
    expect(screen.getByTestId('kpi-latency')).toHaveTextContent('—');
  });

  it('every chart has a table view', async () => {
    mockDashboard();
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    const tokens = await screen.findByRole('region', { name: 'Tokens per day' });
    fireEvent.click(within(tokens).getByRole('button', { name: /table/i }));
    expect(within(tokens).getByRole('columnheader', { name: 'Output' })).toBeInTheDocument();
    expect(within(tokens).getAllByText('10,000')).toHaveLength(30);

    const models = screen.getByRole('region', { name: 'Model usage' });
    fireEvent.click(within(models).getByRole('button', { name: /table/i }));
    expect(within(models).getByText('$0.7000')).toBeInTheDocument();
  });

  it('shows a tooltip when hovering a token column', async () => {
    mockDashboard();
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    const column = await screen.findByTestId('token-column-2026-09-05');
    fireEvent.pointerEnter(column.querySelector('rect[fill="transparent"]')!);
    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toHaveTextContent('Sep 5');
    expect(tooltip).toHaveTextContent('6,000input');
    expect(tooltip).toHaveTextContent('4,000output');
  });

  it('exports with the current filters', async () => {
    mockDashboard();
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await screen.findByTestId('kpi-executions');
    fireEvent.click(screen.getByRole('button', { name: /export/i }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Stage runs (CSV)' }));
    await waitFor(() => expect(api.downloadExport).toHaveBeenCalledWith(
      'csv', 'stage_runs', expect.objectContaining({ start_date: expect.any(String) })));
  });

  it('reports API failures', async () => {
    mockDashboard();
    api.getOverview.mockRejectedValue({ response: { data: { detail: 'database unavailable' } } });
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByText('Could not load analytics: database unavailable')).toBeInTheDocument();
  });
});

// ---------- timeline ----------

const timeline: ExecutionTimeline = {
  execution_id: 'e1', workflow_id: 'wf-1', started_at: null, completed_at: null, total_duration_ms: 3000, parallelism: 1.5,
  stages: [
    { stage_id: 's1', stage_name: 'Analyze', stage_order: 0, stage_type: 'analysis', status: 'completed', cache_hit: true,
      model_used: 'gpt-4o-mini', provider: 'cache', started_at: null, completed_at: null, start_offset_ms: 0, end_offset_ms: 5,
      duration_ms: 5, latency_ms: 0, estimated_cost: 0 },
    { stage_id: 's2', stage_name: 'Design API', stage_order: 1, stage_type: 'design', status: 'completed', cache_hit: false,
      model_used: 'gpt-4o', provider: 'openai', started_at: null, completed_at: null, start_offset_ms: 5, end_offset_ms: 1500,
      duration_ms: 1495, latency_ms: 1495, estimated_cost: 0.0075 },
    { stage_id: 's3', stage_name: 'Design DB', stage_order: 1, stage_type: 'design', status: 'failed', cache_hit: false,
      model_used: null, provider: null, started_at: null, completed_at: null, start_offset_ms: 5, end_offset_ms: 3000,
      duration_ms: 2995, latency_ms: null, estimated_cost: 0 },
  ],
};

describe('TimelineChart', () => {
  it('draws a labelled bar per stage run and reports overlap', () => {
    render(<TimelineChart timeline={timeline} />);
    expect(screen.getByText(/stages overlapped/)).toHaveTextContent('1.50x');
    expect(screen.getByTestId('gantt-row-2')).toHaveAttribute('data-status', 'failed');
    // Status is never color alone: legend carries icon + label
    expect(screen.getByText(/✕ Failed/)).toBeInTheDocument();
    expect(screen.getByText(/Cache hit/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Show table' }));
    expect(screen.getByText('cache hit')).toBeInTheDocument();
    expect(screen.getByText('$0.0075')).toBeInTheDocument();
  });

  it('says so when stages ran sequentially', () => {
    render(<TimelineChart timeline={{ ...timeline, parallelism: 1.0 }} />);
    expect(screen.getByText(/stages ran one after another/)).toBeInTheDocument();
  });
});

// ---------- executions page ----------

describe('ExecutionsPage', () => {
  it('lists executions and opens the one named in ?expand', async () => {
    vi.mocked(executionApi.listExecutions).mockResolvedValue([
      { execution_id: 'e1', workflow_id: 'wf-1', workflow_name: 'Todo app generator', status: 'completed',
        total_stages: 3, completed_stages: 3, started_at: '2026-09-27T10:00:00Z', completed_at: null, duration_ms: 3000, total_cost: 0.0075 },
    ]);
    api.getTimeline.mockResolvedValue(timeline);
    render(<MemoryRouter initialEntries={['/executions?expand=e1']}><ExecutionsPage /></MemoryRouter>);

    expect(await screen.findByText('Todo app generator')).toBeInTheDocument();
    expect(await screen.findByText(/stages overlapped/)).toBeInTheDocument();
    expect(api.getTimeline).toHaveBeenCalledWith('e1');
  });
});
