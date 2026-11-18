/**
 * Review step for an AI-generated plan: the planner's assessment, the proposed stages grouped
 * into execution steps (stages in one step run in parallel), light editing (rename, describe,
 * remove) and approval, which creates the workflow from the edited plan.
 */
import { useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  ArrowLeft, Check, Loader2, Boxes, Pencil, Clock, Layers, GitMerge, Sparkles, X, RotateCcw,
} from 'lucide-react';
import { plannerApi, type ObjectiveAnalysisResponse, type PlannerMode, type StagePlan } from '../api/plannerApi';
import { getErrorMessage } from '../lib/errors';
import { PlannerSteps } from './planner/PlannerSteps';
import { Notice } from './ui/States';
import { RISE, transition } from '../lib/motion';

/** Seconds between successive plan levels appearing */
const LEVEL_STAGGER = 0.08;

interface PlanReviewProps {
  objective: string;
  plan: ObjectiveAnalysisResponse;
  mode?: PlannerMode;
  onApproved: (workflowId: string) => void;
  onBack: () => void;
}

/** Group stages into execution levels: a stage runs one level after its latest dependency. */
export const planLevels = (stages: StagePlan[]): StagePlan[][] => {
  const byId = new Map(stages.map((s) => [s.id, s]));
  const memo = new Map<string, number>();
  const level = (s: StagePlan, seen: Set<string>): number => {
    if (memo.has(s.id)) return memo.get(s.id)!;
    if (seen.has(s.id)) return 0; // cycle guard: the backend validates the graph
    seen.add(s.id);
    const deps = s.dependencies.map((d) => byId.get(d)).filter(Boolean) as StagePlan[];
    const value = deps.length ? 1 + Math.max(...deps.map((d) => level(d, seen))) : 0;
    memo.set(s.id, value);
    return value;
  };
  const levels: StagePlan[][] = [];
  stages.forEach((s) => {
    const l = level(s, new Set());
    (levels[l] ??= []).push(s);
  });
  return levels.filter(Boolean);
};

const STAGE_TYPE_LABEL: Record<string, string> = {
  analysis: 'Analysis', design: 'Design', generation: 'Generation', testing: 'Testing',
  documentation: 'Documentation', review: 'Review', custom: 'Custom',
};

export default function PlanReview({ objective, plan, mode = 'artifact', onApproved, onBack }: PlanReviewProps) {
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stages, setStages] = useState<StagePlan[]>(plan.stages);
  const [editing, setEditing] = useState<string | null>(null);

  const edited = stages !== plan.stages;
  const levels = useMemo(() => planLevels(stages), [stages]);
  const stageNames = new Map(stages.map((s) => [s.id, s.name]));
  const maxParallel = Math.max(0, ...levels.map((l) => l.length));

  const handleApprove = async () => {
    setApproving(true);
    setError(null);
    try {
      const workflow = await plannerApi.generateWorkflow({ objective, plan: { ...plan, stages }, auto_execute: false, mode });
      onApproved(workflow.id);
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to create the workflow. Check the plan and try again.'));
      setApproving(false);
    }
  };

  const updateStage = (id: string, changes: Partial<StagePlan>) =>
    setStages((prev) => prev.map((s) => (s.id === id ? { ...s, ...changes } : s)));

  // Removing a stage also removes it from the dependency lists of the stages after it
  const removeStage = (id: string) =>
    setStages((prev) =>
      prev.filter((s) => s.id !== id).map((s) => ({ ...s, dependencies: s.dependencies.filter((d) => d !== id) })),
    );

  return (
    <div className="mx-auto max-w-6xl">
      <PlannerSteps current={approving ? 2 : 1} />

      <button onClick={onBack} disabled={approving} className="btn btn-ghost btn-sm -ml-3 mb-4">
        <ArrowLeft size={15} aria-hidden /> Back
      </button>

      <div className="mb-8">
        <p className="eyebrow mb-3 flex items-center gap-1.5"><Sparkles size={13} className="text-primary" aria-hidden /> Proposed plan</p>
        <h1 className="text-[26px] font-medium leading-tight tracking-[0.01em] text-ink sm:text-heading-2">Review the proposed plan</h1>
        <p className="mt-2 max-w-3xl text-[15px] font-light leading-relaxed text-ink-secondary">{objective}</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        {/* Stages, grouped by execution step */}
        <section aria-label="Proposed stages" className="min-w-0">
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-[17px] font-medium text-ink">Stages ({stages.length})</h2>
            {edited && (
              <button type="button" onClick={() => { setStages(plan.stages); setEditing(null); }} className="btn btn-ghost btn-sm -mr-2">
                <RotateCcw size={13} aria-hidden /> Reset edits
              </button>
            )}
          </div>

          {stages.length === 0 && (
            <p className="card-soft px-5 py-6 text-sm text-ink-secondary">
              The planner proposed no stages. Go back and add detail to the objective, or create the workflow and add stages yourself.
            </p>
          )}

          <ol className="space-y-6">
            <AnimatePresence initial>
            {levels.map((group, i) => (
              <motion.li
                key={i}
                className="relative"
                layout="position"
                initial={{ opacity: 0, y: RISE }}
                animate={{ opacity: 1, y: 0, transition: { ...transition.enter, delay: 0.1 + i * LEVEL_STAGGER } }}
                exit={{ opacity: 0, transition: transition.exit }}
              >
                <div className="mb-2.5 flex items-center gap-2.5">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-night text-[11px] text-on-dark tabular" aria-hidden>
                    {i + 1}
                  </span>
                  <span className="eyebrow">Step {i + 1}</span>
                  {group.length > 1 && <span className="chip">runs {group.length} in parallel</span>}
                </div>
                <div className={`grid gap-3 border-l border-hairline-strong pl-5 ml-3 ${group.length > 1 ? 'md:grid-cols-2' : ''}`}>
                  <AnimatePresence mode="popLayout" initial={false}>
                    {group.map((stage) => (
                      <motion.div
                        key={stage.id}
                        className="min-w-0"
                        layout="position"
                        transition={transition.state}
                        exit={{ opacity: 0, scale: 0.97, transition: transition.exit }}
                      >
                        <StageCard
                          stage={stage}
                          dependencyNames={stage.dependencies.map((d) => stageNames.get(d) || d)}
                          editing={editing === stage.id}
                          disabled={approving}
                          onEdit={() => setEditing(stage.id)}
                          onDone={() => setEditing(null)}
                          onChange={(changes) => updateStage(stage.id, changes)}
                          onRemove={stages.length > 1 ? () => removeStage(stage.id) : undefined}
                        />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </motion.li>
            ))}
            </AnimatePresence>

            {mode === 'project' && (
              <motion.li
                layout="position"
                initial={{ opacity: 0, y: RISE }}
                animate={{ opacity: 1, y: 0, transition: { ...transition.enter, delay: 0.1 + levels.length * LEVEL_STAGGER } }}
              >
                <div className="mb-2.5 flex items-center gap-2.5">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-white" aria-hidden>
                    <Boxes size={12} />
                  </span>
                  <span className="eyebrow">Final step · added automatically</span>
                </div>
                <div className="ml-3 border-l border-dashed border-primary/40 pl-5">
                  <div className="card-tint flex items-start gap-3 p-4 sm:p-5">
                    <Boxes size={18} className="mt-0.5 shrink-0 text-primary" aria-hidden />
                    <div>
                      <h3 className="text-[15px] font-medium text-ink">Build &amp; verify project</h3>
                      <p className="mt-1 text-sm leading-relaxed text-ink-secondary">
                        Added automatically after the file-writing stages: installs dependencies, builds and tests the project
                        in an isolated sandbox, and lets the AI fix errors (up to 3 attempts). The result is reported as it is,
                        including failures.
                      </p>
                    </div>
                  </div>
                </div>
              </motion.li>
            )}
          </ol>
        </section>

        {/* Assessment + approval */}
        <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start" aria-label="Planner assessment">
          <div className="card p-5">
            <p className="eyebrow mb-3">Planner assessment</p>
            <span className={`chip ${plan.complexity === 'simple' ? '!bg-success-soft !text-success' : '!bg-info-soft !text-info'}`}>
              {plan.complexity === 'simple' ? 'Simple task' : 'Multi-stage workflow'}
            </span>
            <p className="mt-3 text-sm leading-relaxed text-ink-secondary">{plan.reason}</p>
            <dl className="mt-5 grid grid-cols-2 gap-2 text-sm">
              <Fact icon={Layers} label="Stages" value={String(stages.length)} />
              <Fact icon={GitMerge} label="Steps" value={String(levels.length)} />
              <Fact icon={Sparkles} label="Max parallel" value={String(maxParallel)} />
              {plan.estimated_duration_minutes ? (
                <Fact icon={Clock} label="Estimated" value={`~${plan.estimated_duration_minutes} min`} />
              ) : (
                <Fact icon={Boxes} label="Output" value={mode === 'project' ? 'Project' : 'Artifacts'} />
              )}
            </dl>
          </div>

          {error && (
            <Notice tone="danger" title="Workflow creation failed">{error}</Notice>
          )}

          <div className="card p-5">
            <button onClick={handleApprove} disabled={approving || editing !== null} className="btn btn-primary h-11 w-full">
              {approving ? (
                <>
                  <Loader2 size={17} className="animate-spin" aria-hidden />
                  Creating workflow…
                </>
              ) : (
                <>
                  <Check size={17} aria-hidden />
                  Approve &amp; create workflow
                </>
              )}
            </button>
            <button onClick={onBack} disabled={approving} className="btn btn-outline mt-2 w-full">
              Cancel
            </button>
            <p className="mt-4 text-xs leading-relaxed text-ink-muted">
              {editing !== null
                ? 'Finish editing the open stage to continue.'
                : 'Nothing runs yet. You can add, remove, reorder and assign models to stages on the workflow page after creating it.'}
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Fact({ icon: Icon, label, value }: { icon: typeof Clock; label: string; value: string }) {
  return (
    <div className="rounded-[10px] bg-lavender-soft px-3 py-2.5">
      <dt className="flex items-center gap-1.5 text-xs text-ink-muted"><Icon size={12} aria-hidden /> {label}</dt>
      <dd className="mt-1 font-medium text-ink tabular">{value}</dd>
    </div>
  );
}

function StageCard({
  stage, dependencyNames, editing, disabled, onEdit, onDone, onChange, onRemove,
}: {
  stage: StagePlan;
  dependencyNames: string[];
  editing: boolean;
  disabled: boolean;
  onEdit: () => void;
  onDone: () => void;
  onChange: (changes: Partial<StagePlan>) => void;
  onRemove?: () => void;
}) {
  if (editing) {
    return (
      <div className="card animate-fade-in space-y-3 border-primary/40 p-4 ring-4 ring-primary/[0.08]">
        <div>
          <label htmlFor={`plan-name-${stage.id}`} className="label">Stage name</label>
          <input id={`plan-name-${stage.id}`} className="input" value={stage.name}
                 onChange={(e) => onChange({ name: e.target.value })} />
        </div>
        <div>
          <label htmlFor={`plan-desc-${stage.id}`} className="label">Description</label>
          <textarea id={`plan-desc-${stage.id}`} className="input resize-y" rows={3} value={stage.description}
                    onChange={(e) => onChange({ description: e.target.value })} />
        </div>
        <div>
          <label htmlFor={`plan-out-${stage.id}`} className="label">Expected output</label>
          <input id={`plan-out-${stage.id}`} className="input" value={stage.expected_output}
                 onChange={(e) => onChange({ expected_output: e.target.value })} />
        </div>
        <div className="flex justify-end">
          <button type="button" onClick={onDone} disabled={!stage.name.trim()} className="btn btn-secondary btn-sm">
            <Check size={13} aria-hidden /> Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="card group p-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[15px] font-medium text-ink">{stage.name}</h3>
            <span className="chip">{STAGE_TYPE_LABEL[stage.stage_type] ?? stage.stage_type}</span>
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-secondary">{stage.description}</p>
        </div>
        <div className="-mr-1.5 -mt-1 flex shrink-0 gap-0.5 sm:opacity-0 sm:transition-opacity sm:focus-within:opacity-100 sm:group-hover:opacity-100">
          <button type="button" onClick={onEdit} disabled={disabled} aria-label={`Edit ${stage.name}`}
                  className="btn btn-ghost btn-icon btn-sm">
            <Pencil size={13} />
          </button>
          {onRemove && (
            <button type="button" onClick={onRemove} disabled={disabled} aria-label={`Remove ${stage.name}`}
                    className="btn btn-ghost btn-icon btn-sm hover:!text-danger">
              <X size={14} />
            </button>
          )}
        </div>
      </div>
      <div className="mt-3 space-y-1 border-t border-hairline pt-3 text-xs">
        <p className="text-ink-secondary">
          <span className="text-ink-muted">Expected output:</span> {stage.expected_output}
        </p>
        {dependencyNames.length > 0 && (
          <p className="text-ink-secondary">
            <span className="text-ink-muted">Depends on:</span> {dependencyNames.join(', ')}
          </p>
        )}
      </div>
    </div>
  );
}

