import { useEffect, useState } from 'react';
import { Plus, Trash2, Save, X, ChevronDown, ChevronUp } from 'lucide-react';
import { stageApi } from '../lib/stages';
import { modelsApi } from '../api/modelsApi';
import { ModelSelect } from './ModelSelect';
import type { Stage } from '../types';
import type { ModelProfile } from '../types/routing';

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

  useEffect(() => {
    modelsApi.listModels()
      .then(setModels)
      .catch((err) => console.error('Failed to load models:', err));
  }, []);

  const handleModelChange = async (stage: Stage, modelName: string | null) => {
    await stageApi.update(stage.id, { model_preference: modelName });
    onUpdate();
  };

  // Stages sharing a stage_order run in parallel; the step number counts distinct orders
  const orders = [...new Set(stages.map((s) => s.stage_order))].sort((a, b) => a - b);
  const lastOrder = orders.length ? orders[orders.length - 1] : -1;
  const orderCount = (order: number) => stages.filter((s) => s.stage_order === order).length;

  const handleAdd = async () => {
    if (!form.name || !form.instruction) return;
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
    onUpdate();
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this stage?')) return;
    await stageApi.delete(id);
    onUpdate();
  };

  // Swap stage_order with the neighbour (keeps parallel groups intact, unlike renumbering)
  const swapWith = async (index: number, other: number) => {
    const a = stages[index], b = stages[other];
    if (!a || !b || a.stage_order === b.stage_order) return;
    await stageApi.update(a.id, { stage_order: b.stage_order });
    await stageApi.update(b.id, { stage_order: a.stage_order });
    onUpdate();
  };

  const handleMoveUp = (index: number) => swapWith(index, index - 1);
  const handleMoveDown = (index: number) => swapWith(index, index + 1);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Stages ({stages.length})</h2>
        <button
          onClick={() => setAdding(true)}
          className="flex items-center gap-1.5 text-sm text-primary-400 hover:text-primary-300 transition-colors"
        >
          <Plus size={16} /> Add Stage
        </button>
      </div>

      {/* Stage list */}
      <div className="space-y-3">
        {stages.map((stage, idx) => (
          <div key={stage.id} className="glass rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="flex flex-col gap-0.5">
                <button onClick={() => handleMoveUp(idx)} className="text-surface-200/30 hover:text-white transition-colors" disabled={idx === 0}>
                  <ChevronUp size={14} />
                </button>
                <button onClick={() => handleMoveDown(idx)} className="text-surface-200/30 hover:text-white transition-colors" disabled={idx === stages.length - 1}>
                  <ChevronDown size={14} />
                </button>
              </div>
              <div className="w-8 h-8 rounded-full bg-primary-500/20 flex items-center justify-center text-sm font-bold text-primary-400 shrink-0">
                {orders.indexOf(stage.stage_order) + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
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
              <button onClick={() => handleDelete(stage.id)} className="text-surface-200/30 hover:text-red-400 transition-colors">
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
          <input type="text" placeholder="Stage name" value={form.name}
            onChange={e => setForm({...form, name: e.target.value})}
            className="w-full px-3 py-2 bg-surface-800/50 border border-surface-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-primary-500/50" />
          <textarea placeholder="Instruction for the LLM..." value={form.instruction}
            onChange={e => setForm({...form, instruction: e.target.value})} rows={3}
            className="w-full px-3 py-2 bg-surface-800/50 border border-surface-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-primary-500/50 resize-none" />
          <div className="flex gap-3">
            <select value={form.stage_type} onChange={e => setForm({...form, stage_type: e.target.value})}
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
            <button onClick={handleAdd} disabled={!form.name || !form.instruction}
              className="flex items-center gap-1.5 px-4 py-2 bg-primary-600 hover:bg-primary-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-all">
              <Save size={14} /> Add Stage
            </button>
            <button onClick={() => setAdding(false)}
              className="flex items-center gap-1.5 px-4 py-2 bg-surface-700/50 hover:bg-surface-700 rounded-lg text-sm transition-colors">
              <X size={14} /> Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
