/**
 * A workflow's stages: step numbers (stages sharing a stage_order run in parallel), reorder,
 * per-stage model preference, delete, and the add-stage form.
 */
import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Plus, Trash2, X, ChevronDown, ChevronUp, Layers } from 'lucide-react';
import { stageApi } from '../lib/stages';
import { modelsApi } from '../api/modelsApi';
import { ModelSelect } from './ModelSelect';
import type { Stage } from '../types';
import type { ModelProfile } from '../types/routing';
import { getErrorMessage } from '../lib/errors';
import { useConfirm } from './ui/Dialog';
import { Notice } from './ui/States';
import { Collapse } from './motion/Motion';
import { RISE, transition } from '../lib/motion';

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
  const [confirm, confirmDialog] = useConfirm();

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

  const handleDelete = async (stage: Stage) => {
    const ok = await confirm({
      title: 'Delete stage?',
      message: <>“{stage.name}” will be removed from this workflow.</>,
      confirmLabel: 'Delete stage',
      destructive: true,
    });
    if (ok) await mutate(() => stageApi.delete(stage.id));
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
    <section className="card min-w-0" aria-label="Stages">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pb-4 pt-5 sm:px-6">
        <div>
          <h2 className="text-[17px] font-medium text-ink">Stages ({stages.length})</h2>
          <p className="mt-1 text-[13px] text-ink-muted">Stages that share a step number run in parallel.</p>
        </div>
        <button onClick={() => setAdding(true)} disabled={adding} className="btn btn-secondary">
          <Plus size={15} aria-hidden /> Add Stage
        </button>
      </div>

      {error && <Notice tone="danger" className="mx-5 mb-4 sm:mx-6" onDismiss={() => setError(null)}>Stage update failed: {error}</Notice>}

      {stages.length === 0 && !adding && (
        <div className="mx-5 mb-5 flex items-center gap-3 rounded-card bg-lavender-soft px-4 py-5 text-sm text-ink-secondary sm:mx-6">
          <Layers size={18} className="shrink-0 text-primary" aria-hidden />
          This workflow has no stages yet. Add one to be able to execute it.
        </div>
      )}

      {/* Stage list */}
      {stages.length > 0 && (
        <ul className="border-t border-hairline">
          <AnimatePresence initial={false}>
          {stages.map((stage, idx) => {
            const parallel = orderCount(stage.stage_order) > 1;
            return (
              <motion.li key={stage.id} data-testid="stage-row"
                  // Reordering glides rows to their new places; new stages settle in
                  layout="position"
                  initial={{ opacity: 0, y: RISE }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, transition: transition.exit }}
                  transition={transition.state}
                  className="flex flex-wrap items-center gap-x-3 gap-y-2.5 border-b border-hairline px-4 py-3.5 last:border-b-0 sm:flex-nowrap sm:px-6">
                <div className="flex flex-col">
                  <button onClick={() => handleMoveUp(idx)} aria-label={`Move ${stage.name} up`} disabled={idx === 0}
                    className="rounded text-ink-faint transition-colors hover:text-ink disabled:opacity-30 disabled:hover:text-ink-faint">
                    <ChevronUp size={15} />
                  </button>
                  <button onClick={() => handleMoveDown(idx)} aria-label={`Move ${stage.name} down`} disabled={idx === stages.length - 1}
                    className="rounded text-ink-faint transition-colors hover:text-ink disabled:opacity-30 disabled:hover:text-ink-faint">
                    <ChevronDown size={15} />
                  </button>
                </div>
                <span
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[13px] tabular ${
                    parallel ? 'bg-primary/10 text-primary-700 ring-1 ring-primary/25' : 'bg-lavender text-ink'
                  }`}
                  title={`Step ${orders.indexOf(stage.stage_order) + 1}`}
                >
                  {orders.indexOf(stage.stage_order) + 1}
                </span>
                <div className="min-w-0 flex-1 basis-40">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-sm font-book text-ink">{stage.name}</span>
                    {parallel && (
                      <span className="chip !bg-primary/10 !py-0 !text-primary-700" title="Runs at the same time as the other stages of this step">
                        parallel
                      </span>
                    )}
                    {stage.stage_type && <span className="chip !py-0">{stage.stage_type}</span>}
                  </div>
                  <p className="mt-1 truncate text-[13px] text-ink-muted" title={stage.instruction}>{stage.instruction}</p>
                </div>
                <div className="flex w-full items-center gap-2 pl-[4.25rem] sm:w-auto sm:pl-0">
                  <ModelSelect
                    aria-label={`Model for ${stage.name}`}
                    models={models}
                    stageType={stage.stage_type}
                    value={stage.model_preference}
                    onChange={(modelName) => handleModelChange(stage, modelName)}
                    className={`input input-sm w-full min-w-0 sm:w-56 ${stage.model_preference ? '!text-primary-700' : '!text-ink-secondary'}`}
                  />
                  <button onClick={() => handleDelete(stage)} aria-label={`Delete ${stage.name}`}
                    className="btn btn-ghost btn-icon btn-sm shrink-0 text-ink-faint hover:!text-danger">
                    <Trash2 size={15} />
                  </button>
                </div>
              </motion.li>
            );
          })}
          </AnimatePresence>
        </ul>
      )}

      {/* Add form */}
      <Collapse open={adding}>
        <div className="border-t border-hairline bg-surface-tint px-5 py-5 sm:px-6">
          <div className="space-y-4">
            <h3 className="text-[15px] font-medium text-ink">New stage</h3>
            <input type="text" aria-label="Stage name" placeholder="Stage name" value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              className="input" />
            <textarea aria-label="Instruction" placeholder="Instruction for the LLM..." value={form.instruction}
              onChange={e => setForm({ ...form, instruction: e.target.value })} rows={3}
              className="input resize-y" />
            <div className="flex flex-col gap-3 sm:flex-row">
              <select aria-label="Stage type" value={form.stage_type} onChange={e => setForm({ ...form, stage_type: e.target.value })}
                className="input sm:w-52">
                <option value="">Type (optional)</option>
                {stageTypes.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <ModelSelect
                aria-label="Model preference"
                models={models}
                stageType={form.stage_type}
                value={form.model_preference || null}
                onChange={(modelName) => setForm({ ...form, model_preference: modelName || '' })}
                className="input flex-1"
              />
            </div>
            {stages.length > 0 && (
              <label className="flex cursor-pointer items-center gap-2.5 text-sm text-ink-secondary">
                <input type="checkbox" role="switch" className="switch" checked={form.parallel}
                  onChange={e => setForm({ ...form, parallel: e.target.checked })} />
                Run in parallel with the previous step
              </label>
            )}
            <p className="text-xs text-ink-muted">
              Leave the model on Auto to let the routing engine pick the best model for the stage type.
            </p>
            <div className="flex flex-wrap gap-2">
              <button onClick={handleAdd} disabled={!form.name || !form.instruction} className="btn btn-primary">
                <Plus size={14} aria-hidden /> Add Stage
              </button>
              <button onClick={() => setAdding(false)} className="btn btn-outline">
                <X size={14} aria-hidden /> Cancel
              </button>
            </div>
          </div>
        </div>
      </Collapse>
      {confirmDialog}
    </section>
  );
}
