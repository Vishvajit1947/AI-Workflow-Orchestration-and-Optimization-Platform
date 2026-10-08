import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, GitBranch, Clock, Trash2 } from 'lucide-react';
import { useWorkflowList } from '../hooks/useWorkflows';
import { workflowApi } from '../lib/workflows';

const statusColors: Record<string, string> = {
  draft: 'bg-surface-700/50 text-surface-200/80',
  running: 'bg-blue-500/15 text-blue-300',
  completed: 'bg-primary-500/15 text-primary-400',
  failed: 'bg-red-500/15 text-red-300',
  paused: 'bg-amber-500/15 text-amber-300',
};

export default function WorkflowList() {
  const { data, loading, error, refetch } = useWorkflowList();
  const [search, setSearch] = useState('');

  const filtered = data?.items.filter(w =>
    w.name.toLowerCase().includes(search.toLowerCase())
  ) || [];

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm('Delete this workflow?')) return;
    await workflowApi.delete(id);
    refetch();
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Workflows</h1>
          <p className="text-surface-200/50 mt-1">Manage your AI workflow pipelines</p>
        </div>
        <Link
          to="/workflows/new"
          className="flex items-center gap-2 px-4 py-2.5 bg-primary-600 hover:bg-primary-500 rounded-lg text-sm font-medium transition-all duration-200 shadow-lg shadow-primary-600/25"
        >
          <Plus size={18} />
          New Workflow
        </Link>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-200/40" />
        <input
          type="text"
          placeholder="Search workflows..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 bg-surface-800/50 border border-surface-700/50 rounded-lg text-sm text-white placeholder:text-surface-200/30 focus:outline-none focus:border-primary-500/50 transition-colors"
        />
      </div>

      {/* Loading */}
      {loading && <p className="text-surface-200/50">Loading workflows...</p>}
      {error && <p className="text-red-400">Error: {error}</p>}

      {/* Grid */}
      {!loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(w => (
            <Link
              key={w.id}
              to={`/workflows/${w.id}`}
              className="glass rounded-xl p-5 card-hover group"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <GitBranch size={18} className="text-primary-400" />
                  <h3 className="font-semibold text-white group-hover:text-primary-300 transition-colors">
                    {w.name}
                  </h3>
                </div>
                <button
                  onClick={(e) => handleDelete(w.id, e)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition-all"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              {w.description && (
                <p className="text-sm text-surface-200/50 mb-3 line-clamp-2">{w.description}</p>
              )}
              <div className="flex items-center justify-between text-xs">
                <span className={`px-2 py-0.5 rounded-full ${statusColors[w.status] || statusColors.draft}`}>
                  {w.status}
                </span>
                <span className="text-surface-200/40 flex items-center gap-1">
                  <Clock size={12} />
                  {w.stage_count} stages
                </span>
              </div>
            </Link>
          ))}

          {filtered.length === 0 && !loading && (
            <div className="col-span-full text-center py-12 text-surface-200/40">
              <GitBranch size={48} className="mx-auto mb-4 opacity-30" />
              <p>No workflows found. Create your first one!</p>
            </div>
          )}
        </div>
      )}

      {/* Pagination info */}
      {data && (
        <div className="mt-6 text-sm text-surface-200/40">
          Showing {filtered.length} of {data.total} workflows
        </div>
      )}
    </div>
  );
}
