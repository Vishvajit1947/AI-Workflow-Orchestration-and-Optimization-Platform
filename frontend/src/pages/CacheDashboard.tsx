/**
 * Semantic Cache dashboard: performance stats, live hit-rate chart,
 * filterable entries table and cache management controls.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Database, CheckCircle2, TrendingUp, Coins, RefreshCw, Trash2, Clock,
  Search, ChevronRight,
} from 'lucide-react';
import { cacheApi } from '../api/cacheApi';
import { getErrorMessage } from '../lib/errors';
import { PageHeader } from '../components/ui/PageHeader';
import { MetricCard } from '../components/metrics/MetricCard';
import { EmptyState, ErrorState, LoadingState, Notice } from '../components/ui/States';
import { useConfirm } from '../components/ui/Dialog';
import { CHART } from '../components/charts/chartKit';
import type { CacheEntry, CacheStats } from '../types/cache';

const PAGE_SIZE = 25;
const POLL_INTERVAL_MS = 10_000;
const MAX_SAMPLES = 30;

const STAGE_TYPES = ['analysis', 'design', 'generation', 'testing', 'documentation', 'review', 'custom'];

type ValidityFilter = '' | 'true' | 'false';

interface HitRateSample {
  time: Date;
  hitRate: number;
}

export default function CacheDashboard() {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [entries, setEntries] = useState<CacheEntry[]>([]);
  const [samples, setSamples] = useState<HitRateSample[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [stageType, setStageType] = useState('');
  const [validity, setValidity] = useState<ValidityFilter>('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [confirm, confirmDialog] = useConfirm();

  const loadStats = useCallback(async () => {
    const data = await cacheApi.getStats();
    setStats(data);
    setSamples((prev) => [...prev, { time: new Date(), hitRate: data.hit_rate }].slice(-MAX_SAMPLES));
  }, []);

  const loadEntries = useCallback(async () => {
    const data = await cacheApi.listEntries({
      stage_type: stageType || undefined,
      is_valid: validity === '' ? undefined : validity === 'true',
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    });
    setEntries(data);
  }, [stageType, validity, page]);

  const loadAll = useCallback(async () => {
    try {
      await Promise.all([loadStats(), loadEntries()]);
      setError(null);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [loadStats, loadEntries]);

  // Initial load and reload on filter/page change
  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Live stats polling for the hit-rate chart
  useEffect(() => {
    const timer = setInterval(() => {
      loadStats().catch(() => { /* keep last known stats */ });
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [loadStats]);

  const runAction = async (action: () => Promise<string>) => {
    setBusy(true);
    try {
      setNotice(await action());
      await loadAll();
    } catch (err: unknown) {
      setNotice(`Failed: ${getErrorMessage(err)}`);
    } finally {
      setBusy(false);
    }
  };

  const handleClearCache = async () => {
    const ok = await confirm({
      title: 'Clear the whole cache?',
      message: 'Every cache entry is invalidated. The next executions will call the LLM again.',
      confirmLabel: 'Clear cache',
      destructive: true,
    });
    if (!ok) return;
    runAction(async () => {
      const result = await cacheApi.clearCache();
      return `Invalidated ${result.entries_invalidated} cache entries`;
    });
  };

  const handleCleanupExpired = () =>
    runAction(async () => {
      const result = await cacheApi.cleanupExpired();
      return `Cleaned up ${result.entries_cleaned} expired entries`;
    });

  const handleDeleteEntry = async (entryId: string) => {
    const ok = await confirm({
      title: 'Delete this cache entry?',
      message: 'The entry is removed permanently. Similar inputs will call the LLM again.',
      confirmLabel: 'Delete entry',
      destructive: true,
    });
    if (!ok) return;
    runAction(async () => {
      await cacheApi.deleteEntry(entryId);
      return 'Cache entry deleted';
    });
  };

  const query = search.trim().toLowerCase();
  const visibleEntries = query
    ? entries.filter(
        (e) =>
          e.input_text.toLowerCase().includes(query) ||
          e.result.toLowerCase().includes(query) ||
          (e.model_used ?? '').toLowerCase().includes(query)
      )
    : entries;

  return (
    <div>
      <PageHeader
        eyebrow="Insights"
        title="Semantic Cache"
        description="Stage results reused for similar inputs, invalidated when upstream outputs change."
        actions={
          <>
            <button onClick={() => loadAll()} disabled={busy} className="btn btn-outline">
              <RefreshCw size={14} aria-hidden /> Refresh
            </button>
            <button onClick={handleCleanupExpired} disabled={busy} className="btn btn-secondary">
              <Clock size={14} aria-hidden /> Cleanup Expired
            </button>
            <button onClick={handleClearCache} disabled={busy} className="btn btn-danger">
              <Trash2 size={14} aria-hidden /> Clear All Cache
            </button>
          </>
        }
      />

      {notice && (
        <Notice tone={notice.startsWith('Failed') ? 'warning' : 'success'} className="mb-6" onDismiss={() => setNotice(null)}>
          {notice}
        </Notice>
      )}

      {loading && <LoadingState label="Loading cache data…" />}
      {error && <ErrorState className="mb-6" title="Could not load the cache" message={error} onRetry={() => loadAll()} />}

      {/* Stats */}
      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard
            icon={Database}
            label="Valid Entries"
            value={stats.total_entries.toLocaleString()}
          />
          <MetricCard
            icon={CheckCircle2}
            label="Cache Hits"
            value={stats.total_hits.toLocaleString()}
            detail={stats.total_hits > 0 ? `Avg similarity ${(stats.avg_similarity_score * 100).toFixed(1)}%` : undefined}
          />
          <MetricCard
            icon={TrendingUp}
            label="Hit Rate"
            value={`${(stats.hit_rate * 100).toFixed(1)}%`}
          />
          <MetricCard
            icon={Coins}
            label="Tokens Saved"
            value={stats.total_tokens_saved.toLocaleString()}
            detail={`$${Number(stats.total_cost_saved).toFixed(4)} saved`}
          />
        </div>
      )}

      {/* Live hit-rate chart */}
      {stats && <HitRateChart samples={samples} />}

      {/* Filters */}
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-[17px] font-medium text-ink">Entries</h2>
      </div>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <div className="relative min-w-0 flex-1 sm:min-w-[240px]">
          <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden />
          <input
            type="text"
            aria-label="Search cache entries"
            placeholder="Search input, output or model on this page..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input input-pill"
          />
        </div>
        <select
          aria-label="Stage type"
          value={stageType}
          onChange={(e) => { setStageType(e.target.value); setPage(0); }}
          className="input rounded-pill sm:w-48"
        >
          <option value="">All stage types</option>
          {STAGE_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          aria-label="Validity"
          value={validity}
          onChange={(e) => { setValidity(e.target.value as ValidityFilter); setPage(0); }}
          className="input rounded-pill sm:w-40"
        >
          <option value="">All entries</option>
          <option value="true">Valid only</option>
          <option value="false">Invalid only</option>
        </select>
      </div>

      {/* Entries table */}
      <div className="card overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th className="w-8"><span className="sr-only">Expand</span></th>
              <th>Stage Type</th>
              <th>Input</th>
              <th className="hidden md:table-cell">Model</th>
              <th className="!text-right">Hits</th>
              <th className="hidden !text-right sm:table-cell">Tokens</th>
              <th className="!text-center">Status</th>
              <th className="hidden lg:table-cell">Created</th>
              <th><span className="sr-only">Delete</span></th>
            </tr>
          </thead>
          <tbody>
            {visibleEntries.map((entry) => (
              <EntryRow
                key={entry.id}
                entry={entry}
                expanded={expanded === entry.id}
                onToggle={() => setExpanded(expanded === entry.id ? null : entry.id)}
                onDelete={() => handleDeleteEntry(entry.id)}
                disabled={busy}
              />
            ))}
          </tbody>
        </table>

        {!loading && visibleEntries.length === 0 && (
          <EmptyState
            className="m-3"
            compact
            icon={Database}
            title="No cache entries found"
            description={query || stageType || validity ? 'Try clearing the search or filters.' : 'Results are cached automatically as stages run.'}
          />
        )}
      </div>

      {/* Pagination */}
      <div className="mt-4 flex items-center justify-between text-sm text-ink-muted">
        <span>
          Page {page + 1}
          {query && ` · ${visibleEntries.length} of ${entries.length} match search`}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="btn btn-outline btn-sm"
          >
            Previous
          </button>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={entries.length < PAGE_SIZE}
            className="btn btn-outline btn-sm"
          >
            Next
          </button>
        </div>
      </div>
      {confirmDialog}
    </div>
  );
}

// --- Entry row with expandable input/output ---
const EntryRow: React.FC<{
  entry: CacheEntry;
  expanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
  disabled: boolean;
}> = ({ entry, expanded, onToggle, onDelete, disabled }) => {
  const expired = entry.expires_at !== null && new Date(entry.expires_at) < new Date();
  return (
    <>
      <tr
        onClick={onToggle}
        className={`cursor-pointer transition-colors hover:bg-lavender-soft ${expanded ? 'bg-lavender-soft' : ''}`}
        aria-expanded={expanded}
      >
        <td className="text-ink-faint">
          <ChevronRight size={14} className={`transition-transform duration-300 ease-mercury ${expanded ? 'rotate-90' : ''}`} />
        </td>
        <td>
          <span className="chip !bg-primary/10 !text-primary-700">
            {entry.stage_type || 'n/a'}
          </span>
        </td>
        <td className="max-w-[12rem] truncate text-ink sm:max-w-xs" title={entry.input_text}>
          {entry.input_text}
        </td>
        <td className="hidden max-w-[11rem] truncate whitespace-nowrap text-ink-secondary md:table-cell" title={entry.model_used ?? undefined}>{entry.model_used || 'n/a'}</td>
        <td className="text-right font-book tabular">{entry.hit_count}</td>
        <td className="hidden text-right text-ink-secondary tabular sm:table-cell">{(entry.result_tokens ?? 0).toLocaleString()}</td>
        <td className="text-center">
          {!entry.is_valid ? (
            <StatusPill tone="danger">invalid</StatusPill>
          ) : expired ? (
            <StatusPill tone="warning">expired</StatusPill>
          ) : (
            <StatusPill tone="success">valid</StatusPill>
          )}
        </td>
        <td className="hidden whitespace-nowrap text-ink-muted lg:table-cell">
          {new Date(entry.created_at).toLocaleString()}
        </td>
        <td className="text-right">
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            disabled={disabled}
            className="btn btn-ghost btn-icon btn-sm text-ink-faint hover:!text-danger"
            title="Delete entry"
            aria-label="Delete entry"
          >
            <Trash2 size={14} />
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-lavender-soft/50">
          <td colSpan={9} className="!px-4 !py-4 sm:!pl-12">
            <div className="grid animate-fade-in-up gap-4 md:grid-cols-2">
              <div className="min-w-0">
                <p className="eyebrow mb-2">Input</p>
                <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded-[10px] border border-hairline bg-surface p-3 font-mono text-xs leading-5 text-ink">
                  {entry.input_text}
                </pre>
              </div>
              <div className="min-w-0">
                <p className="eyebrow mb-2">Cached Output</p>
                <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded-[10px] border border-hairline bg-surface p-3 font-mono text-xs leading-5 text-ink">
                  {entry.result}
                </pre>
              </div>
            </div>
            <p className="mt-3 break-all text-xs text-ink-muted">
              ID {entry.id}
              {entry.expires_at && ` · Expires ${new Date(entry.expires_at).toLocaleString()}`}
            </p>
          </td>
        </tr>
      )}
    </>
  );
};

// --- Live hit-rate sparkline (samples collected while the page is open) ---
const HitRateChart: React.FC<{ samples: HitRateSample[] }> = ({ samples }) => {
  const width = 600;
  const height = 120;
  const pad = 8;
  const latest = samples[samples.length - 1];

  const points = samples.map((s, i) => {
    const x = samples.length > 1 ? pad + (i / (samples.length - 1)) * (width - pad * 2) : width / 2;
    const y = pad + (1 - s.hitRate) * (height - pad * 2);
    return { x, y, s };
  });
  const line = points.map((p) => `${p.x},${p.y}`).join(' ');
  const area = points.length > 1
    ? `${points[0].x},${height - pad} ${line} ${points[points.length - 1].x},${height - pad}`
    : '';

  return (
    <section className="card mb-8 p-5 sm:p-6" aria-label="Hit rate live">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-medium text-ink">Hit Rate — Live</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Sampled every {POLL_INTERVAL_MS / 1000}s while this page is open
          </p>
        </div>
        {latest && (
          <span className="text-stat font-medium text-ink tabular">{(latest.hitRate * 100).toFixed(1)}%</span>
        )}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-28" preserveAspectRatio="none" role="img"
           aria-label="Cache hit rate over time">
        {[0, 0.5, 1].map((v) => (
          <line
            key={v}
            x1={pad} x2={width - pad}
            y1={pad + (1 - v) * (height - pad * 2)} y2={pad + (1 - v) * (height - pad * 2)}
            stroke={CHART.grid} strokeWidth={1} strokeDasharray="4 4"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {area && <polygon points={area} fill={CHART.series1} opacity={0.1} />}
        {points.length > 1 && (
          <polyline points={line} fill="none" stroke={CHART.series1}
                    strokeWidth={2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        )}
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={3} fill={CHART.series1} stroke={CHART.surface} strokeWidth={1.5}>
            <title>{`${p.s.time.toLocaleTimeString()} — ${(p.s.hitRate * 100).toFixed(1)}%`}</title>
          </circle>
        ))}
      </svg>
      <div className="mt-1 flex justify-between text-xs text-ink-muted tabular">
        <span>{samples[0]?.time.toLocaleTimeString()}</span>
        <span>{samples.length > 1 && latest?.time.toLocaleTimeString()}</span>
      </div>
    </section>
  );
};

const PILL_TONES = {
  success: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
};

const StatusPill: React.FC<{ tone: keyof typeof PILL_TONES; children: React.ReactNode }> = ({ tone, children }) => (
  <span className={`inline-flex rounded-pill px-2.5 py-0.5 text-xs font-book ${PILL_TONES[tone]}`}>{children}</span>
);
