import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Save, ArrowLeft } from 'lucide-react';
import { workflowApi } from '../lib/workflows';
import type { WorkflowCreate } from '../types';

export default function WorkflowEditor() {
  const { id } = useParams();
  const isEditing = Boolean(id);
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<WorkflowCreate>({
    name: '',
    description: '',
    objective: '',
  });

  useEffect(() => {
    if (id) {
      workflowApi.get(id).then(w => {
        setForm({ name: w.name, description: w.description || '', objective: w.objective || '' });
      });
    }
  }, [id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (isEditing && id) {
        await workflowApi.update(id, form);
        navigate(`/workflows/${id}`);
      } else {
        const created = await workflowApi.create(form);
        navigate(`/workflows/${created.id}`);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-surface-200/50 hover:text-white mb-6 transition-colors">
        <ArrowLeft size={16} /> Back
      </button>

      <h1 className="text-2xl font-bold mb-6">{isEditing ? 'Edit Workflow' : 'Create Workflow'}</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-surface-200/70 mb-2">Name *</label>
          <input
            type="text"
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-4 py-2.5 bg-surface-800/50 border border-surface-700/50 rounded-lg text-white focus:outline-none focus:border-primary-500/50 transition-colors"
            placeholder="e.g., Software Development Workflow"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-surface-200/70 mb-2">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={3}
            className="w-full px-4 py-2.5 bg-surface-800/50 border border-surface-700/50 rounded-lg text-white focus:outline-none focus:border-primary-500/50 transition-colors resize-none"
            placeholder="Describe what this workflow does..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-surface-200/70 mb-2">Objective</label>
          <textarea
            value={form.objective}
            onChange={(e) => setForm({ ...form, objective: e.target.value })}
            rows={3}
            className="w-full px-4 py-2.5 bg-surface-800/50 border border-surface-700/50 rounded-lg text-white focus:outline-none focus:border-primary-500/50 transition-colors resize-none"
            placeholder="e.g., Build an online course management system"
          />
        </div>

        <button
          type="submit"
          disabled={saving || !form.name}
          className="flex items-center gap-2 px-6 py-2.5 bg-primary-600 hover:bg-primary-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-all shadow-lg shadow-primary-600/25"
        >
          <Save size={16} />
          {saving ? 'Saving...' : (isEditing ? 'Update Workflow' : 'Create Workflow')}
        </button>
      </form>
    </div>
  );
}
