/**
 * Pause / resume / cancel buttons for a live execution.
 */
import React, { useState } from 'react';
import { Pause, Play, Square } from 'lucide-react';
import { executionApi } from '../api/executionApi';
import type { LiveExecutionStatus } from '../types/execution';

interface ExecutionControlsProps {
  executionId: string;
  status: LiveExecutionStatus;
}

export const ExecutionControls: React.FC<ExecutionControlsProps> = ({ executionId, status }) => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const handleCancel = () => {
    if (confirm('Cancel this execution? Running LLM calls are stopped and remaining stages are skipped.')) {
      run(() => executionApi.cancel(executionId));
    }
  };

  const active = status === 'running' || status === 'paused' || status === 'queued';
  if (!active) return null;

  const button = 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors disabled:opacity-50';
  return (
    <div className="flex items-center gap-2">
      {status === 'paused' ? (
        <button onClick={() => run(() => executionApi.resume(executionId))} disabled={busy}
                className={`${button} bg-primary-500/15 hover:bg-primary-500/25 text-primary-400`}>
          <Play size={14} /> Resume
        </button>
      ) : (
        <button onClick={() => run(() => executionApi.pause(executionId))} disabled={busy}
                className={`${button} bg-amber-500/15 hover:bg-amber-500/25 text-amber-300`}>
          <Pause size={14} /> Pause
        </button>
      )}
      <button onClick={handleCancel} disabled={busy}
              className={`${button} bg-red-500/15 hover:bg-red-500/25 text-red-300`}>
        <Square size={14} /> Cancel
      </button>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  );
};
