import { useParams, Link, useNavigate } from 'react-router-dom';
import { useState, useEffect, useCallback, useRef } from 'react';
import { Edit, Trash2, ArrowLeft, Play } from 'lucide-react';
import { useWorkflow } from '../hooks/useWorkflows';
import { workflowApi } from '../lib/workflows';
import { stageApi } from '../lib/stages';
import { executionApi } from '../api/executionApi';
import StageEditor from '../components/StageEditor';
import { ExecutionConfigModal, type ExecutionConfig } from '../components/ExecutionConfigModal';
import { ExecutionResults } from '../components/ExecutionResults';
import { ExecutionMonitor } from '../components/ExecutionMonitor';
import { DAGLegend, DAGVisualization } from '../components/DAGVisualization';
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
  const finishedExecutionId = useRef<string | null>(null);

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
    if (!id || !confirm('Delete this workflow?')) return;
    try {
      await workflowApi.delete(id);
      navigate('/workflows');
    } catch (err: unknown) {
      alert(`Could not delete the workflow: ${getErrorMessage(err)}`);
    }
  };

  const handleStageUpdate = () => {
    fetchStages();
    refetch();
  };

  const handleExecute = async (config: ExecutionConfig) => {
    if (!id) return;
    setIsExecuting(true);
    try {
      // Run in the background and follow it live
      const response = await executionApi.startExecution(id, { ...config, background: true });
      setLiveExecutionId(response.execution_id);
    } catch (err: unknown) {
      alert(`Execution failed: ${getErrorMessage(err)}`);
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
  if (loading && !workflow) return <p className="text-sm text-surface-200/50">Loading workflow…</p>;
  if (error) return <p role="alert" className="text-sm text-red-400">Could not load the workflow: {error}</p>;
  if (!id) return <p className="text-sm text-red-400">Invalid workflow ID</p>;
  if (!workflow) return <p className="text-sm text-surface-200/50">Workflow not found.</p>;

  return (
    <div>
      <Link to="/workflows" className="btn btn-ghost -ml-3 mb-4">
        <ArrowLeft size={16} aria-hidden /> Workflows
      </Link>

      <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <h1 className="break-words text-2xl font-semibold tracking-tight">{workflow.name}</h1>
          {workflow.description && <p className="mt-1.5 text-surface-200/60">{workflow.description}</p>}
          {workflow.objective && (
            <p className="mt-1.5 text-sm text-surface-200/50">
              <span className="text-surface-200/70">Objective:</span> {workflow.objective}
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            onClick={() => setShowExecuteModal(true)}
            disabled={isExecuting || stages.length === 0 || Boolean(dagError)}
            className="btn btn-primary"
          >
            <Play size={16} aria-hidden />
            {isExecuting ? 'Executing...' : 'Execute Workflow'}
          </button>
          <Link to={`/workflows/${id}/edit`} className="btn btn-secondary">
            <Edit size={14} aria-hidden /> Edit details
          </Link>
          <button onClick={handleDelete} className="btn btn-danger">
            <Trash2 size={14} aria-hidden /> Delete
          </button>
        </div>
      </div>

      {/* Stages */}
      <div className="mb-8">
        {stagesLoading && stages.length === 0 ? (
          <p className="text-sm text-surface-200/50">Loading stages…</p>
        ) : (
          <StageEditor workflowId={id!} stages={stages} onUpdate={handleStageUpdate} />
        )}
      </div>

      {/* Execution plan (idle) or live monitor */}
      {liveExecutionId ? (
        <div className="mb-8">
          <ExecutionMonitor executionId={liveExecutionId} onFinished={handleExecutionFinished} />
        </div>
      ) : (dag || dagError) && (
        <div className="glass rounded-xl p-6 mb-8">
          <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
            <h2 className="text-lg font-semibold">Execution Plan</h2>
            {dag && (
              <p className="text-xs text-surface-200/50">
                {dag.levels.length} level{dag.levels.length === 1 ? '' : 's'} · up to {dag.max_width} in parallel ·
                parallelism {dag.parallelism_factor.toFixed(2)}x · critical path {dag.critical_path.length} stage{dag.critical_path.length === 1 ? '' : 's'}
              </p>
            )}
          </div>
          {dagError ? (
            <p className="text-sm text-red-400">{dagError}</p>
          ) : dag && (
            <div className="space-y-2">
              <DAGVisualization dag={dag} />
              <DAGLegend live={false} />
            </div>
          )}
        </div>
      )}

      {/* Execution Results */}
      {execution && (
        <div className="mb-8">
          <ExecutionResults execution={execution} />
        </div>
      )}

      {/* Execution Config Modal */}
      <ExecutionConfigModal
        isOpen={showExecuteModal}
        onClose={() => setShowExecuteModal(false)}
        onExecute={handleExecute}
        workflowName={workflow.name}
        workflowId={id}
        stages={stages}
      />
    </div>
  );
}
