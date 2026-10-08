/**
 * Recent executions across workflows; expand a row to see its timeline (Gantt).
 */
import { Fragment, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { executionApi } from '../api/executionApi';
import type { ExecutionListItem } from '../types/execution';
import { formatDuration, formatUSD } from '../lib/format';
import { ExecutionTimelineView } from '../components/charts/TimelineChart';

const PAGE_SIZE = 25;

export default function ExecutionsPage() {
  const [items, setItems] = useState<ExecutionListItem[]>([]);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // ?expand=<execution_id> deep-links straight to one execution's timeline
  const [searchParams] = useSearchParams();
  const [expanded, setExpanded] = useState<string | null>(searchParams.get('expand'));

  const load = async () => {
    setLoading(true);
    try {
      setItems(await executionApi.listExecutions(undefined, PAGE_SIZE, page * PAGE_SIZE));
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [page]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Executions</h1>
          <p className="text-surface-200/50 mt-1">Every workflow run, newest first</p>
        </div>
        <button onClick={load} disabled={loading}
                className="flex items-center gap-1.5 px-3 py-2 bg-surface-700/50 hover:bg-surface-700 rounded-lg text-sm transition-colors disabled:opacity-50">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {error && <p className="text-red-400 mb-4">Could not load executions: {error}</p>}
      {!loading && items.length === 0 && !error && (
        <p className="text-surface-200/50">No executions yet. Run a workflow from its page.</p>
      )}

      {items.length > 0 && (
        <div className={`glass rounded-xl overflow-x-auto ${loading ? 'opacity-60' : ''}`}>
          <table className="w-full text-sm">
            <thead className="text-surface-200/50 text-xs uppercase tracking-wide border-b border-surface-700/50">
              <tr>
                <th className="px-4 py-3 w-8" />
                <th className="px-4 py-3 text-left">Workflow</th>
                <th className="px-4 py-3 text-left">Started</th>
                <th className="px-4 py-3 text-right">Stages</th>
                <th className="px-4 py-3 text-right">Duration</th>
                <th className="px-4 py-3 text-right">Cost</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {items.map((e) => (
                <Fragment key={e.execution_id}>
                  <tr className="border-b border-surface-700/30 hover:bg-surface-700/20 cursor-pointer"
                      onClick={() => setExpanded(expanded === e.execution_id ? null : e.execution_id)}>
                    <td className="px-4 py-3 text-surface-200/50">
                      {expanded === e.execution_id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </td>
                    <td className="px-4 py-3">
                      <Link to={`/workflows/${e.workflow_id}`} onClick={(ev) => ev.stopPropagation()}
                            className="font-medium hover:text-primary-400">
                        {e.workflow_name}
                      </Link>
                      <div className="text-xs text-surface-200/40 font-mono">{e.execution_id.slice(0, 8)}</div>
                    </td>
                    <td className="px-4 py-3 text-surface-200/70">{e.started_at ? new Date(e.started_at).toLocaleString() : '—'}</td>
                    <td className="px-4 py-3 text-right">{e.completed_stages}/{e.total_stages}</td>
                    <td className="px-4 py-3 text-right">{e.duration_ms != null ? formatDuration(e.duration_ms) : '—'}</td>
                    <td className="px-4 py-3 text-right">{formatUSD(Number(e.total_cost))}</td>
                  </tr>
                  {expanded === e.execution_id && (
                    <tr className="border-b border-surface-700/30">
                      <td colSpan={6} className="px-4 py-4">
                        <ExecutionTimelineView executionId={e.execution_id} dark />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex justify-end gap-2 mt-4">
        <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0 || loading}
                className="px-3 py-1.5 bg-surface-700/50 hover:bg-surface-700 rounded-lg text-sm disabled:opacity-40">
          Previous
        </button>
        <button onClick={() => setPage(page + 1)} disabled={items.length < PAGE_SIZE || loading}
                className="px-3 py-1.5 bg-surface-700/50 hover:bg-surface-700 rounded-lg text-sm disabled:opacity-40">
          Next
        </button>
      </div>
    </div>
  );
}
