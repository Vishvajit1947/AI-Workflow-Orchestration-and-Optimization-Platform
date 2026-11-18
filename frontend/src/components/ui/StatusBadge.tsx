/**
 * Pill showing a workflow, execution or stage status. One colour per status across the app.
 */
import React from 'react';

const NEUTRAL = 'bg-surface-700/50 text-surface-200/70';

export const STATUS_TONES: Record<string, string> = {
  draft: NEUTRAL,
  pending: NEUTRAL,
  queued: NEUTRAL,
  cancelled: NEUTRAL,
  running: 'bg-blue-500/15 text-blue-300',
  paused: 'bg-amber-500/15 text-amber-300',
  skipped: 'bg-amber-500/15 text-amber-300',
  completed: 'bg-primary-500/15 text-primary-400',
  failed: 'bg-red-500/15 text-red-300',
  // projects
  initializing: NEUTRAL,
  building: 'bg-blue-500/15 text-blue-300',
  succeeded: 'bg-primary-500/15 text-primary-400',
  unavailable: 'bg-amber-500/15 text-amber-300',
};

interface StatusBadgeProps {
  status: string;
  className?: string;
  'data-testid'?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '', ...rest }) => (
  <span
    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_TONES[status] ?? NEUTRAL} ${className}`}
    {...rest}
  >
    {status}
  </span>
);
