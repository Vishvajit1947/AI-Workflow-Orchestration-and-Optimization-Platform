/**
 * The user's workflows: search, filter by status, open, delete.
 */
import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, GitBranch, Layers, Trash2, ArrowUpRight, X } from 'lucide-react';
import { useWorkflowList } from '../hooks/useWorkflows';
import { workflowApi } from '../lib/workflows';
import { getErrorMessage } from '../lib/errors';
import { PageHeader } from '../components/ui/PageHeader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState, ErrorState, Notice, Skeleton } from '../components/ui/States';
import { SegmentedControl } from '../components/ui/Tabs';
import { useConfirm } from '../components/ui/Dialog';
import { relativeTime } from '../lib/format';
import { Stagger, StaggerItem } from '../components/motion/Motion';

export default function WorkflowList() {
  const { data, loading, error, refetch } = useWorkflowList();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('all');
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirm, confirmDialog] = useConfirm();

  const workflows = data?.items ?? [];
  const query = search.trim().toLowerCase();

  // Status filter options come from the data, so only real statuses are offered
  const statusOptions = useMemo(() => {
    const counts = new Map<string, number>();
    workflows.forEach((w) => counts.set(w.status, (counts.get(w.status) ?? 0) + 1));
    return [
      { value: 'all', label: `All ${workflows.length}` },
      ...[...counts.entries()].sort().map(([s, n]) => ({ value: s, label: `${s.charAt(0).toUpperCase()}${s.slice(1)} ${n}` })),
    ];
  }, [workflows]);

  const filtered = workflows.filter(
    (w) =>
      (status === 'all' || w.status === status) &&
      (w.name.toLowerCase().includes(query) || (w.description ?? '').toLowerCase().includes(query)),
  );

  const handleDelete = async (id: string, name: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const ok = await confirm({
      title: 'Delete workflow?',
      message: <>“{name}” and its stages will be deleted. Past execution records are removed with it.</>,
      confirmLabel: 'Delete workflow',
      destructive: true,
    });
    if (!ok) return;
    try {
      setActionError(null);
      await workflowApi.delete(id);
      refetch();
    } catch (err: unknown) {
      setActionError(`Could not delete the workflow: ${getErrorMessage(err)}`);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Build"
        title="Workflows"
        description="Your saved workflows and their latest status."
        actions={
          <>
            <Link to="/workflows/new" className="btn btn-outline">Create manually</Link>
            <Link to="/" className="btn btn-primary">
              <Plus size={16} aria-hidden />
              New Workflow
            </Link>
          </>
        }
      />

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative min-w-0 flex-1 sm:max-w-sm">
          <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden />
          <input
            type="search"
            aria-label="Search workflows"
            placeholder="Search workflows…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input input-pill"
          />
        </div>
        {workflows.length > 0 && statusOptions.length > 2 && (
          <SegmentedControl ariaLabel="Filter by status" options={statusOptions} value={status} onChange={setStatus} />
        )}
      </div>

      {actionError && <Notice tone="danger" className="mb-4" onDismiss={() => setActionError(null)}>{actionError}</Notice>}
      {error && <ErrorState title="Could not load workflows" message={error} onRetry={() => refetch()} />}

      {loading && !data && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" aria-busy>
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-40" />)}
        </div>
      )}

      {!loading && !error && (
        <>
          <Stagger inView={false} step={0.04} className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((w) => (
              <StaggerItem key={w.id} layout className="min-w-0">
              <Link
                to={`/workflows/${w.id}`}
                className="card card-interactive group flex h-full min-h-[10rem] flex-col p-5 hover:border-primary/30 focus-visible:ring-2 focus-visible:ring-primary/40"
              >
                <div className="mb-3 flex items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-lavender text-primary" aria-hidden>
                    <GitBranch size={16} strokeWidth={1.75} />
                  </span>
                  <h3 className="min-w-0 flex-1 break-words pt-1.5 text-[15px] font-medium leading-snug text-ink">
                    {w.name}
                  </h3>
                  <button
                    onClick={(e) => handleDelete(w.id, w.name, e)}
                    aria-label={`Delete ${w.name}`}
                    className="btn btn-ghost btn-icon btn-sm -mr-1.5 -mt-0.5 text-ink-faint opacity-100 hover:text-danger sm:opacity-0 sm:focus-visible:opacity-100 sm:group-hover:opacity-100"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                {w.description ? (
                  <p className="mb-4 line-clamp-2 text-sm leading-relaxed text-ink-secondary">{w.description}</p>
                ) : (
                  <p className="mb-4 text-sm italic text-ink-faint">No description</p>
                )}
                <div className="mt-auto flex items-center justify-between gap-2 border-t border-hairline pt-3.5 text-xs">
                  <StatusBadge status={w.status} />
                  <span className="flex items-center gap-3 text-ink-muted tabular">
                    <span className="flex items-center gap-1">
                      <Layers size={12} aria-hidden />
                      {w.stage_count} {w.stage_count === 1 ? 'stage' : 'stages'}
                    </span>
                    {w.updated_at && <span className="hidden sm:inline">{relativeTime(w.updated_at)}</span>}
                    <ArrowUpRight size={14} className="text-ink-faint transition-[color,transform] duration-300 ease-mercury group-hover:-translate-y-px group-hover:translate-x-px group-hover:text-primary" aria-hidden />
                  </span>
                </div>
              </Link>
              </StaggerItem>
            ))}
          </Stagger>

          {filtered.length === 0 && (
            workflows.length === 0 ? (
              <EmptyState
                icon={GitBranch}
                title="No workflows yet."
                description="Describe an objective and the AI planner proposes the stages for you to review."
                action={
                  <Link to="/" className="btn btn-primary">
                    <Plus size={16} aria-hidden /> Plan your first workflow
                  </Link>
                }
              />
            ) : (
              <EmptyState
                icon={Search}
                title={query ? `No workflows match “${search.trim()}”.` : 'No workflows with this status.'}
                action={
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setSearch(''); setStatus('all'); }}>
                    <X size={13} aria-hidden /> Clear filters
                  </button>
                }
              />
            )
          )}

          {data && data.total > 0 && (
            <p className="mt-6 text-sm text-ink-muted">
              Showing {filtered.length} of {data.total} workflows
            </p>
          )}
        </>
      )}
      {confirmDialog}
    </div>
  );
}
