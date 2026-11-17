/**
 * Recent executions across workflows; expand a row to see its timeline (Gantt).
 */
import { Fragment, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { executionApi } from '../api/executionApi';
import type { ExecutionListItem } from '../types/execution';
import { formatDuration, formatUSD } from '../lib/format';
import { getErrorMessage } from '../lib/errors';
import { ExecutionTimelineView } from '../components/charts/TimelineChart';
import { PageHeader } from '../components/ui/PageHeader';
import { StatusBadge } from '../components/ui/StatusBadge';

const PAGE_SIZE = 25;
const COLUMN_COUNT = 7;

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
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload only when the page changes
  }, [page]);

  const toggle = (id: string) => setExpanded(expanded === id ? null : id);

  return (
    <div>
      <PageHeader
        title="Executions"
        description="Every workflow run, newest first. Expand a run to see its timeline."
        actions={
          <button onClick={load} disabled={loading} className="btn btn-secondary">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} aria-hidden /> Refresh
          </button>
        }
      />

      {error && <p role="alert" className="mb-4 text-sm text-red-400">Could not load executions: {error}</p>}
      {loading && items.length === 0 && !error && <p className="text-sm text-surface-200/50">Loading executions…</p>}
      {!loading && items.length === 0 && !error && (
        <p className="glass rounded-xl p-6 text-sm text-surface-200/50">
          No executions yet. Open a workflow and choose <span className="text-white">Execute Workflow</span> to run it.
        </p>
      )}

      {items.length > 0 && (
        <div className={`glass overflow-x-auto rounded-xl transition-opacity ${loading ? 'opacity-60' : ''}`} aria-busy={loading}>
          <table className="w-full text-sm">
            <thead className="border-b border-surface-700/50 text-xs uppercase tracking-wide text-surface-200/50">
              <tr>
                <th className="w-8 px-4 py-3"><span className="sr-only">Expand</span></th>
                <th className="px-4 py-3 text-left">Workflow</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="whitespace-nowrap px-4 py-3 text-left">Started</th>
                <th className="px-4 py-3 text-right">Stages</th>
                <th className="px-4 py-3 text-right">Duration</th>
                <th className="px-4 py-3 text-right">Cost</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {items.map((e) => {
                const isOpen = expanded === e.execution_id;
                return (
                  <Fragment key={e.execution_id}>
                    <tr className="cursor-pointer border-b border-surface-700/30 hover:bg-surface-700/20" onClick={() => toggle(e.execution_id)}>
                      <td className="px-4 py-3 text-surface-200/50">
                        <button
                          onClick={(ev) => { ev.stopPropagation(); toggle(e.execution_id); }}
                          aria-expanded={isOpen}
                          aria-label={`${isOpen ? 'Hide' : 'Show'} timeline for ${e.workflow_name}`}
                          className="rounded p-0.5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/60"
                        >
                          {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          to={`/workflows/${e.workflow_id}`}
                          onClick={(ev) => ev.stopPropagation()}
                          className="font-medium hover:text-primary-400"
                        >
                          {e.workflow_name}
                        </Link>
                        <div className="font-mono text-xs text-surface-200/40">{e.execution_id.slice(0, 8)}</div>
                      </td>
                      <td className="px-4 py-3"><StatusBadge status={e.status} /></td>
                      <td className="whitespace-nowrap px-4 py-3 text-surface-200/70">
                        {e.started_at ? new Date(e.started_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-3 text-right">{e.completed_stages}/{e.total_stages}</td>
                      <td className="px-4 py-3 text-right">{e.duration_ms != null ? formatDuration(e.duration_ms) : '—'}</td>
                      <td className="px-4 py-3 text-right">{formatUSD(Number(e.total_cost))}</td>
                    </tr>
                    {isOpen && (
                      <tr className="border-b border-surface-700/30">
                        <td colSpan={COLUMN_COUNT} className="px-4 py-4">
                          <ExecutionTimelineView executionId={e.execution_id} dark />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {(page > 0 || items.length === PAGE_SIZE) && (
        <div className="mt-4 flex items-center justify-end gap-2">
          <span className="mr-2 text-xs text-surface-200/40">Page {page + 1}</span>
          <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0 || loading} className="btn btn-secondary py-1.5">
            Previous
          </button>
          <button onClick={() => setPage(page + 1)} disabled={items.length < PAGE_SIZE || loading} className="btn btn-secondary py-1.5">
            Next
          </button>
        </div>
      )}
    </div>
  );
}
