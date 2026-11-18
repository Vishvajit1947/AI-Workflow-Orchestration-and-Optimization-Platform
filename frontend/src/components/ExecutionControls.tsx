/**
 * Pause / resume / cancel buttons for a live execution.
 */
import React, { useState } from 'react';
import { Pause, Play, Square } from 'lucide-react';
import { executionApi } from '../api/executionApi';
import type { LiveExecutionStatus } from '../types/execution';
import { useConfirm } from './ui/Dialog';

interface ExecutionControlsProps {
  executionId: string;
  status: LiveExecutionStatus;
}

export const ExecutionControls: React.FC<ExecutionControlsProps> = ({ executionId, status }) => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirm, confirmDialog] = useConfirm();

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = async () => {
    const ok = await confirm({
      title: 'Cancel this execution?',
      message: 'Running LLM calls are stopped and the remaining stages are skipped. Completed stage results are kept.',
      confirmLabel: 'Cancel execution',
      cancelLabel: 'Keep running',
      destructive: true,
    });
    if (ok) run(() => executionApi.cancel(executionId));
  };

  const active = status === 'running' || status === 'paused' || status === 'queued';
  if (!active) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {status === 'paused' ? (
        <button onClick={() => run(() => executionApi.resume(executionId))} disabled={busy} className="btn btn-primary btn-sm">
          <Play size={13} aria-hidden /> Resume
        </button>
      ) : (
        <button onClick={() => run(() => executionApi.pause(executionId))} disabled={busy} className="btn btn-outline btn-sm">
          <Pause size={13} aria-hidden /> Pause
        </button>
      )}
      <button onClick={handleCancel} disabled={busy} className="btn btn-danger btn-sm">
        <Square size={12} aria-hidden /> Cancel
      </button>
      {error && <span role="alert" className="text-xs text-danger">{error}</span>}
      {confirmDialog}
    </div>
  );
};
