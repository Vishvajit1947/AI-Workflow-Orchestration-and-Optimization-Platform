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
    if (!id) {
      console.warn('fetchStages called without workflow ID');
      return;
    }
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
      .catch((err) => { setDag(null); setDagError(err.response?.data?.detail || err.message); });
  }, [id, stages]);

  const loadLatestExecution = async () => {
    if (!id) {
      console.warn('loadLatestExecution called without workflow ID');
      return;
    }
    try {
      const latest = await executionApi.getLatestExecution(id);
      setExecution(latest);
    } catch (err) {
      // No executions yet, that's fine
      console.log('No previous executions found');
    }
  };

  const handleDelete = async () => {
    if (!id || !confirm('Delete this workflow?')) return;
    await workflowApi.delete(id);
    navigate('/workflows');
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
    } catch (error: any) {
      alert(`Execution failed: ${error.response?.data?.detail || error.message}`);
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
  if (loading && !workflow) return <p className="text-surface-200/50">Loading...</p>;
  if (error) return <p className="text-red-400">Error: {error}</p>;
  if (!id) return <p className="text-red-400">Invalid workflow ID</p>;
  if (!workflow) return <p className="text-surface-200/50">Workflow not found.</p>;

  return (
    <div>
      <Link to="/workflows" className="flex items-center gap-1 text-sm text-surface-200/50 hover:text-white mb-6 transition-colors">
        <ArrowLeft size={16} /> Back to Workflows
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">{workflow.name}</h1>
          {workflow.description && (
            <p className="text-surface-200/50 mt-2">{workflow.description}</p>
          )}
          {workflow.objective && (
            <p className="text-sm text-primary-400/70 mt-1">Objective: {workflow.objective}</p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowExecuteModal(true)}
            disabled={isExecuting || stages.length === 0 || Boolean(dagError)}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play size={16} />
            {isExecuting ? 'Executing...' : 'Execute Workflow'}
          </button>
          <Link
            to={`/workflows/${id}/edit`}
            className="flex items-center gap-1.5 px-3 py-2 bg-surface-700/50 hover:bg-surface-700 rounded-lg text-sm transition-colors"
          >
            <Edit size={14} /> Edit
          </Link>
          <button
            onClick={handleDelete}
            className="flex items-center gap-1.5 px-3 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-sm transition-colors"
          >
            <Trash2 size={14} /> Delete
          </button>
        </div>
      </div>

      {/* Stages */}
      <div className="mb-8">
        {stagesLoading && stages.length === 0 ? (
          <p className="text-surface-200/50">Loading stages...</p>
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
            <h2 className="text-xl font-semibold">Execution Plan</h2>
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
