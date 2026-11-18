/**
 * Live view of a running execution: status and progress, controls, stage counters, the DAG
 * with per-stage status, a timeline of when each stage ran, and stage errors.
 * Updates arrive over the WebSocket (polling fallback) via useExecutionStatus.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Radio, Loader2, Database } from 'lucide-react';
import { useExecutionStatus } from '../hooks/useExecutionStatus';
import { DAGLegend, DAGVisualization, STATUS_STYLES } from './DAGVisualization';
import { ExecutionControls } from './ExecutionControls';
import type { ExecutionStatus, LiveStageStatus } from '../types/execution';
import { StatusBadge } from './ui/StatusBadge';
import { Notice } from './ui/States';
import { formatDuration } from '../lib/format';

interface ExecutionMonitorProps {
  executionId: string;
  onFinished?: (status: ExecutionStatus) => void;
}

/** Re-render every second while `active`, so elapsed times and running bars advance. */
const useTicker = (active: boolean) => {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(timer);
  }, [active]);
};

export const ExecutionMonitor: React.FC<ExecutionMonitorProps> = ({ executionId, onFinished }) => {
  const { status, connected, isActive } = useExecutionStatus(executionId);
  const reported = useRef<string | null>(null);
  useTicker(Boolean(status) && isActive);

  useEffect(() => {
    if (status && !isActive && reported.current !== executionId) {
      reported.current = executionId;
      onFinished?.(status);
    }
  }, [status, isActive, executionId, onFinished]);

  if (!status) {
    return (
      <div className="card flex items-center gap-3 p-6 text-sm text-ink-secondary" role="status">
        <Loader2 size={16} className="animate-spin text-primary" aria-hidden />
        Starting execution…
      </div>
    );
  }

  const byId = Object.fromEntries(status.stages.map((s) => [s.stage_id, s]));
  const done = status.stages.filter((s) => !['pending', 'running'].includes(s.status)).length;
  const running = status.stages.filter((s) => s.status === 'running').length;
  const failed = status.stages.filter((s) => s.status === 'failed').length;
  const cached = status.stages.filter((s) => s.cache_hit).length;
  const failures = status.stages.filter((s) => s.error && s.status !== 'skipped');
  const pct = Math.round(status.progress * 100);
  const elapsed = status.started_at
    ? (status.completed_at ? Date.parse(status.completed_at) : Date.now()) - Date.parse(status.started_at)
    : null;

  return (
    <section className="card overflow-hidden" data-testid="execution-monitor" aria-label="Live execution">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline bg-surface-tint px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-center gap-2.5">
          <h2 className="text-[17px] font-medium text-ink">Live Execution</h2>
          <StatusBadge status={status.status} data-testid="live-status" />
          <span className="chip">{status.parallel ? 'parallel' : 'sequential'}</span>
          {isActive && (
            <span
              className={`inline-flex items-center gap-1.5 text-xs ${connected ? 'text-primary-700' : 'text-ink-muted'}`}
              title={connected ? 'Live updates via WebSocket' : 'Polling for updates'}
            >
              <Radio size={12} aria-hidden className={connected ? 'animate-pulse' : ''} /> {connected ? 'live' : 'polling'}
            </span>
          )}
        </div>
        <ExecutionControls executionId={executionId} status={status.status} />
      </div>

      <div className="space-y-6 p-5 sm:p-6">
        {/* Progress + counters */}
        <div>
          <div className="mb-2 flex items-baseline justify-between gap-3 text-xs text-ink-muted">
            <span>{done} of {status.stages.length} stages finished</span>
            <span className="text-sm font-medium text-ink tabular">{pct}%</span>
          </div>
          <div
            className="h-2 overflow-hidden rounded-full bg-lavender"
            role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Execution progress"
          >
            <div
              className={`relative h-full overflow-hidden rounded-full transition-[width,background-color] duration-700 ease-mercury ${status.status === 'failed' ? 'bg-danger' : 'bg-primary'}`}
              style={{ width: `${status.progress * 100}%` }}
            >
              {/* Faint sheen while work is in progress: activity without a spinner */}
              {status.status === 'running' && (
                <span aria-hidden className="absolute inset-y-0 left-0 w-1/3 animate-sheen bg-gradient-to-r from-transparent via-white/35 to-transparent" />
              )}
            </div>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Counter label="Running" value={running} tone={running ? 'text-primary-700' : undefined} />
            <Counter label="Failed" value={failed} tone={failed ? 'text-danger' : undefined} />
            <Counter label="Cache hits" value={cached} icon={<Database size={11} aria-hidden />} />
            <Counter label="Elapsed" value={elapsed != null && elapsed >= 0 ? formatDuration(elapsed) : '—'} />
          </dl>
        </div>

        {status.dag && (
          <div className="space-y-3">
            <p className="eyebrow">Dependency graph</p>
            <DAGVisualization dag={status.dag} stageStatuses={byId} />
            <DAGLegend live />
          </div>
        )}

        <Timeline stages={status.stages} />

        {status.error && <Notice tone="danger" title="Execution error" className="animate-fade-in-up">{status.error}</Notice>}
        {failures.length > 0 && (
          <div className="space-y-2" aria-label="Stage errors">
            {failures.map((s) => (
              <div key={s.stage_id} className="animate-fade-in-up rounded-card border border-danger-line bg-danger-soft px-4 py-3 text-sm">
                <p className="font-medium text-ink">{s.name}</p>
                <p className="mt-1 break-words font-mono text-xs leading-5 text-danger">{s.error}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};

const Counter: React.FC<{ label: string; value: React.ReactNode; tone?: string; icon?: React.ReactNode }> = ({
  label, value, tone, icon,
}) => (
  <div className="rounded-[10px] bg-lavender-soft px-3 py-2.5">
    <dt className="flex items-center gap-1 text-xs text-ink-muted">{icon}{label}</dt>
    <dd className={`mt-0.5 text-base font-medium tabular transition-colors duration-300 ease-soft ${tone ?? 'text-ink'}`}>{value}</dd>
  </div>
);

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
      <p className="eyebrow mb-3">Timeline</p>
      <div className="space-y-2">
        {stages.map((s) => {
          const style = STATUS_STYLES[s.status] ?? STATUS_STYLES.pending;
          const left = s.started_at ? ((Date.parse(s.started_at) - t0) / span) * 100 : 0;
          const width = s.started_at ? Math.max(((end(s) - Date.parse(s.started_at)) / span) * 100, 1) : 0;
          const seconds = s.started_at ? ((end(s) - Date.parse(s.started_at)) / 1000).toFixed(1) : null;
          return (
            <div key={s.stage_id} className="flex items-center gap-3 text-xs" data-testid={`timeline-${s.stage_id}`}>
              <div className="w-28 min-w-0 sm:w-44">
                <p className="truncate text-ink" title={s.name}>{s.name}</p>
                {(s.model || s.cache_hit) && (
                  <p className="truncate text-[11px] text-ink-muted" title={s.model ?? undefined}>
                    {s.cache_hit ? 'cache hit' : s.model}
                  </p>
                )}
              </div>
              <div className="relative h-5 flex-1 rounded-md bg-lavender-soft">
                {s.started_at && (
                  <div
                    className="absolute top-0 h-5 overflow-hidden rounded-md border-[1.5px] transition-[left,width,background-color,border-color] duration-700 ease-mercury"
                    style={{ left: `${left}%`, width: `${width}%`, background: style.fill, borderColor: style.stroke }}
                  >
                    {s.status === 'running' && (
                      <span aria-hidden className="absolute inset-y-0 left-0 w-1/2 animate-sheen bg-gradient-to-r from-transparent via-white/60 to-transparent" />
                    )}
                  </div>
                )}
              </div>
              <span className="w-16 text-right text-ink-secondary tabular sm:w-20">
                {seconds ? `${seconds}s` : style.label.toLowerCase()}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
