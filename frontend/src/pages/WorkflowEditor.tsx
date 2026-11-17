/**
 * Create a workflow manually, or edit a workflow's name, description and objective.
 * Stages are managed on the workflow page.
 */
import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Save, ArrowLeft } from 'lucide-react';
import { workflowApi } from '../lib/workflows';
import { getErrorMessage } from '../lib/errors';
import type { WorkflowCreate } from '../types';

export default function WorkflowEditor() {
  const { id } = useParams();
  const isEditing = Boolean(id);
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(isEditing);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<WorkflowCreate>({ name: '', description: '', objective: '' });

  useEffect(() => {
    if (!id) return;
    workflowApi
      .get(id)
      .then((w) => setForm({ name: w.name, description: w.description || '', objective: w.objective || '' }))
      .catch((err: unknown) => setError(`Could not load the workflow: ${getErrorMessage(err)}`))
      .finally(() => setLoading(false));
  }, [id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (isEditing && id) {
        await workflowApi.update(id, form);
        navigate(`/workflows/${id}`);
      } else {
        const created = await workflowApi.create(form);
        navigate(`/workflows/${created.id}`);
      }
    } catch (err: unknown) {
      setError(`Could not save the workflow: ${getErrorMessage(err)}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <button onClick={() => navigate(-1)} className="btn btn-ghost -ml-3 mb-4">
        <ArrowLeft size={16} aria-hidden /> Back
      </button>

      <h1 className="text-2xl font-semibold tracking-tight">{isEditing ? 'Edit workflow' : 'Create a workflow manually'}</h1>
      <p className="mb-6 mt-1 text-sm text-surface-200/50">
        {isEditing
          ? 'Update the workflow details. Stages are edited on the workflow page.'
          : 'Name the workflow, then add its stages on the next page.'}
      </p>

      {error && (
        <p role="alert" className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-surface-200/50">Loading workflow…</p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="wf-name" className="mb-1.5 block text-sm font-medium text-surface-200/80">
              Name <span className="text-red-400" aria-hidden>*</span>
            </label>
            <input
              id="wf-name"
              type="text"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="input px-4 py-2.5"
              placeholder="e.g. Software development workflow"
            />
          </div>

          <div>
            <label htmlFor="wf-description" className="mb-1.5 block text-sm font-medium text-surface-200/80">
              Description
            </label>
            <textarea
              id="wf-description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
              className="input resize-none px-4 py-2.5"
              placeholder="What this workflow does"
            />
          </div>

          <div>
            <label htmlFor="wf-objective" className="mb-1.5 block text-sm font-medium text-surface-200/80">
              Objective
            </label>
            <textarea
              id="wf-objective"
              value={form.objective}
              onChange={(e) => setForm({ ...form, objective: e.target.value })}
              rows={3}
              className="input resize-none px-4 py-2.5"
              placeholder="e.g. Build an online course management system"
            />
          </div>

          <button type="submit" disabled={saving || !form.name} className="btn btn-primary px-5 py-2.5">
            <Save size={16} aria-hidden />
            {saving ? 'Saving…' : isEditing ? 'Save changes' : 'Create workflow'}
          </button>
        </form>
      )}
    </div>
  );
}
