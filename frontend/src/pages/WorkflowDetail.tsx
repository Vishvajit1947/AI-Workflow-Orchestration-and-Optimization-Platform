import { useParams, Link, useNavigate } from 'react-router-dom';
import { useState, useEffect, useCallback, useRef } from 'react';
import { Edit, Trash2, Play, Loader2, Layers, Target, GitBranch } from 'lucide-react';
import { useWorkflow } from '../hooks/useWorkflows';
import { workflowApi } from '../lib/workflows';
import { stageApi } from '../lib/stages';
import { executionApi } from '../api/executionApi';
import StageEditor from '../components/StageEditor';
import { ExecutionConfigModal, type ExecutionConfig } from '../components/ExecutionConfigModal';
import { ExecutionResults } from '../components/ExecutionResults';
import { ExecutionMonitor } from '../components/ExecutionMonitor';
import { DAGLegend, DAGVisualization } from '../components/DAGVisualization';
import { ProjectPanel } from '../components/project/ProjectPanel';
import { PageHeader } from '../components/ui/PageHeader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState, ErrorState, LoadingState, Notice } from '../components/ui/States';
import { useConfirm } from '../components/ui/Dialog';
import type { Stage } from '../types';
import type { ExecutionDetailResponse, WorkflowDAG } from '../types/execution';
import { getErrorMessage } from '../lib/errors';

export default function WorkflowDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { workflow, loading, error, refetch } = useWorkflow(id);
  const [stages, setStages] = useState<Stage[]>([]);
  const [stagesLoading, setStagesLoading] = useState(false);
  const [showExecuteModal, setShowExecuteModal] = useState(false);
  const [execution, setExecution] = useState<ExecutionDetailResponse | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [liveExecutionId, setLiveExecutionId] = useState<string | null>(null);
  const [dag, setDag] = useState<WorkflowDAG | null>(null);
  const [dagError, setDagError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const finishedExecutionId = useRef<string | null>(null);
  const [confirm, confirmDialog] = useConfirm();

  const fetchStages = async () => {
    if (!id) return;
    setStagesLoading(true);
    try {
      const data = await stageApi.list(id);
      setStages(data);
    } catch (err) {
      console.error('Failed to fetch stages:', err);
    } finally {
      setStagesLoading(false);
    }
  };

  useEffect(() => {
    if (!id) return;
    fetchStages();
    loadLatestExecution();
    // Reattach to an execution still running on the server (e.g. after a page reload)
    executionApi.getLiveExecution(id)
      .then((live) => { setLiveExecutionId(live.execution_id); setIsExecuting(true); })
      .catch(() => { /* none running */ });
  }, [id]);

  // Execution plan: refetch whenever the stages change
  useEffect(() => {
    if (!id || stages.length === 0) {
      setDag(null);
      return;
    }
    executionApi.getDag(id)
      .then((data) => { setDag(data); setDagError(null); })
      .catch((err: unknown) => { setDag(null); setDagError(getErrorMessage(err)); });
  }, [id, stages]);

  const loadLatestExecution = async () => {
    if (!id) return;
    try {
      setExecution(await executionApi.getLatestExecution(id));
    } catch {
      // No executions yet
    }
  };

  const handleDelete = async () => {
    if (!id || !workflow) return;
    const ok = await confirm({
      title: 'Delete workflow?',
      message: <>“{workflow.name}” and its stages will be deleted. This cannot be undone.</>,
      confirmLabel: 'Delete workflow',
      destructive: true,
    });
    if (!ok) return;
    try {
      await workflowApi.delete(id);
      navigate('/workflows');
    } catch (err: unknown) {
      setActionError(`Could not delete the workflow: ${getErrorMessage(err)}`);
    }
  };

  const handleStageUpdate = () => {
    fetchStages();
    refetch();
  };

  const handleExecute = async (config: ExecutionConfig) => {
    if (!id) return;
    setIsExecuting(true);
    setActionError(null);
    try {
      // Run in the background and follow it live
      const response = await executionApi.startExecution(id, { ...config, background: true });
      setLiveExecutionId(response.execution_id);
    } catch (err: unknown) {
      setActionError(`Execution failed: ${getErrorMessage(err)}`);
      setIsExecuting(false);
    }
  };

  const handleExecutionFinished = useCallback(async () => {
    // Handle each execution's completion once, even if the monitor re-reports it
    if (finishedExecutionId.current === liveExecutionId) return;
    finishedExecutionId.current = liveExecutionId;
    setIsExecuting(false);
    if (liveExecutionId) {
      try {
        setExecution(await executionApi.getExecution(liveExecutionId));
      } catch {
        // No stage records (e.g. cancelled before any stage ran)
      }
    }
    fetchStages();
    refetch();
  }, [liveExecutionId]);

  // Only block the page on the first load; background refetches keep the current view mounted
  if (loading && !workflow) return <LoadingState label="Loading workflow…" />;
  if (error) return <ErrorState title="Could not load the workflow" message={error} onRetry={refetch} />;
  if (!id) return <ErrorState message="Invalid workflow ID" />;
  if (!workflow) {
    return (
      <EmptyState icon={GitBranch} title="Workflow not found."
        action={<Link to="/workflows" className="btn btn-secondary btn-sm">Back to workflows</Link>} />
    );
  }

  const canExecute = !isExecuting && stages.length > 0 && !dagError;

  return (
    <div>
      <PageHeader
        eyebrow="Workflow"
        title={workflow.name}
        description={workflow.description || undefined}
        meta={
          <>
            {workflow.status && <StatusBadge status={workflow.status} />}
            <span className="chip"><Layers size={12} aria-hidden /> {stages.length} {stages.length === 1 ? 'stage' : 'stages'}</span>
            {stages.some((s) => s.config?.kind === 'project_build') && <span className="chip">Complete project</span>}
          </>
        }
        actions={
          <>
            <button onClick={handleDelete} className="btn btn-ghost hover:!bg-danger/10 hover:!text-danger" aria-label="Delete">
              <Trash2 size={15} aria-hidden /> <span className="hidden sm:inline">Delete</span>
            </button>
            <Link to={`/workflows/${id}/edit`} className="btn btn-outline">
              <Edit size={14} aria-hidden /> Edit details
            </Link>
            <button
              onClick={() => setShowExecuteModal(true)}
              disabled={!canExecute}
              className="btn btn-primary"
              title={stages.length === 0 ? 'Add a stage first' : dagError ? 'Fix the execution plan first' : undefined}
            >
              {isExecuting ? <Loader2 size={15} className="animate-spin" aria-hidden /> : <Play size={15} aria-hidden />}
              {isExecuting ? 'Executing...' : 'Execute Workflow'}
            </button>
          </>
        }
      />

      {workflow.objective && (
        <div className="card-soft mb-6 flex items-start gap-3 px-4 py-3.5 text-sm sm:px-5">
          <Target size={16} className="mt-0.5 shrink-0 text-primary" aria-hidden />
          <p className="min-w-0 leading-relaxed text-ink-secondary">
            <span className="font-book text-ink">Objective</span>
            <span className="mx-2 text-ink-faint" aria-hidden>·</span>
            {workflow.objective}
          </p>
        </div>
      )}

      {actionError && <Notice tone="danger" className="mb-6" onDismiss={() => setActionError(null)}>{actionError}</Notice>}

      <div className="space-y-6">
        {/* Live monitor comes first while a run is in progress */}
        {liveExecutionId && (
          <div key={liveExecutionId} className="animate-fade-in-up">
            <ExecutionMonitor executionId={liveExecutionId} onFinished={handleExecutionFinished} />
          </div>
        )}

        {/* Stages */}
        {stagesLoading && stages.length === 0 ? (
          <LoadingState label="Loading stages…" />
        ) : (
          <StageEditor workflowId={id!} stages={stages} onUpdate={handleStageUpdate} />
        )}

        {/* Execution plan (when idle) */}
        {!liveExecutionId && (dag || dagError) && (
          <section className="card min-w-0 p-5 sm:p-6" aria-label="Execution plan">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-[17px] font-medium text-ink">Execution Plan</h2>
                <p className="mt-1 text-[13px] text-ink-muted">The dependency graph the engine will run. Columns run left to right.</p>
              </div>
              {dag && (
                <dl className="flex flex-wrap gap-2 text-xs">
                  <PlanFact label="Levels" value={dag.levels.length} />
                  <PlanFact label="Max parallel" value={dag.max_width} />
                  <PlanFact label="Parallelism" value={`${dag.parallelism_factor.toFixed(2)}x`} />
                  <PlanFact label="Critical path" value={`${dag.critical_path.length} stage${dag.critical_path.length === 1 ? '' : 's'}`} />
                </dl>
              )}
            </div>
            {dagError ? (
              <Notice tone="danger" title="The workflow can't run as configured">{dagError}</Notice>
            ) : dag && (
              <div className="space-y-3">
                <DAGVisualization dag={dag} />
                <DAGLegend live={false} />
              </div>
            )}
          </section>
        )}

        {/* Complete Project workflows: build status, logs, repairs, files, ZIP */}
        {stages.some((s) => s.config?.kind === 'project_build') && (
          <ProjectPanel workflowId={id} active={isExecuting} />
        )}

        {/* Execution Results */}
        {execution && (
          <div key={execution.summary.execution_id} className="animate-fade-in-up">
            <ExecutionResults execution={execution} />
          </div>
        )}
      </div>

      {/* Execution Config Modal */}
      <ExecutionConfigModal
        isOpen={showExecuteModal}
        onClose={() => setShowExecuteModal(false)}
        onExecute={handleExecute}
        workflowName={workflow.name}
        workflowId={id}
        stages={stages}
      />
      {confirmDialog}
    </div>
  );
}

function PlanFact({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-pill bg-lavender-soft px-3 py-1.5">
      <dt className="inline text-ink-muted">{label} </dt>
      <dd className="inline font-book text-ink tabular">{value}</dd>
    </div>
  );
}
