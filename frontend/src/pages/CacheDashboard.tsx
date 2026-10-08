/**
 * Semantic Cache dashboard: performance stats, live hit-rate chart,
 * filterable entries table and cache management controls.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Database, CheckCircle2, TrendingUp, Coins, RefreshCw, Trash2, Clock,
  Search, ChevronDown, ChevronRight, XCircle,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cacheApi } from '../api/cacheApi';
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
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
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
    } catch (err: any) {
      setNotice(`Failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleClearCache = () => {
    if (!confirm('Invalidate every cache entry? The next executions will call the LLM again.')) return;
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

  const handleDeleteEntry = (entryId: string) => {
    if (!confirm('Permanently delete this cache entry?')) return;
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
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold">Semantic Cache</h1>
          <p className="text-surface-200/50 mt-1">Reuse of LLM results across similar stage inputs</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => loadAll()}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 bg-surface-700/50 hover:bg-surface-700 rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} /> Refresh
          </button>
          <button
            onClick={handleCleanupExpired}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            <Clock size={14} /> Cleanup Expired
          </button>
          <button
            onClick={handleClearCache}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            <Trash2 size={14} /> Clear All Cache
          </button>
        </div>
      </div>

      {notice && (
        <div className="mb-6 flex items-center justify-between glass rounded-lg px-4 py-3 text-sm">
          <span>{notice}</span>
          <button onClick={() => setNotice(null)} className="text-surface-200/50 hover:text-white">
            <XCircle size={16} />
          </button>
        </div>
      )}

      {loading && <p className="text-surface-200/50">Loading cache data...</p>}
      {error && <p className="text-red-400 mb-6">Error: {error}</p>}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            icon={Database}
            label="Valid Entries"
            value={stats.total_entries.toLocaleString()}
          />
          <StatCard
            icon={CheckCircle2}
            label="Cache Hits"
            value={stats.total_hits.toLocaleString()}
            subtext={stats.total_hits > 0 ? `Avg similarity ${(stats.avg_similarity_score * 100).toFixed(1)}%` : undefined}
          />
          <StatCard
            icon={TrendingUp}
            label="Hit Rate"
            value={`${(stats.hit_rate * 100).toFixed(1)}%`}
          />
          <StatCard
            icon={Coins}
            label="Tokens Saved"
            value={stats.total_tokens_saved.toLocaleString()}
            subtext={`$${Number(stats.total_cost_saved).toFixed(4)} saved`}
          />
        </div>
      )}

      {/* Live hit-rate chart */}
      {stats && <HitRateChart samples={samples} />}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-200/40" />
          <input
            type="text"
            placeholder="Search input, output or model on this page..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-surface-800/50 border border-surface-700/50 rounded-lg text-sm text-white placeholder:text-surface-200/30 focus:outline-none focus:border-primary-500/50 transition-colors"
          />
        </div>
        <select
          value={stageType}
          onChange={(e) => { setStageType(e.target.value); setPage(0); }}
          className="px-3 py-2 bg-surface-800/50 border border-surface-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-primary-500/50"
        >
          <option value="">All stage types</option>
          {STAGE_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={validity}
          onChange={(e) => { setValidity(e.target.value as ValidityFilter); setPage(0); }}
          className="px-3 py-2 bg-surface-800/50 border border-surface-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-primary-500/50"
        >
          <option value="">All entries</option>
          <option value="true">Valid only</option>
          <option value="false">Invalid only</option>
        </select>
      </div>

      {/* Entries table */}
      <div className="glass rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-surface-200/50 text-xs uppercase tracking-wide border-b border-surface-700/50">
            <tr>
              <th className="px-4 py-3 w-8" />
              <th className="px-4 py-3 text-left">Stage Type</th>
              <th className="px-4 py-3 text-left">Input</th>
              <th className="px-4 py-3 text-left">Model</th>
              <th className="px-4 py-3 text-right">Hits</th>
              <th className="px-4 py-3 text-right">Tokens</th>
              <th className="px-4 py-3 text-center">Status</th>
              <th className="px-4 py-3 text-left">Created</th>
              <th className="px-4 py-3" />
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
          <div className="text-center py-12 text-surface-200/40">
            <Database size={40} className="mx-auto mb-3 opacity-30" />
            <p>No cache entries found</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-4 text-sm text-surface-200/50">
        <span>
          Page {page + 1}
          {query && ` · ${visibleEntries.length} of ${entries.length} match search`}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1.5 bg-surface-700/50 hover:bg-surface-700 rounded-lg disabled:opacity-40"
          >
            Previous
          </button>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={entries.length < PAGE_SIZE}
            className="px-3 py-1.5 bg-surface-700/50 hover:bg-surface-700 rounded-lg disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
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
        className="border-b border-surface-700/30 hover:bg-surface-700/20 cursor-pointer"
      >
        <td className="px-4 py-3 text-surface-200/40">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </td>
        <td className="px-4 py-3">
          <span className="px-2 py-0.5 rounded-full text-xs bg-primary-500/15 text-primary-300">
            {entry.stage_type || 'n/a'}
          </span>
        </td>
        <td className="px-4 py-3 text-surface-200/80 max-w-xs truncate" title={entry.input_text}>
          {entry.input_text}
        </td>
        <td className="px-4 py-3 text-surface-200/60">{entry.model_used || 'n/a'}</td>
        <td className="px-4 py-3 text-right font-medium">{entry.hit_count}</td>
        <td className="px-4 py-3 text-right text-surface-200/60">{(entry.result_tokens ?? 0).toLocaleString()}</td>
        <td className="px-4 py-3 text-center">
          {!entry.is_valid ? (
            <span className="px-2 py-0.5 rounded-full text-xs bg-red-500/20 text-red-300">invalid</span>
          ) : expired ? (
            <span className="px-2 py-0.5 rounded-full text-xs bg-amber-500/20 text-amber-300">expired</span>
          ) : (
            <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-500/20 text-emerald-300">valid</span>
          )}
        </td>
        <td className="px-4 py-3 text-surface-200/50 whitespace-nowrap">
          {new Date(entry.created_at).toLocaleString()}
        </td>
        <td className="px-4 py-3 text-right">
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            disabled={disabled}
            className="p-1 text-surface-200/50 hover:text-red-400 transition-colors disabled:opacity-40"
            title="Delete entry"
          >
            <Trash2 size={14} />
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-surface-700/30 bg-surface-800/40">
          <td />
          <td colSpan={8} className="px-4 py-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-surface-200/40 mb-1">Input</p>
                <pre className="text-xs font-mono whitespace-pre-wrap text-surface-200/80 max-h-64 overflow-y-auto">
                  {entry.input_text}
                </pre>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-surface-200/40 mb-1">Cached Output</p>
                <pre className="text-xs font-mono whitespace-pre-wrap text-surface-200/80 max-h-64 overflow-y-auto">
                  {entry.result}
                </pre>
              </div>
            </div>
            <p className="text-xs text-surface-200/40 mt-3">
              ID {entry.id}
              {entry.expires_at && ` · Expires ${new Date(entry.expires_at).toLocaleString()}`}
            </p>
          </td>
        </tr>
      )}
    </>
  );
};

// --- Stat card ---
const StatCard: React.FC<{
  icon: LucideIcon;
  label: string;
  value: string;
  subtext?: string;
}> = ({ icon: Icon, label, value, subtext }) => (
  <div className="glass rounded-xl p-5">
    <div className="flex items-center justify-between mb-2">
      <p className="text-sm text-surface-200/50">{label}</p>
      <Icon size={18} className="text-primary-400" />
    </div>
    <p className="text-3xl font-bold">{value}</p>
    {subtext && <p className="text-xs text-surface-200/50 mt-1">{subtext}</p>}
  </div>
);

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
    <div className="glass rounded-xl p-5 mb-6">
      <div className="flex items-baseline justify-between mb-3">
        <div>
          <h2 className="font-semibold">Hit Rate — Live</h2>
          <p className="text-xs text-surface-200/40">
            Sampled every {POLL_INTERVAL_MS / 1000}s while this page is open
          </p>
        </div>
        {latest && (
          <span className="text-2xl font-bold text-primary-300">{(latest.hitRate * 100).toFixed(1)}%</span>
        )}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-28" preserveAspectRatio="none" role="img"
           aria-label="Cache hit rate over time">
        {[0, 0.5, 1].map((v) => (
          <line
            key={v}
            x1={pad} x2={width - pad}
            y1={pad + (1 - v) * (height - pad * 2)} y2={pad + (1 - v) * (height - pad * 2)}
            stroke="currentColor" className="text-surface-700" strokeWidth={1} strokeDasharray="4 4"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {area && <polygon points={area} className="fill-primary-500/15" />}
        {points.length > 1 && (
          <polyline points={line} fill="none" stroke="currentColor" className="text-primary-400"
                    strokeWidth={2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        )}
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={3} className="fill-primary-300">
            <title>{`${p.s.time.toLocaleTimeString()} — ${(p.s.hitRate * 100).toFixed(1)}%`}</title>
          </circle>
        ))}
      </svg>
      <div className="flex justify-between text-xs text-surface-200/40 mt-1">
        <span>{samples[0]?.time.toLocaleTimeString()}</span>
        <span>{samples.length > 1 && latest?.time.toLocaleTimeString()}</span>
      </div>
    </div>
  );
};
