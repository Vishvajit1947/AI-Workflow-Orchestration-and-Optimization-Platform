/**
 * Frontend cache UI tests: Cache dashboard, cache indicators in execution
 * results, and the execute modal's cache toggle.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import CacheDashboard from '../src/pages/CacheDashboard';
import { ExecutionResults } from '../src/components/ExecutionResults';
import { ExecutionConfigModal } from '../src/components/ExecutionConfigModal';
import { cacheApi } from '../src/api/cacheApi';
import type { CacheEntry, CacheStats } from '../src/types/cache';
import type { ExecutionDetailResponse } from '../src/types/execution';

vi.mock('../src/api/cacheApi', () => ({
  cacheApi: {
    listEntries: vi.fn(),
    getStats: vi.fn(),
    deleteEntry: vi.fn(),
    clearCache: vi.fn(),
    cleanupExpired: vi.fn(),
    getWorkflowHitRate: vi.fn(),
  },
}));

const api = vi.mocked(cacheApi);

const mockStats: CacheStats = {
  total_entries: 50,
  total_hits: 200,
  hit_rate: 0.8,
  total_tokens_saved: 10000,
  total_cost_saved: '0.010000', // Decimal arrives as a string from the API
  avg_similarity_score: 0.95,
};

const makeEntry = (overrides: Partial<CacheEntry> = {}): CacheEntry => ({
  id: 'entry-1',
  workflow_id: 'wf-1',
  stage_id: 'stage-1',
  stage_type: 'analysis',
  input_text: 'Test input 1',
  result: 'Test result 1',
  result_tokens: 100,
  model_used: 'gpt-4o-mini',
  hit_count: 5,
  similarity_score: null,
  is_valid: true,
  created_at: '2024-01-01T00:00:00Z',
  expires_at: null,
  ...overrides,
});

const mockEntries: CacheEntry[] = [
  makeEntry(),
  makeEntry({
    id: 'entry-2', stage_type: 'design', input_text: 'Design the database schema',
    result: 'Tables: users, tasks', model_used: 'claude-3-5-haiku', hit_count: 0, is_valid: false,
  }),
  makeEntry({
    id: 'entry-3', stage_type: 'generation', input_text: 'Generate the REST endpoints',
    result: 'GET /tasks', hit_count: 2, expires_at: '2000-01-01T00:00:00Z',
  }),
];

// ============================================================================
// Cache Dashboard
// ============================================================================

describe('CacheDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getStats.mockResolvedValue(mockStats);
    api.listEntries.mockResolvedValue(mockEntries);
    window.confirm = vi.fn(() => true);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders cache statistics', async () => {
    render(<CacheDashboard />);

    expect(await screen.findByText('50')).toBeInTheDocument();            // valid entries
    expect(screen.getByText('200')).toBeInTheDocument();                  // hits
    expect(screen.getAllByText('80.0%').length).toBeGreaterThanOrEqual(1); // hit rate (card + chart)
    expect(screen.getByText('10,000')).toBeInTheDocument();               // tokens saved
    expect(screen.getByText('$0.0100 saved')).toBeInTheDocument();        // Decimal string formatted
    expect(screen.getByText('Avg similarity 95.0%')).toBeInTheDocument();
  });

  it('displays cache entries table with status badges', async () => {
    render(<CacheDashboard />);

    const row1 = (await screen.findByText('Test input 1')).closest('tr')!;
    expect(within(row1).getByText('analysis')).toBeInTheDocument();
    expect(within(row1).getByText('gpt-4o-mini')).toBeInTheDocument();
    expect(within(row1).getByText('5')).toBeInTheDocument();
    expect(within(row1).getByText('valid')).toBeInTheDocument();

    const row2 = screen.getByText('Design the database schema').closest('tr')!;
    expect(within(row2).getByText('invalid')).toBeInTheDocument();

    const row3 = screen.getByText('Generate the REST endpoints').closest('tr')!;
    expect(within(row3).getByText('expired')).toBeInTheDocument();
  });

  it('shows empty state when there are no entries', async () => {
    api.listEntries.mockResolvedValue([]);
    render(<CacheDashboard />);
    expect(await screen.findByText('No cache entries found')).toBeInTheDocument();
  });

  it('shows an error when the API fails', async () => {
    api.getStats.mockRejectedValue(new Error('Network Error'));
    render(<CacheDashboard />);
    expect(await screen.findByText('Error: Network Error')).toBeInTheDocument();
  });

  it('expands a row to show full input and cached output', async () => {
    render(<CacheDashboard />);
    fireEvent.click(await screen.findByText('Design the database schema'));

    expect(screen.getByText('Cached Output')).toBeInTheDocument();
    expect(screen.getByText('Tables: users, tasks')).toBeInTheDocument();
    expect(screen.getByText(/ID entry-2/)).toBeInTheDocument();
  });

  it('filters by stage type via the API and resets to the first page', async () => {
    render(<CacheDashboard />);
    await screen.findByText('Test input 1');

    fireEvent.change(screen.getByDisplayValue('All stage types'), { target: { value: 'design' } });

    await waitFor(() => {
      expect(api.listEntries).toHaveBeenLastCalledWith(
        expect.objectContaining({ stage_type: 'design', offset: 0 })
      );
    });
  });

  it('filters by validity via the API', async () => {
    render(<CacheDashboard />);
    await screen.findByText('Test input 1');

    fireEvent.change(screen.getByDisplayValue('All entries'), { target: { value: 'false' } });

    await waitFor(() => {
      expect(api.listEntries).toHaveBeenLastCalledWith(expect.objectContaining({ is_valid: false }));
    });
  });

  it('searches entries on the current page by input, output or model', async () => {
    render(<CacheDashboard />);
    await screen.findByText('Test input 1');

    const search = screen.getByPlaceholderText(/Search input, output or model/);
    fireEvent.change(search, { target: { value: 'claude' } });

    expect(screen.getByText('Design the database schema')).toBeInTheDocument();
    expect(screen.queryByText('Test input 1')).not.toBeInTheDocument();
    expect(screen.getByText(/1 of 3 match search/)).toBeInTheDocument();
  });

  it('calls clear cache API after confirmation and reloads', async () => {
    api.clearCache.mockResolvedValue({ entries_invalidated: 10 });
    render(<CacheDashboard />);

    fireEvent.click(await screen.findByText('Clear All Cache'));

    expect(await screen.findByText('Invalidated 10 cache entries')).toBeInTheDocument();
    expect(api.clearCache).toHaveBeenCalledTimes(1);
    expect(api.getStats).toHaveBeenCalledTimes(2); // initial + reload
  });

  it('does not clear the cache when confirmation is cancelled', async () => {
    window.confirm = vi.fn(() => false);
    render(<CacheDashboard />);

    fireEvent.click(await screen.findByText('Clear All Cache'));
    expect(api.clearCache).not.toHaveBeenCalled();
  });

  it('cleans up expired entries', async () => {
    api.cleanupExpired.mockResolvedValue({ entries_cleaned: 4 });
    render(<CacheDashboard />);

    fireEvent.click(await screen.findByText('Cleanup Expired'));
    expect(await screen.findByText('Cleaned up 4 expired entries')).toBeInTheDocument();
  });

  it('deletes a single entry', async () => {
    api.deleteEntry.mockResolvedValue(undefined);
    render(<CacheDashboard />);

    const row = (await screen.findByText('Test input 1')).closest('tr')!;
    fireEvent.click(within(row).getByTitle('Delete entry'));

    await waitFor(() => expect(api.deleteEntry).toHaveBeenCalledWith('entry-1'));
    expect(await screen.findByText('Cache entry deleted')).toBeInTheDocument();
  });

  it('reports action failures in the notice', async () => {
    api.clearCache.mockRejectedValue({ response: { data: { detail: 'DB unavailable' } } });
    render(<CacheDashboard />);

    fireEvent.click(await screen.findByText('Clear All Cache'));
    expect(await screen.findByText('Failed: DB unavailable')).toBeInTheDocument();
  });

  it('polls stats every 10s for the live hit-rate chart', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<CacheDashboard />);
    await screen.findByText('Test input 1');
    expect(api.getStats).toHaveBeenCalledTimes(1);

    api.getStats.mockResolvedValue({ ...mockStats, hit_rate: 0.9 });
    await vi.advanceTimersByTimeAsync(10_000);

    await waitFor(() => expect(api.getStats).toHaveBeenCalledTimes(2));
    expect(await screen.findAllByText('90.0%')).not.toHaveLength(0);
    expect(screen.getByRole('img', { name: 'Cache hit rate over time' })
      .querySelectorAll('circle')).toHaveLength(2);
  });
});

// ============================================================================
// Execution results cache indicators
// ============================================================================

describe('ExecutionResults cache indicators', () => {
  const execution: ExecutionDetailResponse = {
    summary: {
      execution_id: 'exec-cache', workflow_id: 'wf-1', workflow_name: 'Cached Workflow',
      status: 'completed', total_stages: 2, completed_stages: 2, failed_stages: 0,
      total_tokens: 150, total_cost: '0.000100', total_latency_ms: 500,
      started_at: '2024-01-01T00:00:00Z', completed_at: '2024-01-01T00:00:01Z', duration_ms: 1000,
    },
    stages: [
      {
        id: 'rec-1', stage_id: 'stage-1', stage_name: 'Analyze', stage_order: 0,
        model_used: 'gpt-4o-mini', provider: 'openai', input_tokens: 100, output_tokens: 50,
        total_tokens: 150, latency_ms: 500, estimated_cost: '0.000100', status: 'completed',
        result: 'Fresh LLM output', error_message: null,
        started_at: '2024-01-01T00:00:00Z', completed_at: '2024-01-01T00:00:00.5Z', duration_ms: 500,
        cache_hit: false, cache_similarity: null, tokens_saved: null, cost_saved: null,
      },
      {
        id: 'rec-2', stage_id: 'stage-2', stage_name: 'Design', stage_order: 1,
        model_used: 'gpt-4o-mini', provider: 'cache', input_tokens: 0, output_tokens: 0,
        total_tokens: 0, latency_ms: 0, estimated_cost: '0.000000', status: 'completed',
        result: 'Cached design output', error_message: null,
        started_at: '2024-01-01T00:00:01Z', completed_at: '2024-01-01T00:00:01Z', duration_ms: 0,
        cache_hit: true, cache_similarity: 0.9734, tokens_saved: 150, cost_saved: '0.000300',
      },
    ],
  };

  it('shows a Cache Hit badge only on cached stages', () => {
    render(<ExecutionResults execution={execution} />);

    const cachedCard = screen.getByText('Design').closest('[data-testid="stage-result"]')! as HTMLElement;
    const freshCard = screen.getByText('Analyze').closest('[data-testid="stage-result"]')! as HTMLElement;
    expect(within(cachedCard).getByText('▣ Cache Hit')).toBeInTheDocument();
    expect(within(freshCard).queryByText(/Cache Hit/)).not.toBeInTheDocument();
  });

  it('shows instant, zero-cost results with savings for cached stages', () => {
    render(<ExecutionResults execution={execution} />);
    const cachedCard = screen.getByText('Design').closest('[data-testid="stage-result"]')! as HTMLElement;

    expect(within(within(cachedCard).getByTestId('stage-metrics')).getAllByText('0ms')).toHaveLength(2); // latency + duration
    expect(within(cachedCard).getByText('instant')).toBeInTheDocument();
    expect(within(cachedCard).getByText('Cached model')).toBeInTheDocument();
    expect(within(cachedCard).getByText('$0.0000')).toBeInTheDocument();
    expect(within(cachedCard).getByText('$0.0003 saved')).toBeInTheDocument();
    expect(within(cachedCard).getByText('150 saved')).toBeInTheDocument();
    expect(within(within(cachedCard).getByTestId('stage-metrics')).getByText('▣ HIT')).toBeInTheDocument();
    expect(within(cachedCard).getByTestId('cache-status')).toHaveTextContent(/similarity 97\.34%/);
  });

  it('formats Decimal strings for uncached stages', () => {
    render(<ExecutionResults execution={execution} />);
    const freshCard = screen.getByText('Analyze').closest('[data-testid="stage-result"]')! as HTMLElement;
    expect(within(freshCard).getByText('$0.0001')).toBeInTheDocument();
    expect(within(freshCard).getByText('Model')).toBeInTheDocument();
    expect(within(within(freshCard).getByTestId('stage-metrics')).getByText('○ MISS')).toBeInTheDocument();
  });

  it('shows cache hits and savings in the Metrics tab', () => {
    render(<ExecutionResults execution={execution} />);
    fireEvent.click(screen.getByText('Metrics'));

    expect(screen.getByText('Cache Hits')).toBeInTheDocument();
    expect(screen.getByText('1/2')).toBeInTheDocument();
    expect(screen.getByText('50% hit rate')).toBeInTheDocument();
    expect(screen.getByText('150 saved via cache')).toBeInTheDocument();
    expect(screen.getByText('$0.0003 saved via cache')).toBeInTheDocument();
    const costCard = screen.getByText('Total Cost').parentElement!;
    expect(within(costCard).getByText('$0.0001')).toBeInTheDocument(); // total cost from Decimal string

    const cachedRow = screen.getAllByText('Design').map((el) => el.closest('tr')).find(Boolean)!;
    expect(within(cachedRow).getByText('Cache')).toBeInTheDocument();
  });

  it('marks cached stages in the Context Flow tab', () => {
    render(<ExecutionResults execution={execution} />);
    fireEvent.click(screen.getByText('Context Flow'));
    expect(screen.getAllByText('Cache Hit')).toHaveLength(1);
  });
});

// ============================================================================
// Execute modal cache toggle
// ============================================================================

describe('ExecutionConfigModal cache toggle', () => {
  it('sends use_cache=true by default and false when unticked', () => {
    const onExecute = vi.fn();
    const { rerender } = render(
      <ExecutionConfigModal isOpen onClose={vi.fn()} onExecute={onExecute} workflowName="WF" />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Execute' }));
    expect(onExecute).toHaveBeenLastCalledWith(expect.objectContaining({ use_cache: true }));

    rerender(<ExecutionConfigModal isOpen onClose={vi.fn()} onExecute={onExecute} workflowName="WF" />);
    fireEvent.click(screen.getByLabelText('Use semantic cache'));
    fireEvent.click(screen.getByRole('button', { name: 'Execute' }));
    expect(onExecute).toHaveBeenLastCalledWith(expect.objectContaining({ use_cache: false }));
  });
});
