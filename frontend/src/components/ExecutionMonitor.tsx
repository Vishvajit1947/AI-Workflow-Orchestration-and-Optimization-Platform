/**
 * Live view of a running execution: status and progress, controls, the DAG with
 * per-stage status, a timeline of when each stage ran, and stage errors.
 */
import React, { useEffect, useRef } from 'react';
import { Radio } from 'lucide-react';
import { useExecutionStatus } from '../hooks/useExecutionStatus';
import { DAGLegend, DAGVisualization, STATUS_STYLES } from './DAGVisualization';
import { ExecutionControls } from './ExecutionControls';
import type { ExecutionStatus, LiveStageStatus } from '../types/execution';

interface ExecutionMonitorProps {
  executionId: string;
  onFinished?: (status: ExecutionStatus) => void;
}

const STATUS_BADGES: Record<string, string> = {
  queued: 'bg-surface-700/50 text-surface-200/70',
  running: 'bg-blue-500/15 text-blue-300',
  paused: 'bg-amber-500/15 text-amber-300',
  completed: 'bg-primary-500/15 text-primary-400',
  failed: 'bg-red-500/15 text-red-300',
  cancelled: 'bg-surface-700/50 text-surface-200/70',
};

export const ExecutionMonitor: React.FC<ExecutionMonitorProps> = ({ executionId, onFinished }) => {
  const { status, connected, isActive } = useExecutionStatus(executionId);
  const reported = useRef<string | null>(null);

  useEffect(() => {
    if (status && !isActive && reported.current !== executionId) {
      reported.current = executionId;
      onFinished?.(status);
    }
  }, [status, isActive, executionId, onFinished]);

  if (!status) {
    return <div className="glass rounded-xl p-6 text-surface-200/50">Starting execution…</div>;
  }

  const byId = Object.fromEntries(status.stages.map((s) => [s.stage_id, s]));
  const done = status.stages.filter((s) => !['pending', 'running'].includes(s.status)).length;
  const failures = status.stages.filter((s) => s.error && s.status !== 'skipped');

  return (
    <div className="glass rounded-xl p-6 space-y-6" data-testid="execution-monitor">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold">Live Execution</h2>
          <span data-testid="live-status" className={`px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_BADGES[status.status]}`}>
            {status.status}
          </span>
          <span className="text-xs text-surface-200/40">{status.parallel ? 'parallel' : 'sequential'}</span>
          {isActive && (
            <span className={`flex items-center gap-1 text-xs ${connected ? 'text-primary-400' : 'text-surface-200/40'}`}
                  title={connected ? 'Live updates via WebSocket' : 'Polling for updates'}>
              <Radio size={12} /> {connected ? 'live' : 'polling'}
            </span>
          )}
        </div>
        <ExecutionControls executionId={executionId} status={status.status} />
      </div>

      {/* Progress */}
      <div>
        <div className="flex justify-between text-xs text-surface-200/50 mb-1.5">
          <span>{done} of {status.stages.length} stages finished</span>
          <span>{Math.round(status.progress * 100)}%</span>
        </div>
        <div className="h-2 rounded-full bg-surface-700/50 overflow-hidden"
             role="progressbar" aria-valuenow={Math.round(status.progress * 100)} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-full bg-primary-500 transition-all duration-300" style={{ width: `${status.progress * 100}%` }} />
        </div>
      </div>

      {status.dag && (
        <div className="space-y-2">
          <DAGVisualization dag={status.dag} stageStatuses={byId} />
          <DAGLegend live />
        </div>
      )}

      <Timeline stages={status.stages} />

      {status.error && <p className="text-sm text-red-400">Execution error: {status.error}</p>}
      {failures.length > 0 && (
        <div className="space-y-1">
          {failures.map((s) => (
            <p key={s.stage_id} className="text-sm text-red-300">
              <span className="font-medium">{s.name}:</span> {s.error}
            </p>
          ))}
        </div>
      )}
    </div>
  );
};

/** One bar per stage from its start to its end (or now, while running), on a shared time axis. */
export const Timeline: React.FC<{ stages: LiveStageStatus[] }> = ({ stages }) => {
  const started = stages.filter((s) => s.started_at);
  if (started.length === 0) return null;

  const now = Date.now();
  const t0 = Math.min(...started.map((s) => Date.parse(s.started_at!)));
  const end = (s: LiveStageStatus) => (s.completed_at ? Date.parse(s.completed_at) : now);
  const t1 = Math.max(...started.map(end), t0 + 1);
  const span = t1 - t0;

  return (
    <div>
      <h3 className="text-sm font-medium text-surface-200/70 mb-2">Timeline</h3>
      <div className="space-y-1.5">
        {stages.map((s) => {
          const style = STATUS_STYLES[s.status] ?? STATUS_STYLES.pending;
          const left = s.started_at ? ((Date.parse(s.started_at) - t0) / span) * 100 : 0;
          const width = s.started_at ? Math.max(((end(s) - Date.parse(s.started_at)) / span) * 100, 1) : 0;
          const seconds = s.started_at ? ((end(s) - Date.parse(s.started_at)) / 1000).toFixed(1) : null;
          return (
            <div key={s.stage_id} className="flex items-center gap-3 text-xs" data-testid={`timeline-${s.stage_id}`}>
              <span className="w-36 truncate text-surface-200/70" title={s.name}>{s.name}</span>
              <div className="relative flex-1 h-4 rounded bg-surface-800/60">
                {s.started_at && (
                  <div className="absolute top-0 h-4 rounded border"
                       style={{ left: `${left}%`, width: `${width}%`, background: style.fill, borderColor: style.stroke }} />
                )}
              </div>
              <span className="w-24 text-right text-surface-200/50">
                {seconds ? `${seconds}s` : style.label.toLowerCase()}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
