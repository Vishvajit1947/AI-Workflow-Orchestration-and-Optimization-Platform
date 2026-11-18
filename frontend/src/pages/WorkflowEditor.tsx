/**
 * Create a workflow manually, or edit a workflow's name, description and objective.
 * Stages are managed on the workflow page.
 */
import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Save, Sparkles } from 'lucide-react';
import { workflowApi } from '../lib/workflows';
import { getErrorMessage } from '../lib/errors';
import { PageHeader } from '../components/ui/PageHeader';
import { LoadingState, Notice } from '../components/ui/States';
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
    <div className="mx-auto max-w-2xl">
      <PageHeader
        eyebrow={isEditing ? 'Workflow' : 'Build'}
        title={isEditing ? 'Edit workflow' : 'Create a workflow manually'}
        description={
          isEditing
            ? 'Update the workflow details. Stages are edited on the workflow page.'
            : 'Name the workflow, then add its stages on the next page.'
        }
      />

      {error && <Notice tone="danger" className="mb-6">{error}</Notice>}

      {loading ? (
        <LoadingState label="Loading workflow…" />
      ) : (
        <form onSubmit={handleSubmit} className="card space-y-5 p-5 sm:p-7">
          <div>
            <label htmlFor="wf-name" className="label">
              Name <span className="text-danger" aria-hidden>*</span>
            </label>
            <input
              id="wf-name"
              type="text"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="input"
              placeholder="e.g. Software development workflow"
            />
          </div>

          <div>
            <label htmlFor="wf-description" className="label">
              Description
            </label>
            <textarea
              id="wf-description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
              className="input resize-y"
              placeholder="What this workflow does"
            />
          </div>

          <div>
            <label htmlFor="wf-objective" className="label">
              Objective
            </label>
            <textarea
              id="wf-objective"
              value={form.objective}
              onChange={(e) => setForm({ ...form, objective: e.target.value })}
              rows={3}
              className="input resize-y"
              placeholder="e.g. Build an online course management system"
            />
            <p className="hint">Shown on the workflow page as context for its stages.</p>
          </div>

          <div className="flex flex-col-reverse gap-2 border-t border-hairline pt-5 sm:flex-row sm:justify-end">
            <button type="button" onClick={() => navigate(-1)} className="btn btn-outline">Cancel</button>
            <button type="submit" disabled={saving || !form.name} className="btn btn-primary">
              <Save size={15} aria-hidden />
              {saving ? 'Saving…' : isEditing ? 'Save changes' : 'Create workflow'}
            </button>
          </div>
        </form>
      )}

      {!isEditing && (
        <p className="mt-8 text-center text-sm text-ink-secondary">
          <Sparkles size={14} className="mr-1 inline text-primary" aria-hidden />
          Not sure which stages you need?{' '}
          <Link to="/" className="link">Let the AI planner propose them</Link>
        </p>
      )}
    </div>
  );
}
