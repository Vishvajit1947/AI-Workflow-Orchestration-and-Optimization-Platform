import { useState } from 'react';
import { ArrowLeft, Check, Edit2, Loader2, AlertCircle, GitBranch } from 'lucide-react';
import { plannerApi, type ObjectiveAnalysisResponse, type StagePlan } from '../api/plannerApi';

interface PlanReviewProps {
  objective: string;
  plan: ObjectiveAnalysisResponse;
  onApproved: (workflowId: string) => void;
  onBack: () => void;
}

const STAGE_TYPE_COLORS: Record<string, string> = {
  analysis: 'bg-surface-700/50 text-surface-200/80 border-surface-700',
  design: 'bg-surface-700/50 text-surface-200/80 border-surface-700',
  generation: 'bg-surface-700/50 text-surface-200/80 border-surface-700',
  testing: 'bg-surface-700/50 text-surface-200/80 border-surface-700',
  documentation: 'bg-surface-700/50 text-surface-200/80 border-surface-700',
  review: 'bg-surface-700/50 text-surface-200/80 border-surface-700',
  custom: 'bg-surface-700/50 text-surface-200/80 border-surface-700',
};

export default function PlanReview({ objective, plan: initialPlan, onApproved, onBack }: PlanReviewProps) {
  const [plan, setPlan] = useState(initialPlan);
  const [editing, setEditing] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApprove = async () => {
    setApproving(true);
    setError(null);

    try {
      const workflow = await plannerApi.generateWorkflow({
        objective,
        plan,
        auto_execute: false,
      });
      onApproved(workflow.id);
    } catch (err: any) {
      console.error('Workflow generation failed:', err);
      const detail = err.response?.data?.detail;
      // FastAPI validation errors (422) arrive as a list of objects, not a string
      setError(
        Array.isArray(detail)
          ? detail.map((d: any) => d.msg).join('; ')
          : (typeof detail === 'string' && detail) ||
            'Failed to generate workflow. Please check the plan and try again.'
      );
      setApproving(false);
    }
  };

  const renderStageTree = () => {
    // Build dependency graph
    const stageMap = new Map(plan.stages.map(s => [s.id, s]));
    const roots = plan.stages.filter(s => s.dependencies.length === 0);

    const renderStage = (stage: StagePlan, level: number = 0) => {
      const deps = plan.stages.filter(s => s.dependencies.includes(stage.id));
      
      return (
        <div key={stage.id} className="mb-2">
          <div className={`flex items-start gap-3 p-4 bg-surface-900 border border-surface-700 rounded-lg hover:border-primary-500/40 transition-colors ${level > 0 ? 'ml-8' : ''}`}>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <h4 className="font-medium text-white">{stage.name}</h4>
                <span className={`px-2 py-0.5 text-xs rounded border ${STAGE_TYPE_COLORS[stage.stage_type] || STAGE_TYPE_COLORS.custom}`}>
                  {stage.stage_type}
                </span>
              </div>
              <p className="text-sm text-surface-200/80 mb-2">{stage.description}</p>
              <p className="text-xs text-surface-200/60">
                Expected Output: {stage.expected_output}
              </p>
              {stage.dependencies.length > 0 && (
                <p className="text-xs text-primary-400/80 mt-1">
                  Depends on: {stage.dependencies.map(depId => stageMap.get(depId)?.name || depId).join(', ')}
                </p>
              )}
            </div>
          </div>
          {deps.length > 0 && (
            <div className="ml-4 mt-2 border-l-2 border-primary-500/30 pl-4">
              {deps.map(dep => renderStage(dep, level + 1))}
            </div>
          )}
        </div>
      );
    };

    if (roots.length === 0) {
      // Fallback: show all stages
      return plan.stages.map(s => renderStage(s, 0));
    }

    return roots.map(s => renderStage(s, 0));
  };

  return (
    <div className="max-w-5xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-surface-200/50 hover:text-white mb-6 transition-colors">
        <ArrowLeft size={16} /> Back
      </button>

      <div className="mb-8">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold mb-2">AI Workflow Plan</h1>
            <p className="text-surface-200/60">{objective}</p>
          </div>
        </div>

        {/* Complexity Badge */}
        <div className="glass rounded-xl p-6 mb-6">
          <div className="flex items-start gap-4">
            <div className={`flex-shrink-0 px-4 py-2 rounded-lg font-medium ${
              plan.complexity === 'simple' 
                ? 'bg-primary-500/15 text-primary-400 border border-primary-500/30' 
                : 'bg-surface-700/50 text-surface-200 border border-surface-700'
            }`}>
              {plan.complexity === 'simple' ? 'Simple Task' : 'Complex Workflow'}
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-surface-200/70 mb-1">Analysis</h3>
              <p className="text-sm text-surface-200/80">{plan.reason}</p>
              {plan.estimated_duration_minutes && (
                <p className="text-xs text-surface-200/50 mt-2">
                  Estimated duration: ~{plan.estimated_duration_minutes} minutes
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Stages */}
        <div className="glass rounded-xl p-6 mb-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <GitBranch size={20} className="text-primary-400" />
              Workflow Stages ({plan.stages.length})
            </h2>
            {!editing && (
              <button
                onClick={() => setEditing(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-surface-700/50 hover:bg-surface-700 rounded-lg transition-colors"
              >
                <Edit2 size={14} />
                Edit Plan
              </button>
            )}
          </div>

          {renderStageTree()}

          {editing && (
            <div className="mt-4 p-4 bg-surface-800/50 border border-surface-700/50 rounded-lg">
              <div className="flex items-start gap-2 text-sm text-surface-200/60 mb-3">
                <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
                <p>
                  Advanced editing coming soon. For now, you can go back and modify your objective, 
                  or use the manual workflow builder for full control.
                </p>
              </div>
              <button
                onClick={() => setEditing(false)}
                className="px-3 py-1.5 text-sm bg-surface-700/50 hover:bg-surface-700 rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="glass rounded-xl p-4 mb-6 bg-red-500/10 border border-red-500/30">
            <div className="flex items-start gap-2">
              <AlertCircle size={18} className="text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-300 mb-1">Workflow Generation Failed</p>
                <p className="text-sm text-red-400/80">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleApprove}
            disabled={approving}
            className="flex-1 flex items-center justify-center gap-2 px-6 py-3.5 bg-primary-600 hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium transition-all shadow-lg shadow-primary-600/25"
          >
            {approving ? (
              <>
                <Loader2 size={20} className="animate-spin" />
                Creating Workflow...
              </>
            ) : (
              <>
                <Check size={20} />
                Approve & Create Workflow
              </>
            )}
          </button>
          <button
            onClick={onBack}
            disabled={approving}
            className="px-6 py-3.5 bg-surface-700/50 hover:bg-surface-700 disabled:opacity-50 rounded-lg font-medium transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

