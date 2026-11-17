import { useEffect, useState } from 'react';
import { Plus, Trash2, Save, X, ChevronDown, ChevronUp } from 'lucide-react';
import { stageApi } from '../lib/stages';
import { modelsApi } from '../api/modelsApi';
import { ModelSelect } from './ModelSelect';
import type { Stage } from '../types';
import type { ModelProfile } from '../types/routing';
import { getErrorMessage } from '../lib/errors';

interface Props {
  workflowId: string;
  stages: Stage[];
  onUpdate: () => void;
}

const stageTypes = ['analysis', 'design', 'generation', 'testing', 'documentation', 'review', 'custom'];

export default function StageEditor({ workflowId, stages, onUpdate }: Props) {
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: '', instruction: '', stage_type: '', model_preference: '', parallel: false });
  const [models, setModels] = useState<ModelProfile[]>([]);
  const [error, setError] = useState<string | null>(null);

  /** Run a stage change, then refresh; failures are shown above the list instead of being dropped. */
  const mutate = async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
      onUpdate();
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    }
  };

  useEffect(() => {
    modelsApi.listModels()
      .then(setModels)
      .catch((err) => console.error('Failed to load models:', err));
  }, []);

  const handleModelChange = async (stage: Stage, modelName: string | null) => {
    await mutate(() => stageApi.update(stage.id, { model_preference: modelName }));
  };

  // Stages sharing a stage_order run in parallel; the step number counts distinct orders
  const orders = [...new Set(stages.map((s) => s.stage_order))].sort((a, b) => a - b);
  const lastOrder = orders.length ? orders[orders.length - 1] : -1;
  const orderCount = (order: number) => stages.filter((s) => s.stage_order === order).length;

  const handleAdd = async () => {
    if (!form.name || !form.instruction) return;
    await mutate(async () => {
      await stageApi.create({
        workflow_id: workflowId,
        name: form.name,
        instruction: form.instruction,
        stage_order: form.parallel && lastOrder >= 0 ? lastOrder : lastOrder + 1,
        stage_type: form.stage_type || undefined,
        model_preference: form.model_preference || undefined,
      });
      setForm({ name: '', instruction: '', stage_type: '', model_preference: '', parallel: false });
      setAdding(false);
    });
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this stage?')) return;
    await mutate(() => stageApi.delete(id));
  };

  // Swap stage_order with the neighbour (keeps parallel groups intact, unlike renumbering)
  const swapWith = async (index: number, other: number) => {
    const a = stages[index], b = stages[other];
    if (!a || !b || a.stage_order === b.stage_order) return;
    await mutate(async () => {
      await stageApi.update(a.id, { stage_order: b.stage_order });
      await stageApi.update(b.id, { stage_order: a.stage_order });
    });
  };

  const handleMoveUp = (index: number) => swapWith(index, index - 1);
  const handleMoveDown = (index: number) => swapWith(index, index + 1);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Stages ({stages.length})</h2>
        <button onClick={() => setAdding(true)} className="btn btn-secondary">
          <Plus size={16} aria-hidden /> Add Stage
        </button>
      </div>

      {error && <p role="alert" className="mb-3 text-sm text-red-400">Stage update failed: {error}</p>}

      {stages.length === 0 && !adding && (
        <p className="glass rounded-lg p-4 text-sm text-surface-200/50">
          This workflow has no stages yet. Add one to be able to execute it.
        </p>
      )}

      {/* Stage list */}
      <div className="space-y-3">
        {stages.map((stage, idx) => (
          <div key={stage.id} className="glass rounded-lg p-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex flex-col gap-0.5">
                <button onClick={() => handleMoveUp(idx)} aria-label={`Move ${stage.name} up`}
                  className="text-surface-200/30 transition-colors hover:text-white disabled:opacity-30 disabled:hover:text-surface-200/30" disabled={idx === 0}>
                  <ChevronUp size={14} />
                </button>
                <button onClick={() => handleMoveDown(idx)} aria-label={`Move ${stage.name} down`}
                  className="text-surface-200/30 transition-colors hover:text-white disabled:opacity-30 disabled:hover:text-surface-200/30" disabled={idx === stages.length - 1}>
                  <ChevronDown size={14} />
                </button>
              </div>
              <div className="w-8 h-8 rounded-full bg-primary-500/20 flex items-center justify-center text-sm font-bold text-primary-400 shrink-0">
                {orders.indexOf(stage.stage_order) + 1}
              </div>
              <div className="min-w-[12rem] flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{stage.name}</span>
                  {orderCount(stage.stage_order) > 1 && (
                    <span className="text-xs px-2 py-0.5 rounded bg-surface-700/50 text-surface-200/80" title="Runs at the same time as the other stages of this step">
                      parallel
                    </span>
                  )}
                  {stage.stage_type && (
                    <span className="text-xs px-2 py-0.5 rounded bg-surface-700/50 text-surface-200/50">{stage.stage_type}</span>
                  )}
                </div>
                <p className="text-sm text-surface-200/40 mt-1 truncate">{stage.instruction}</p>
              </div>
              <ModelSelect
                aria-label={`Model for ${stage.name}`}
                models={models}
                stageType={stage.stage_type}
                value={stage.model_preference}
                onChange={(modelName) => handleModelChange(stage, modelName)}
                className={`max-w-[16rem] px-2 py-1.5 bg-surface-800/50 border border-surface-700/50 rounded-lg text-xs focus:outline-none ${
                  stage.model_preference ? 'text-primary-400' : 'text-surface-200/60'
                }`}
              />
              <button onClick={() => handleDelete(stage.id)} aria-label={`Delete ${stage.name}`}
                className="text-surface-200/30 transition-colors hover:text-red-400">
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add form */}
      {adding && (
        <div className="glass rounded-lg p-5 mt-4 space-y-4">
          <h3 className="font-medium">New Stage</h3>
          <input type="text" aria-label="Stage name" placeholder="Stage name" value={form.name}
            onChange={e => setForm({...form, name: e.target.value})}
            className="input" />
          <textarea aria-label="Instruction" placeholder="Instruction for the LLM..." value={form.instruction}
            onChange={e => setForm({...form, instruction: e.target.value})} rows={3}
            className="input resize-none" />
          <div className="flex flex-col gap-3 sm:flex-row">
            <select aria-label="Stage type" value={form.stage_type} onChange={e => setForm({...form, stage_type: e.target.value})}
              className="px-3 py-2 bg-surface-800/50 border border-surface-700/50 rounded-lg text-sm text-white focus:outline-none">
              <option value="">Type (optional)</option>
              {stageTypes.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <ModelSelect
              aria-label="Model preference"
              models={models}
              stageType={form.stage_type}
              value={form.model_preference || null}
              onChange={(modelName) => setForm({...form, model_preference: modelName || ''})}
              className="flex-1 px-3 py-2 bg-surface-800/50 border border-surface-700/50 rounded-lg text-sm text-white focus:outline-none"
            />
          </div>
          {stages.length > 0 && (
            <label className="flex items-center gap-2 text-sm text-surface-200/70">
              <input type="checkbox" checked={form.parallel}
                onChange={e => setForm({...form, parallel: e.target.checked})} />
              Run in parallel with the previous step
            </label>
          )}
          <p className="text-xs text-surface-200/40">
            Leave the model on Auto to let the routing engine pick the best model for the stage type.
          </p>
          <div className="flex gap-2">
            <button onClick={handleAdd} disabled={!form.name || !form.instruction} className="btn btn-primary">
              <Save size={14} aria-hidden /> Add Stage
            </button>
            <button onClick={() => setAdding(false)} className="btn btn-secondary">
              <X size={14} aria-hidden /> Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
