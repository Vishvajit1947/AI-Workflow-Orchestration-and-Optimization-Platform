/**
 * Live status of an execution: initial fetch, then WebSocket events
 * (/ws/executions/{id}), with polling as a fallback while the socket is down.
 */
import { useEffect, useRef, useState } from 'react';
import { executionApi } from '../api/executionApi';
import { WS_BASE_URL } from '../lib/api';
import type { ExecutionEvent, ExecutionStatus } from '../types/execution';
import { ACTIVE_EXECUTION_STATUSES } from '../types/execution';

const POLL_INTERVAL_MS = 2000;
const HEARTBEAT_INTERVAL_MS = 20000;

/** Apply one WebSocket event to the current status. Exported for tests. */
export function applyExecutionEvent(prev: ExecutionStatus | null, event: ExecutionEvent): ExecutionStatus | null {
  switch (event.type) {
    case 'snapshot': {
      const { type: _type, ...snapshot } = event;
      return snapshot;
    }
    case 'stage_update':
      if (!prev) return prev;
      return {
        ...prev,
        progress: event.progress,
        stages: prev.stages.map((s) => (s.stage_id === event.stage.stage_id ? event.stage : s)),
      };
    case 'execution_status':
      if (!prev || event.status === 'cancelling') return prev;
      return { ...prev, status: event.status, progress: event.progress, error: event.error ?? prev.error };
    default:
      return prev;
  }
}

const isActive = (status: ExecutionStatus | null) =>
  !status || ACTIVE_EXECUTION_STATUSES.includes(status.status);

export function useExecutionStatus(executionId: string | null) {
  const [status, setStatus] = useState<ExecutionStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const statusRef = useRef<ExecutionStatus | null>(null);
  statusRef.current = status;

  useEffect(() => {
    setStatus(null);
    setConnected(false);
    if (!executionId) return;

    let closed = false;
    let socket: WebSocket | null = null;
    let pollTimer: ReturnType<typeof setInterval> | undefined;
    let heartbeat: ReturnType<typeof setInterval> | undefined;

    const refresh = () =>
      executionApi.getStatus(executionId)
        .then((s) => { if (!closed) setStatus(s); })
        .catch(() => { /* not registered yet, or server restarting: keep last state */ });

    const startPolling = () => {
      if (pollTimer) return;
      pollTimer = setInterval(() => {
        if (isActive(statusRef.current)) refresh();
        else clearInterval(pollTimer);
      }, POLL_INTERVAL_MS);
    };

    refresh();

    try {
      socket = new WebSocket(`${WS_BASE_URL}/ws/executions/${executionId}`);
      socket.onopen = () => {
        setConnected(true);
        heartbeat = setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send('ping'), HEARTBEAT_INTERVAL_MS);
      };
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data) as ExecutionEvent;
        setStatus((prev) => applyExecutionEvent(prev, event));
      };
      socket.onerror = () => startPolling();
      socket.onclose = () => {
        setConnected(false);
        if (!closed) startPolling();
      };
    } catch {
      startPolling();
    }

    return () => {
      closed = true;
      clearInterval(pollTimer);
      clearInterval(heartbeat);
      socket?.close();
    };
  }, [executionId]);

  return { status, connected, isActive: status ? isActive(status) : Boolean(executionId) };
}
