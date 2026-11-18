/**
 * Recent executions across workflows; expand a row to see its timeline (Gantt).
 */
import { Fragment, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ChevronRight, RefreshCw, Zap } from 'lucide-react';
import { executionApi } from '../api/executionApi';
import type { ExecutionListItem } from '../types/execution';
import { formatDuration, formatUSD } from '../lib/format';
import { getErrorMessage } from '../lib/errors';
import { ExecutionTimelineView } from '../components/charts/TimelineChart';
import { PageHeader } from '../components/ui/PageHeader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState, ErrorState, Skeleton } from '../components/ui/States';

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
        eyebrow="Build"
        title="Executions"
        description="Every workflow run, newest first. Expand a run to see its timeline."
        actions={
          <button onClick={load} disabled={loading} className="btn btn-outline">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} aria-hidden /> Refresh
          </button>
        }
      />

      {error && <ErrorState className="mb-4" title="Could not load executions" message={error} onRetry={load} />}
      {loading && items.length === 0 && !error && (
        <div className="space-y-3" aria-busy>
          {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-14" />)}
        </div>
      )}
      {!loading && items.length === 0 && !error && (
        <EmptyState
          icon={Zap}
          title="No executions yet."
          description={<>Open a workflow and choose <span className="font-book text-ink">Execute Workflow</span> to run it.</>}
          action={<Link to="/workflows" className="btn btn-secondary btn-sm">Open workflows</Link>}
        />
      )}

      {items.length > 0 && (
        <div className={`card overflow-x-auto transition-opacity ${loading ? 'opacity-60' : ''}`} aria-busy={loading}>
          <table className="data-table tabular">
            <thead>
              <tr>
                <th className="w-10"><span className="sr-only">Expand</span></th>
                <th>Workflow</th>
                <th>Status</th>
                <th className="hidden md:table-cell">Started</th>
                <th className="hidden !text-right sm:table-cell">Stages</th>
                <th className="!text-right">Duration</th>
                <th className="hidden !text-right md:table-cell">Cost</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e, index) => {
                const isOpen = expanded === e.execution_id;
                return (
                  <Fragment key={e.execution_id}>
                    <tr
                      className={`animate-fade-in-up cursor-pointer transition-colors duration-200 ease-soft hover:bg-lavender-soft ${isOpen ? 'bg-lavender-soft' : ''}`}
                      style={{ animationDelay: `${Math.min(index, 12) * 0.03}s` }}
                      onClick={() => toggle(e.execution_id)}
                    >
                      <td className="!pr-0">
                        <button
                          onClick={(ev) => { ev.stopPropagation(); toggle(e.execution_id); }}
                          aria-expanded={isOpen}
                          aria-label={`${isOpen ? 'Hide' : 'Show'} timeline for ${e.workflow_name}`}
                          className="btn btn-ghost btn-icon btn-sm"
                        >
                          <ChevronRight size={15} className={`transition-transform duration-300 ease-mercury ${isOpen ? 'rotate-90' : ''}`} />
                        </button>
                      </td>
                      <td className="min-w-[10rem]">
                        <Link
                          to={`/workflows/${e.workflow_id}`}
                          onClick={(ev) => ev.stopPropagation()}
                          className="font-book text-ink hover:text-primary-700"
                        >
                          {e.workflow_name}
                        </Link>
                        <div className="mt-0.5 font-mono text-[11px] text-ink-muted">{e.execution_id.slice(0, 8)}</div>
                      </td>
                      <td><StatusBadge status={e.status} /></td>
                      <td className="hidden whitespace-nowrap text-ink-secondary md:table-cell">
                        {e.started_at ? new Date(e.started_at).toLocaleString() : '—'}
                      </td>
                      <td className="hidden text-right sm:table-cell">{e.completed_stages}/{e.total_stages}</td>
                      <td className="text-right">{e.duration_ms != null ? formatDuration(e.duration_ms) : '—'}</td>
                      <td className="hidden text-right md:table-cell">{formatUSD(Number(e.total_cost))}</td>
                    </tr>
                    {isOpen && (
                      <tr className="!border-b-hairline bg-lavender-soft/50">
                        <td colSpan={COLUMN_COUNT} className="!px-3 !pb-5 !pt-1 sm:!px-5">
                          <div className="animate-fade-in-up">
                            <ExecutionTimelineView executionId={e.execution_id} />
                          </div>
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
          <span className="mr-2 text-xs text-ink-muted">Page {page + 1}</span>
          <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0 || loading} className="btn btn-outline btn-sm">
            Previous
          </button>
          <button onClick={() => setPage(page + 1)} disabled={items.length < PAGE_SIZE || loading} className="btn btn-outline btn-sm">
            Next
          </button>
        </div>
      )}
    </div>
  );
}
