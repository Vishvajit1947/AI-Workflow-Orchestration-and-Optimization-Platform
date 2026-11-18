/**
 * Review step for an AI-generated plan: complexity assessment, the proposed stages and their
 * dependencies, and approval (which creates the workflow).
 */
import { useState } from 'react';
import { ArrowLeft, Check, Loader2, AlertCircle, Boxes } from 'lucide-react';
import { plannerApi, type ObjectiveAnalysisResponse, type PlannerMode, type StagePlan } from '../api/plannerApi';
import { getErrorMessage } from '../lib/errors';

interface PlanReviewProps {
  objective: string;
  plan: ObjectiveAnalysisResponse;
  mode?: PlannerMode;
  onApproved: (workflowId: string) => void;
  onBack: () => void;
}

export default function PlanReview({ objective, plan, mode = 'artifact', onApproved, onBack }: PlanReviewProps) {
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApprove = async () => {
    setApproving(true);
    setError(null);
    try {
      const workflow = await plannerApi.generateWorkflow({ objective, plan, auto_execute: false, mode });
      onApproved(workflow.id);
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to create the workflow. Check the plan and try again.'));
      setApproving(false);
    }
  };

  const stageNames = new Map(plan.stages.map((s) => [s.id, s.name]));

  const renderStage = (stage: StagePlan) => {
    const dependents = plan.stages.filter((s) => s.dependencies.includes(stage.id));
    return (
      <div key={stage.id} className="mb-2">
        <div className="rounded-lg border border-surface-700 bg-surface-900 p-4">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-white">{stage.name}</h3>
            <span className="rounded bg-surface-700/50 px-2 py-0.5 text-xs text-surface-200/70">{stage.stage_type}</span>
          </div>
          <p className="text-sm text-surface-200/80">{stage.description}</p>
          <p className="mt-2 text-xs text-surface-200/50">
            <span className="text-surface-200/70">Expected output:</span> {stage.expected_output}
          </p>
          {stage.dependencies.length > 0 && (
            <p className="mt-1 text-xs text-primary-400/80">
              Depends on: {stage.dependencies.map((id) => stageNames.get(id) || id).join(', ')}
            </p>
          )}
        </div>
        {dependents.length > 0 && (
          <div className="ml-3 mt-2 border-l-2 border-primary-500/30 pl-3 sm:ml-4 sm:pl-4">
            {dependents.map(renderStage)}
          </div>
        )}
      </div>
    );
  };

  const roots = plan.stages.filter((s) => s.dependencies.length === 0);

  return (
    <div className="mx-auto max-w-4xl">
      <button onClick={onBack} className="btn btn-ghost -ml-3 mb-4">
        <ArrowLeft size={16} aria-hidden /> Back
      </button>

      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Review the proposed plan</h1>
        <p className="mt-1 text-sm text-surface-200/60">{objective}</p>
      </div>

      <section className="glass mb-6 rounded-xl p-5" aria-label="Planner assessment">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
          <span
            className={`shrink-0 self-start rounded-lg border px-3 py-1.5 text-sm font-medium ${
              plan.complexity === 'simple'
                ? 'border-primary-500/30 bg-primary-500/15 text-primary-400'
                : 'border-surface-700 bg-surface-700/50 text-surface-200'
            }`}
          >
            {plan.complexity === 'simple' ? 'Simple task' : 'Multi-stage workflow'}
          </span>
          <div className="min-w-0">
            <p className="text-sm text-surface-200/80">{plan.reason}</p>
            {plan.estimated_duration_minutes && (
              <p className="mt-1.5 text-xs text-surface-200/50">
                Estimated duration: ~{plan.estimated_duration_minutes} min
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="glass mb-6 rounded-xl p-5" aria-label="Proposed stages">
        <h2 className="mb-4 text-lg font-semibold">Stages ({plan.stages.length})</h2>
        {(roots.length > 0 ? roots : plan.stages).map(renderStage)}
        {mode === 'project' && (
          <div className="mt-2 flex items-start gap-3 rounded-lg border border-primary-500/30 bg-primary-500/5 p-4">
            <Boxes size={18} className="mt-0.5 shrink-0 text-primary-400" aria-hidden />
            <div>
              <h3 className="font-medium text-white">Build &amp; verify project</h3>
              <p className="mt-1 text-sm text-surface-200/70">
                Added automatically after the file-writing stages: installs dependencies, builds and tests the project
                in an isolated sandbox, and lets the AI fix errors (up to 3 attempts). The result is reported as it is,
                including failures.
              </p>
            </div>
          </div>
        )}
        <p className="mt-4 text-xs text-surface-200/40">
          You can add, remove, reorder and assign models to stages on the workflow page after creating it.
        </p>
      </section>

      {error && (
        <div role="alert" className="mb-6 flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle size={18} className="mt-0.5 shrink-0 text-red-400" aria-hidden />
          <div>
            <p className="mb-1 text-sm font-medium text-red-300">Workflow creation failed</p>
            <p className="text-sm text-red-400/80">{error}</p>
          </div>
        </div>
      )}

      <div className="flex flex-col-reverse gap-3 sm:flex-row">
        <button onClick={onBack} disabled={approving} className="btn btn-secondary px-6 py-3">
          Cancel
        </button>
        <button onClick={handleApprove} disabled={approving} className="btn btn-primary flex-1 px-6 py-3">
          {approving ? (
            <>
              <Loader2 size={18} className="animate-spin" aria-hidden />
              Creating workflow…
            </>
          ) : (
            <>
              <Check size={18} aria-hidden />
              Approve &amp; create workflow
            </>
          )}
        </button>
      </div>
    </div>
  );
}
