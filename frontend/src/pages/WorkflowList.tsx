import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, GitBranch, Layers, Trash2 } from 'lucide-react';
import { useWorkflowList } from '../hooks/useWorkflows';
import { workflowApi } from '../lib/workflows';
import { getErrorMessage } from '../lib/errors';
import { PageHeader } from '../components/ui/PageHeader';
import { StatusBadge } from '../components/ui/StatusBadge';

export default function WorkflowList() {
  const { data, loading, error, refetch } = useWorkflowList();
  const [search, setSearch] = useState('');

  const query = search.trim().toLowerCase();
  const workflows = data?.items ?? [];
  const filtered = workflows.filter((w) => w.name.toLowerCase().includes(query));

  const handleDelete = async (id: string, name: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(`Delete the workflow "${name}"?`)) return;
    try {
      await workflowApi.delete(id);
      refetch();
    } catch (err: unknown) {
      alert(`Could not delete the workflow: ${getErrorMessage(err)}`);
    }
  };

  return (
    <div>
      <PageHeader
        title="Workflows"
        description="Your saved workflows and their latest status"
        actions={
          <Link to="/" className="btn btn-primary">
            <Plus size={16} aria-hidden />
            New Workflow
          </Link>
        }
      />

      <div className="relative mb-6">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-200/40" aria-hidden />
        <input
          type="search"
          aria-label="Search workflows"
          placeholder="Search workflows…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input py-2.5 pl-9"
        />
      </div>

      {loading && <p className="text-sm text-surface-200/50">Loading workflows…</p>}
      {error && <p role="alert" className="text-sm text-red-400">Could not load workflows: {error}</p>}

      {!loading && !error && (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filtered.map((w) => (
              <Link
                key={w.id}
                to={`/workflows/${w.id}`}
                className="glass card-hover group flex flex-col rounded-xl p-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/60"
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <h3 className="min-w-0 break-words font-semibold text-white transition-colors group-hover:text-primary-300">
                    {w.name}
                  </h3>
                  <button
                    onClick={(e) => handleDelete(w.id, w.name, e)}
                    aria-label={`Delete ${w.name}`}
                    className="shrink-0 rounded p-1 text-surface-200/40 transition-colors hover:text-red-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/60"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                {w.description && <p className="mb-3 line-clamp-2 text-sm text-surface-200/50">{w.description}</p>}
                <div className="mt-auto flex items-center justify-between pt-2 text-xs">
                  <StatusBadge status={w.status} />
                  <span className="flex items-center gap-1 text-surface-200/40">
                    <Layers size={12} aria-hidden />
                    {w.stage_count} {w.stage_count === 1 ? 'stage' : 'stages'}
                  </span>
                </div>
              </Link>
            ))}
          </div>

          {filtered.length === 0 && (
            <div className="py-16 text-center text-surface-200/50">
              <GitBranch size={40} className="mx-auto mb-4 opacity-30" aria-hidden />
              {workflows.length === 0 ? (
                <>
                  <p className="mb-4">No workflows yet.</p>
                  <Link to="/" className="btn btn-primary">
                    <Plus size={16} aria-hidden /> Plan your first workflow
                  </Link>
                </>
              ) : (
                <p>No workflows match “{search.trim()}”.</p>
              )}
            </div>
          )}

          {data && data.total > 0 && (
            <p className="mt-6 text-sm text-surface-200/40">
              Showing {filtered.length} of {data.total} workflows
            </p>
          )}
        </>
      )}
    </div>
  );
}
